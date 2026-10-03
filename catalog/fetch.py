import json, time, requests
S = requests.Session()
S.headers.update({'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Store-Identifier': '45801993', 'Accept-Language': 'ar'})
url = 'https://api.salla.dev/store/v1/products?per_page=50'
out = []; seen = set(); pages = 0
for _ in range(200):
    for i in range(4):
        try:
            r = S.get(url, timeout=40); break
        except Exception: time.sleep(3)
    j = r.json(); pages += 1
    for p in j.get('data', []):
        out.append({k: p.get(k) for k in ('id', 'name', 'sku', 'url', 'status', 'price', 'is_available', 'quantity')} | {'image': (p.get('image') or {}).get('url')})
    nxt = (j.get('cursor') or {}).get('next')
    if not j.get('data') or not nxt or nxt in seen: break
    seen.add(nxt); url = nxt; time.sleep(0.4)
json.dump(out, open('catalog.json', 'w'), ensure_ascii=False)
print('pages', pages, 'products', len(out))
