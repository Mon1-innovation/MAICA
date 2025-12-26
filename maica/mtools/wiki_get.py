import re
import random
import asyncio
import zhconv

from typing import *
from maica.maica_utils import *
from .censor import *
 
async def get_multi_json(*list_url):
    list_resp = await asyncio.gather(*[dld_json(u) for u in list_url])
    return list_resp

async def get_page(title=None, target_lang='zh'):
    cat_scraper = re.compile(r'Category\s*:\s*(.*)', re.I)
    zh_scraper = re.compile(r'[一-龥]')
    def_cat = True
    use_page = None
    sample = set_sample = 250
    cat_weight = 10
    page_found = None
    insanity = 0

    if title and isinstance(title, dict) and 'type' in title:
        # {"type": "in_category/in_fuzzy_category/page/fuzzy_page", "sample": 200, "title": "anything"}
        maica_assert(title['title'], 'title')
        maica_assert(isinstance(title['sample'], int), 'sample')
        match title.get('type'):
            case detypo if detypo in ['percise_page', 'precise_page']:
                next_title = title['title']
                use_page = True
                sample = 1
                if isinstance(title['sample'], int) and 2 <= title['sample'] <= 250:
                    set_sample = title['sample']
            case 'fuzzy_page':
                next_title = title['title']
                use_page = True
                if isinstance(title['sample'], int) and 2 <= title['sample'] <= 250:
                    sample = set_sample = title['sample']
            case detypo if detypo in ['in_percise_category', 'in_precise_category']:
                next_title = title['title']
                use_page = False
                sample = 1
                if isinstance(title['sample'], int) and 2 <= title['sample'] <= 250:
                    set_sample = title['sample']
            case 'in_fuzzy_category':
                next_title = title['title']
                use_page = False
                if isinstance(title['sample'], int) and 2 <= title['sample'] <= 250:
                    sample = set_sample = title['sample']
            case 'in_fuzzy_all':
                next_title = title['title']
                use_page = None
                if isinstance(title['sample'], int) and 2 <= title['sample'] <= 250:
                    sample = set_sample = title['sample']
            case _:
                raise MaicaInputWarning('MSpire type not matched')
    else:
        if target_lang == 'zh':
            category_list=['自然', '自然科学', '社会', '人文學科', '世界', '生活', '艺术', '文化']
        else:
            category_list=['Nature', 'Natural_sciences', 'Society', 'Humanities', 'World', 'Health', 'Culture', 'The_arts']

        category = random.choice(category_list)
        next_title = f"incategory:{category}"
        # def_cat = True
    next_title_fs = next_title

    while not page_found:
        insanity += 1
        if insanity > 15:
            raise MaicaInternetWarning('MSpire searching entered deadend', '404', 'maica_mspire_search_deadend')
        if title and insanity > 6:
            raise MaicaInputWarning('MSpire prompt not found on wikipedia', '410', 'maica_mspire_prompt_bad')
        
        # Skipping this by default
        if insanity == 1 and not def_cat and not use_page and zh_scraper.search(next_title):
            nxt_hans=zhconv.convert(next_title, 'zh-hans');nxt_hant=zhconv.convert(next_title, 'zh-hant')
            hans_list, hant_list = await get_multi_json(f"https://{target_lang}.wikipedia.org/w/api.php?action=query&format=json&list=search&redirects=1&utf8=1&formatversion=2&srsearch={nxt_hans}&srnamespace=0%7C14&srlimit=1&sroffset=0&srprop=", f"https://{target_lang}.wikipedia.org/w/api.php?action=query&format=json&list=search&redirects=1&utf8=1&formatversion=2&srsearch={nxt_hant}&srnamespace=0%7C14&srlimit=1&sroffset=0&srprop=")
            hans_len, hant_len = hans_list['query']['searchinfo']['totalhits'], hant_list['query']['searchinfo']['totalhits']
            if hans_len >= hant_len:
                next_title = nxt_hans
                await messenger(info='MSpire using simplified Chinese title', type=MsgType.DEBUG)
            else:
                next_title = nxt_hant
                await messenger(info='MSpire using traditional Chinese title', type=MsgType.DEBUG)

        if insanity >= 2:
            sample = set_sample
        page_url = f"https://{target_lang}.wikipedia.org/w/api.php?action=query&format=json&list=search&redirects=1&utf8=1&formatversion=2&srsearch={next_title}&srnamespace=0&srlimit={sample}&sroffset=0&srprop="
        cat_url = f"https://{target_lang}.wikipedia.org/w/api.php?action=query&format=json&list=search&redirects=1&utf8=1&formatversion=2&srsearch={next_title}&srnamespace=14&srlimit={sample}&sroffset=0&srprop="
        next_item = None

        match use_page:
            case None:
                page_list, cat_list = await get_multi_json(page_url, cat_url)
            case True:
                page_list, cat_list = await dld_json(page_url), {"batchcomplete":True,"query":{"searchinfo":{"totalhits":0},"search":[]}}
            case False:
                page_list, cat_list = {"batchcomplete":True,"query":{"searchinfo":{"totalhits":0},"search":[]}}, await dld_json(cat_url)

        page_list_r, cat_list_r = page_list['query']['search'], cat_list['query']['search']

        for cat in cat_list_r:
            if ReUtils.re_search_wiki_avoid.search(cat['title'].lower()):
                cat_list_r.remove(cat)

        if len(cat_list_r):
            if use_page == False or random.randint(1, cat_weight*len(cat_list_r)+len(page_list_r)) <= cat_weight*len(cat_list_r):
                next_item = random.choice(cat_list_r)
                next_cat_title = cat_scraper.match(next_item['title'])[1]
                next_title = f"incategory:{next_cat_title.replace(' ', '_')}"
                await messenger(info=f"MSpire entering fork: {next_cat_title}", type=MsgType.DEBUG)
                use_page = None
            else:
                next_item = random.choice(page_list_r)
                next_title = next_item['title']
                confirmed = await confirm_page(next_title, target_lang)
                if confirmed:
                    await messenger(info=f"MSpire hit midway page: {next_title}", type=MsgType.LOG)
                    return confirmed
                else:
                    await messenger(info=f"MSpire hit bad page: {next_title} --trying again", type=MsgType.WARN)
                    next_title = next_title_fs
                    insanity += 1

        elif len(page_list_r):
            next_item = random.choice(page_list_r)
            next_title = next_item['title']
            confirmed = await confirm_page(next_title, target_lang)
            if confirmed:
                await messenger(info=f"MSpire hit bottom page: {next_title}", type=MsgType.LOG)
                return confirmed
            else:
                await messenger(info=f"MSpire hit bad page: {next_title} --trying again", type=MsgType.WARN)
                next_title = next_title_fs
                insanity += 2

        else:
            await messenger(info='MSpire hit deadend--trying again', type=MsgType.DEBUG)
            next_title = next_title_fs
            insanity += 3

