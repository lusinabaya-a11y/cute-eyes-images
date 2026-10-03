import json, re, requests
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36', 'Accept-Language': 'ar'}
out = {}
for u in ['https://cute-eyes.com/نيو-هير-لوشن-لتقليل-تساقط-الشعر-وتقوية-البصيلات-120-مل/p1196938686',
          'https://cute-eyes.com/العناية-بالشعر/c347476573',
          'https://cute-eyes.com/wrong-slug/p1196938686',
          'https://cute-eyes.com/x/p999999999',
          'https://cute-eyes.com/عدسات-لنس-مي-لاتيه-latte/p1762712017']:
    r = requests.get(u, headers=H, timeout=40, allow_redirects=True)
    t = r.text
    out[u] = {'status': r.status_code, 'final': r.url, 'len': len(t), 'hist': [h.status_code for h in r.history],
              'imgs': sorted(set(re.findall(r'https://cdn\.salla\.sa/[^"\'\s)]+?\.(?:jpe?g|png|webp)', t)))[:80],
              'title': (re.findall(r'<title>(.*?)</title>', t, re.S) or [''])[0][:200]}
    if 'p1196938686' in u and 'wrong' not in u: open('page.html', 'w').write(t)
S = requests.Session(); S.headers.update({'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Store-Identifier': '45801993', 'Accept-Language': 'ar'})
for path in ['/products/1196938686/images', '/products/1196938686/gallery', '/products/1196938686/options', '/products/details/1196938686', '/products/1271829032/details']:
    r = S.get('https://api.salla.dev/store/v1' + path, timeout=40)
    out[path] = {'status': r.status_code, 'body': r.text[:1500]}
json.dump(out, open('probe.json', 'w'), ensure_ascii=False)
