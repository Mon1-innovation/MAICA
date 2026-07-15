import asyncio
import re
import json
import traceback

import sqlalchemy
from sqlalchemy.orm import load_only

from typing import *
from pydantic import BaseModel
from random import choice, sample, uniform
from zhconv import convert
from wikipediaapi import AsyncWikipedia, Namespace
from maica.maica_utils import *
from .censor import *

# We need to apply some patches to make wikipediaapi work with proxy
import httpx
from wikipediaapi import AsyncHTTPClient, AsyncWikipediaResource

class ProxiedAsyncHTTPClient(AsyncHTTPClient):

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Patched to accept proxy params.
        """
        super().__init__(*args, **kwargs)
        self._client = httpx.AsyncClient(
            headers=self._default_headers,
            **self._client_kwargs,
            # transport=httpx.AsyncHTTPTransport(),
        )

class ProxiedAsyncWikipedia(AsyncWikipediaResource, ProxiedAsyncHTTPClient):
    pass

# We write the new wiki_get logics here
# The former implementation is shit

async def fetch_ms_meta(fsc: FullSocketsContainer):
    """Main."""
    target_lang = fsc.maica_settings.basic.target_lang
    ms_m = fsc.maica_settings.temp.mspire

    wiki_target_lang = "en" if target_lang == 'auto' else target_lang
    wiki_cursor = ProxiedAsyncWikipedia(
        user_agent = get_ua(),
        language = wiki_target_lang,
        proxy = G.A.PROXY_ADDR or None,
    )

    async def inspect_page(title: str):
        await fsc.messenger(
            "maica_mspire_searching",
            f"MSpire inspecting page: {title}",
            200,
        )
        page = wiki_cursor.page(title)
        if not await page.exists():
            raise MaicaInternetWarning(f"Wikipedia page does not exist: {title}")
        return await page.summary
    
    async def get_category(title: str):
        await fsc.messenger(
            "maica_mspire_searching",
            f"MSpire searching category: {title}",
            200,
        )
        cate = wiki_cursor.page(title)
        members = await cate.categorymembers

        cates = []
        pages = []
        for member in members.values():
            match member.ns:
                case Namespace.MAIN:
                    pages.append(member.title)
                case Namespace.CATEGORY:
                    cates.append(member.title)

        sync_messenger(info=f"Found {len(cates)} categories and {len(pages)} pages underlying", type=MsgType.DEBUG)
        return cates, pages
    
    ctg_decay_factor = 0.8

    async def recur_random(title: str, remaining_depth: int):
        remaining_depth -= 1
        cates, pages = await get_category(title)

        # Sampling
        prob_cates = len(cates) * ms_m.ctg_weight * (1 - (1 / remaining_depth) * ctg_decay_factor)
        prob_pages = len(pages)

        # Deviation prevention
        if prob_cates + prob_pages < 0.001:
            raise MaicaInternetWarning("MSpire hit deadend")

        if prob_cates < 0.001 or remaining_depth <= 1:
            prob_cates = 0
            if not prob_pages:
                raise MaicaInternetWarning("MSpire hit depth limit")

        sums = prob_cates + prob_pages
        rand = uniform(0, sums)
        cp = "cates" if rand < prob_cates else "pages"

        if cp == "cates":
            next_cate_title = choice(cates)
            return await recur_random(next_cate_title, remaining_depth)
        else:
            # We leave candidates in case one does not pass censoring
            return pages

    async def fuzzy_search(kwd: str, ns: int = Namespace.MAIN, limit: int = 1):
        results = await wiki_cursor.search(
            ns=ns,
            limit=limit
        )
        members = [i.title for i in results.pages.values()]

        if not members:
            raise MaicaInternetWarning(f"No result for kwd={kwd} ns={ns}")
        
        return members
    
    titles: list = ms_m.title
    title = to_str(choice(titles), target_lang)

    match ms_m.type:
        case "precise_page":
            step_1 = await fuzzy_search(title)
            result = step_1

        case "fuzzy_page":
            step_1 = await fuzzy_search(title, limit=ms_m.sample)
            result = step_1

        case "in_precise_category":
            step_1 = await fuzzy_search(title, ns=Namespace.CATEGORY)
            step_2 = step_1[0]
            recur_res = await recur_random(step_2, 7)
            result = recur_res

        case "in_fuzzy_category":
            step_1 = await fuzzy_search(title, ns=Namespace.CATEGORY, limit=ms_m.sample)
            step_2 = choice(step_1)
            recur_res = await recur_random(step_2, 7)
            result = recur_res

        case "in_fuzzy_all":
            title = "Category:" + title
            recur_res = await recur_random(title, 7)
            result = recur_res

    result: list[str]
    for title in result:
        summary = await inspect_page(title)

        if not summary or summary.isspace():
            raise MaicaInternetWarning('MSpire got empty summary')
        
        title = convert(title, 'zh-cn')
        summary = convert(summary, 'zh-cn')

        if G.A.CENSOR_MSPIRE != '0':
            tolerance = int(G.A.CENSOR_MSPIRE)

            title_censor = await has_censored(title)
            summary_censor = await has_censored(summary)
            total_censor = title_censor | summary_censor

            if len(total_censor) >= tolerance:
                sync_messenger(info=f"MSpire {title} has censored words or phrases: {total_censor}", type=MsgType.DEBUG)
                continue

            elif len(total_censor):
                sync_messenger(info=f"MSpire page {title} has censored words or phrases but ignored: {total_censor}", type=MsgType.DEBUG)

        break

    else:
        raise MaicaInternetWarning("No proper page found by MSpire")
    
    await fsc.messenger(
        'maica_mspire_page_found',
        f"\nMSpire found page {title}:\n{summary}\nEnd of MSpire page",
        200,
        type=MsgType.INFO,
    )

    return title, summary

_Bt = BilingualText

async def make_inspire(fsc: FullSocketsContainer):
    title, summary = await fetch_ms_meta(fsc)

    summary = ellipsis_large_str(summary)

    prompt = _Bt(
        f"利用提供的以下信息, 主动阐明话题并和[player]聊聊{title}:\n{summary}\n\n你不必在输出中包含内容的全部信息, 但应当融入自己的理解与思考. 你的回答应当有开头招呼, 表现为由你自主发起话题, 并使用自然有感情的聊天语气. 你应当从你自己的角度思考, 不应盲从信息中的评价和判断.",
        f"Summarize the topic and talk about {title} with [player] using provided information below:\n{summary}\n\nYou don't have to include all information provided, but you should combine your own thinking and understanding into your response. Your reply should contain a greeting and brief introduction, act as you started the conversation with this topic, and always use natural emotional tone. You should think from your own perspective, avoid blindly following the judgements from the information.",
    )
    return prompt

MsFromCacheResult = MaicaSettings.Temp.MSpire.MsFromCacheResult

async def ms_from_cache(prompt: str, fsc: FullSocketsContainer):

    prompt_sha = await hash_sha256(prompt)
    mfc_m = MsFromCacheResult(hash=prompt_sha)

    async with DatabaseUtils.SessionData() as dbs:

        stmt = sqlalchemy.select(SqlMsCache).where(
            SqlMsCache.hash == prompt_sha,
        ).options(
            load_only(SqlMsCache.content)
        )
        obj = await dbs.scalar(stmt)

    if obj:
        sync_messenger(info='Hit a stored cache for MSpire', type=MsgType.DEBUG)
        mfc_m.result = obj.content
    else:
        sync_messenger(info='No stored cache for MSpire', type=MsgType.DEBUG)

    return mfc_m

async def ms_to_cache(mfc_m: MsFromCacheResult, fsc: FullSocketsContainer):

    async with DatabaseUtils.SessionData() as dbs:
        async with dbs.begin():

            await sqla_create_or_update(
                dbs,
                SqlMsCache,
                {"hash": mfc_m.hash},
                {
                    "content": mfc_m.result,
                }
            )

    sync_messenger(info='Stored a cache for MSpire', type=MsgType.DEBUG)

if __name__ == '__main__':
    async def main():
        from maica import init
        init()

        fsc = FullSocketsContainer()
        fsc.maica_settings.basic.target_lang = 'en'
        print(await fetch_ms_meta(fsc))

    asyncio.run(main())