async def confirm_page(title, target_lang='zh') -> Union[False, tuple[str, str]]:
    """We have a likely-ultimately page, now confirm if it's suitable in all aspects."""
    finale_url = f"https://{target_lang}.wikipedia.org/w/api.php?action=query&format=json&prop=extracts&exsentences=15&exlimit=1&titles={title}&explaintext=1&formatversion=2"
    #print(finale_url)
    summary_json = await dld_json(finale_url)

    title = zhconv.convert(summary_json['query']['pages'][0]['title'], 'zh-cn')
    summary_raw = summary_json['query']['pages'][0]['extract']

    summary = re.sub(r'(\n|\s)*\n(\n|\s)*', r'\n', re.sub(r'\n*=+(.*?)=+', r'\n\1:', zhconv.convert(summary_raw, 'zh-cn'), re.I|re.S))

    if G.A.CENSOR_MSPIRE == '1':
        title_censor = await has_censored(title)
        if title_censor:
            sync_messenger(info=f"MSpire title {title} has censored words: {title_censor}", type=MsgType.DEBUG)
            return False

        # Some tolerance settings can be added here
        summary_censor = await has_censored(summary)
        if len(summary_censor) > 3:
            sync_messenger(info=f"MSpire page {title} has censored words: {summary_censor}", type=MsgType.DEBUG)
            return False
        elif summary_censor:
            sync_messenger(info=f"MSpire page {title} has censored words but ignored: {summary_censor}", type=MsgType.DEBUG)

    return title, summary

if __name__ == '__main__':
    import asyncio
    s = asyncio.run(get_page('Images_of_nature',target_lang='en'))
    print(s[1])