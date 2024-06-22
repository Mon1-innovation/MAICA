import requests
r = requests.get("https://restapi.amap.com/v3/geocode/geo?key=1f3b9772ea38b61b73ef5bd8ac985a4d&address=湖北鄂州")
print(r.status_code)
#print(r.headers)
print(r.content.decode('utf-8'))