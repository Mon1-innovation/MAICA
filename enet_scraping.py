import re
from search_engines import Google, Bing

def internet_search_limb(query):
    engine = Bing()
    engine.set_headers({'User-Agent':f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 OPR/109.0.0.0"})
    results = engine.search(query, pages=2)
    slt_default = []
    slt_humane = ''
    rank = 0
    for item in results:
        rank += 1
        title = item['title']
        text = re.sub(r'.*?(?=[\u4e00-\u9fa5])', '', item['text'], 1, re.I)
        if rank <= 5:
            slt_default.append({'rank': rank, 'title': title, 'text': text})
        if rank <= 3:
            slt_humane += f'信息{rank} 标题:{title} 内容:{text}'
    return True, None, slt_default, slt_humane

if __name__ == '__main__':
    print(internet_search_limb('现在的天气怎么样? 鄂州')[2])