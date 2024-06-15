from search_engines import Google, Bing

def internet_search_limb(query):
    engine = Bing()
    results = engine.search(query, pages=2)
    slt_default = []
    slt_humane = ''
    rank = 0
    for item in results:
        rank += 1
        title = item['title']
        text = item['text']
        if rank <= 5:
            slt_default.append({'rank': rank, 'title': title, 'text': text})
        if rank <= 3:
            slt_humane += f'信息{rank} 标题:{title} 内容:{text}'
    return True, None, slt_default, slt_humane

if __name__ == '__main__':
    print(internet_search_limb('湖北鄂州附近有哪些提供红烧肉和土豆丝的餐厅？')[2])