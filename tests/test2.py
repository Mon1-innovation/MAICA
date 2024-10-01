from search_engines import Google, Bing

engine = Bing()
results = engine.search("鄂州附近提供红烧肉和土豆丝的餐厅", pages=1)
for item in results:
    print(item)

print(results.titles)