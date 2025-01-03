import re
import random
import asyncio
import aiohttp
import zhconv
import wikipediaapi
from urllib.parse import unquote
from loadenv import load_env
 
async def get_json(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, proxy=load_env('PROXY_ADDR')) as resp:
            res = await resp.json()
            await asyncio.sleep(0)
            await session.close()
            return res

async def get_multi_json(*list_url):
    list_resp = await asyncio.gather(*[get_json(u) for u in list_url])
    return list_resp

def get_page(title=None, target_lang='zh'):
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
        match title['type']:
            case 'percise_page':
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
            case 'in_percise_category':
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
                raise Exception('MSpire type not matched')
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
            raise Exception('MSpire insanity limit reached')
        # Skipping this by default
        if insanity == 1 and not def_cat and not use_page and zh_scraper.search(next_title):
            nxt_hans=zhconv.convert(next_title, 'zh-hans');nxt_hant=zhconv.convert(next_title, 'zh-hant')
            hans_list, hant_list = asyncio.run(get_multi_json(f"https://{target_lang}.wikipedia.org/w/api.php?action=query&format=json&list=search&redirects=1&utf8=1&formatversion=2&srsearch={nxt_hans}&srnamespace=0%7C14&srlimit=1&sroffset=0&srprop=", f"https://{target_lang}.wikipedia.org/w/api.php?action=query&format=json&list=search&redirects=1&utf8=1&formatversion=2&srsearch={nxt_hant}&srnamespace=0%7C14&srlimit=1&sroffset=0&srprop="))
            hans_len, hant_len = hans_list['query']['searchinfo']['totalhits'], hant_list['query']['searchinfo']['totalhits']
            if hans_len >= hant_len:
                next_title = nxt_hans
                print('MSpire using simplified Chinese title')
            else:
                next_title = nxt_hant
                print('MSpire using traditional Chinese title')
        if insanity >= 2:
            sample = set_sample
        page_url = f"https://{target_lang}.wikipedia.org/w/api.php?action=query&format=json&list=search&redirects=1&utf8=1&formatversion=2&srsearch={next_title}&srnamespace=0&srlimit={sample}&sroffset=0&srprop="
        cat_url = f"https://{target_lang}.wikipedia.org/w/api.php?action=query&format=json&list=search&redirects=1&utf8=1&formatversion=2&srsearch={next_title}&srnamespace=14&srlimit={sample}&sroffset=0&srprop="
        next_item = None
        match use_page:
            case None:
                page_list, cat_list = asyncio.run(get_multi_json(page_url, cat_url))
            case True:
                page_list, cat_list = asyncio.run(get_json(page_url)), {"batchcomplete":True,"query":{"searchinfo":{"totalhits":0},"search":[]}}
            case False:
                page_list, cat_list = {"batchcomplete":True,"query":{"searchinfo":{"totalhits":0},"search":[]}}, asyncio.run(get_json(cat_url))
        page_list_r, cat_list_r = page_list['query']['search'], cat_list['query']['search']
        for cat in cat_list_r:
            temp_kwd = '模板' if target_lang == 'zh' else 'template'
            if temp_kwd in cat['title'].lower():
                cat_list_r.remove(cat)
        if cat_list['query']['searchinfo']['totalhits']:
            if use_page == False or random.randint(1, cat_weight*len(cat_list_r)+len(page_list_r)) <= cat_weight*len(cat_list_r):
                next_item = random.choice(cat_list_r)
                next_cat_title = cat_scraper.match(next_item['title'])[1]
                next_title = f"incategory:{next_cat_title}"
                print(f"MSpire entering fork: {next_cat_title}")
                use_page = None
            else:
                next_item = random.choice(page_list_r)
                next_title = next_item['title']
                page_found = next_title
                print(f"MSpire hit midway page: {next_title}")
        elif page_list['query']['searchinfo']['totalhits']:
            next_item = random.choice(page_list_r)
            next_title = next_item['title']
            page_found = next_title
            print(f"MSpire hit bottom page: {next_title}")
        else:
            print('MSpire hit deadend--trying again')
            next_title = next_title_fs

    wiki_pointer = wikipediaapi.Wikipedia('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36', target_lang, proxies={'https': load_env("PROXY_ADDR")})
    page_wiki = wiki_pointer.page(page_found)
    title = zhconv.convert(page_wiki.title, 'zh-cn')
    #print(wiki_page.summary)
    summary = re.sub(r'\n*==.*?==$', '', zhconv.convert(page_wiki.summary, 'zh-cn'), re.I|re.S)
    return title, summary

if __name__ == '__main__':
    page = get_page({"type": "in_fuzzy_all", "sample": 200, "title": "人文学科"}, 'zh')
    #page = get_page(None, 'zh')
    print(page[0], page[1])
    import time
    time.sleep(10)