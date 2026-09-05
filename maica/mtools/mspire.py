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

# We need an explicit lifecycle hook for the persistent async client.
from wikipediaapi import AsyncHTTPClient, AsyncWikipediaResource

class ProxiedAsyncHTTPClient(AsyncHTTPClient):

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Keep the library client and expose its missing close hook.
        """
        super().__init__(*args, **kwargs)

    async def close(self) -> None:
        await self._client.aclose()

class ProxiedAsyncWikipedia(AsyncWikipediaResource, ProxiedAsyncHTTPClient):
    pass


# We write the new wiki_get logics here
# The former implementation is shit


def _is_not_template(name: str):
    name = convert(name.casefold().strip(), locale="zh-cn")
    for template_kw in ("模板", "template"):
        if name.startswith(template_kw) or name.endswith(template_kw):
            return False
    return True


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

    try:
        return await _fetch_ms_meta(fsc, wiki_cursor, target_lang, ms_m)
    finally:
        await wiki_cursor.close()


async def _fetch_ms_meta(
    fsc: FullSocketsContainer,
    wiki_cursor: ProxiedAsyncWikipedia,
    target_lang: str,
    ms_m: MaicaSettings.Temp.MSpire,
):

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
    
    async def get_category(title: str, use_search=False):
        await fsc.messenger(
            "maica_mspire_searching",
            f"MSpire searching {'pseudo ' if use_search else ''}category: {title}",
            200,
        )

        if use_search:
            cates, pages = await asyncio.gather(
                fuzzy_search(title, ns=Namespace.CATEGORY, limit=ms_m.sample, no_raise=True),
                fuzzy_search(title, limit=ms_m.sample, no_raise=True),
            )

        else:
            cate = wiki_cursor.page(title)
            members = await cate.categorymembers

            cates = []
            pages = []
            for member in members.values():
                if _is_not_template(member.title):
                    match member.ns:
                        case Namespace.MAIN:
                            pages.append(member.title)
                        case Namespace.CATEGORY:
                            cates.append(member.title)

        sync_messenger(info=f"Found {len(cates)} categories and {len(pages)} pages underlying", type=MsgType.DEBUG)
        return cates, pages
    
    ctg_decay_factor = 0.8

    async def recur_random(title: str, remaining_depth: int, use_search=False):
        remaining_depth -= 1
        cates, pages = await get_category(title, use_search)

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

    async def fuzzy_search(kwd: str, ns: int = Namespace.MAIN, limit: int = 1, no_raise=False):
        results = await wiki_cursor.search(
            query=kwd,
            ns=ns,
            limit=limit
        )
        members = [i.title for i in results.pages.values()]

        if not members:
            msg = f"No result for kwd={kwd} ns={ns}"
            if not no_raise:
                raise MaicaInternetWarning(msg)
            else:
                sync_messenger(info=msg, type=MsgType.DEBUG)
                members = []
        
        return members
    
    titles: list = ms_m.title
    title = to_str(choice(titles), target_lang)

    match ms_m.type:
        case "precise_page":
            result = [title]

        case "fuzzy_page":
            step_1 = await fuzzy_search(title, limit=ms_m.sample)
            result = step_1

        case "in_precise_category":
            step_1 = "Category:" + title
            recur_res = await recur_random(step_1, 10)
            result = recur_res

        case "in_fuzzy_category":
            step_1 = await fuzzy_search(title, ns=Namespace.CATEGORY, limit=ms_m.sample)
            step_2 = choice(step_1)
            recur_res = await recur_random(step_2, 10)
            result = recur_res

        case "in_fuzzy_all":
            recur_res = await recur_random(title, 10, use_search=True)
            result = recur_res

    result: list[str]
    for title in result:
        summary = await inspect_page(title)

        if not summary or summary.isspace():
            raise MaicaInternetWarning('MSpire got empty summary')
        
        title = convert(title, 'zh-cn')
        summary = convert(summary, 'zh-cn')

        tolerance = int(G.A.CENSOR_MSPIRE or 0)
        if tolerance:

            title_censor = await has_censored(title)
            summary_censor = await has_censored(summary)
            total_censor = title_censor | summary_censor

            if len(total_censor) >= tolerance:
                sync_messenger(info=f"MSpire {title} has censored words or phrases: {total_censor}", type=MsgType.DEBUG)
                continue

            elif len(total_censor):
                sync_messenger(info=f"MSpire page {title} has censored words or phrases but ignored: {total_censor}", type=MsgType.DEBUG)

            else:
                sync_messenger(info=f"MSpire page {title} has nothing censored", type=MsgType.DEBUG)

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
        f"""你在随意翻阅维基百科时, 看到了以下条目:

{title}
{summary}

请以此为话题引子, 以自然的聊天语气发起话题, 与{{player_name}}聊天. 输出应包括合理的开头, 介绍, 衔接与收尾.
你不必在输出中包含内容的全部信息, 但应当融入自己的理解与思考, 不应盲从信息中的评价和判断.""",
        f"""You came across the following entry on Wikipedia while surfing:

{title}
{summary}

Use it as a topic starter, and start a casual conversation with {{player_name}} in natural tone. Include necessary beginning, introduction, connecting and ending.
You don't have to include all information provided, but you should combine your own thinking and understanding into your response, avoid blindly following the judgements from the information.""",
    )
    return prompt

MsFromCacheResult = MaicaSettings.Temp.MSpire.MsFromCacheResult

async def ms_from_cache(prompt: str, fsc: FullSocketsContainer):

    prompt_sha = await hash_sha256(prompt)
    mfc_m = MsFromCacheResult(hash=prompt_sha, prompt=prompt)

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
                    "user_id": fsc.maica_settings.verification.user_id,
                    "prompt": mfc_m.prompt,
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
