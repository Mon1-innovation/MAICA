import re
import requests
import zhconv
import wikipediaapi
from urllib.parse import unquote
 
def get_redirect_url(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'}
    response = requests.get(url, headers=headers)
    return response.url

def get_random_page():
    random_url = r"https://zh.wikipedia.org/wiki/Special:%E9%9A%8F%E6%9C%BA%E9%A1%B5%E9%9D%A2"
    title = unquote(re.search(r'/wiki/(.*)', get_redirect_url(random_url))[1], 'utf-8')
    #print(title)
    wiki_pointer = wikipediaapi.Wikipedia('MyProjectName (merlin@example.com)', 'zh')
    wiki_page = wiki_pointer.page(title)
    summary = re.sub(r'\n*==.*?==$', '', zhconv.convert(wiki_page.summary, 'zh-hans'), re.I|re.S)
    return title, summary

if __name__ == '__main__':
    print(get_random_page()[1])