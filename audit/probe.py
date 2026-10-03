import json, requests
S = requests.Session()
S.headers.update({'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Store-Identifier': '45801993', 'Accept-Language': 'ar'})
out = {}
for pid in ['1689249826', '1196938686', '1762712017']:
    for path in ['/products/%s/details', '/products/%s']:
        u = 'https://api.salla.dev/store/v1' + path % pid
        try:
            r = S.get(u, timeout=40); out[u] = {'status': r.status_code, 'body': r.json() if 'json' in r.headers.get('content-type', '') else r.text[:3000]}
        except Exception as e: out[u] = {'err': str(e)}
r = requests.get('https://cute-eyes.com/p1689249826', headers={'User-Agent': 'Mozilla/5.0'}, timeout=40, allow_redirects=True)
out['page'] = {'status': r.status_code, 'final': r.url, 'len': len(r.text)}
r = requests.get('https://cute-eyes.com/p999999999', headers={'User-Agent': 'Mozilla/5.0'}, timeout=40, allow_redirects=True)
out['page404'] = {'status': r.status_code, 'final': r.url, 'len': len(r.text)}
json.dump(out, open('probe.json', 'w'), ensure_ascii=False)
