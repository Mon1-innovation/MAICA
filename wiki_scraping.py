import re
import random
import requests
import zhconv
import wikipediaapi
from urllib.parse import unquote
 
def get_redirect_url(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'}
    response = requests.get(url, headers=headers)
    return response.url

def get_page(title=None, target_lang='zh'):
    if target_lang == 'zh':
        category_list=['自然', '自然科学', '社会', '人文', '世界', '生活', '艺术', '文化']
    else:
        category_list=['Nature', 'Natural_sciences', 'Society', 'Humanities', 'World', 'Health', 'Culture', 'The_arts']
    category = random.choice(category_list)
    random_url = rf"https://{target_lang}.wikipedia.org/wiki/Special:%E5%88%86%E7%B1%BB%E5%86%85%E9%9A%8F%E6%9C%BA?wpcategory={category}"
    #i = 1
    #random_url = r"https://randomincategory.toolforge.org/?server=zh.wikipedia.org&cmnamespace=&cmtype=&returntype=&purge=1"
    #for c in category_list:
    #    random_url += f'&category{i}={c}'
    #    i += 1
    #print(random_url)
    #random_url = rf"https://randomincategory.toolforge.org/?category={category}&server=zh.wikipedia.org&cmnamespace=&cmtype=&returntype="
    #random_url = r"https://zh.wikipedia.org/wiki/Special:%E9%9A%8F%E6%9C%BA%E9%A1%B5%E9%9D%A2"
    wiki_pointer = wikipediaapi.Wikipedia('MyProjectName (merlin@example.com)', 'zh')
    if not title:
        #title = unquote(re.search(r'/wiki/(.*)', get_redirect_url(random_url))[1], 'utf-8')
        title = unquote(re.search(r'title=(.*)&', get_redirect_url(random_url))[1], 'utf-8')
        wiki_page = wiki_pointer.page(title)
    else:
        wiki_page = wiki_pointer.page(title)
        if not wiki_page.exists():
            title = zhconv.convert(title, 'zh-hant')
            wiki_page = wiki_pointer.page(title)
    print(f'MSpire acquiring topic: {wiki_page.title}')
    while re.match('category:', wiki_page.title, re.I):
        sub_category = re.search(r'category:(.*)\s*\n*', wiki_page.title, re.I)[1]
        print(f'MSpire acquiring subtopic: {sub_category}')
        #random_url = rf"https://randomincategory.toolforge.org/?category={sub_category}&server=zh.wikipedia.org&cmnamespace=&cmtype=&returntype=&purge=1"
        #print(get_redirect_url(random_url))
        random_url = rf"https://{target_lang}.wikipedia.org/wiki/Special:%E5%88%86%E7%B1%BB%E5%86%85%E9%9A%8F%E6%9C%BA?wpcategory={sub_category}"
        title = unquote(re.search(r'title=(.*)&', get_redirect_url(random_url))[1], 'utf-8')
        wiki_page = wiki_pointer.page(title)
    title = zhconv.convert(title, 'zh-cn')
    summary = re.sub(r'\n*==.*?==$', '', zhconv.convert(wiki_page.summary, 'zh-cn'), re.I|re.S)
    return title, summary

if __name__ == '__main__':
    redir = get_redirect_url(r'https://zh.wikipedia.org/wiki/Special:%E5%88%86%E7%B1%BB%E5%86%85%E9%9A%8F%E6%9C%BA?wpcategory=自然科学')
    print(redir)
    page = get_page()
    print(page[0], page[1])