import re, json, time, requests, concurrent.futures as cf
from xml.etree import ElementTree as ET
UA={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36','Accept-Language':'ar,en;q=0.8'}
S=requests.Session(); S.headers.update(UA)
out={}
def get(u,**kw):
    for i in range(3):
        try: return S.get(u,timeout=40,**kw)
        except Exception as e: err=e; time.sleep(2)
    return None
def page_info(u):
    r=get(u)
    if r is None: return {'url':u,'error':'fetch failed'}
    h=r.text
    info={'url':u,'final':r.url,'status':r.status_code,'history':[x.url for x in r.history]}
    m=re.search(r'<title>(.*?)</title>',h,re.S); info['title']=m.group(1).strip() if m else None
    m=re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',h); info['canonical']=m.group(1) if m else None
    m=re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']*)',h); info['og_title']=m.group(1) if m else None
    lds=re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>',h,re.S)
    info['ld']=[x.strip()[:4000] for x in lds]
    for k in ['sku','gtin','mpn']:
        m=re.search(r'"%s"\s*:\s*"([^"]*)"'%k,h); info[k]=m.group(1) if m else None
    return info
# 2) storefront API following cursor
api=[]; url='https://api.salla.dev/store/v1/products?per_page=50'
seen=set()
for p in range(60):
    r=get(url,headers={'Store-Identifier':'45801993','Accept':'application/json'})
    if r is None: break
    try: j=r.json()
    except Exception: api.append({'status':r.status_code,'text':r.text[:500]}); break
    api.append(j)
    nxt=(j.get('cursor') or {}).get('next')
    if not j.get('data') or not nxt or nxt in seen: break
    seen.add(nxt); url=nxt; time.sleep(0.5)
out['ce_api']=api
# 3) old links
olds=[l.strip() for l in open('scrape/old_links.txt') if l.strip()]
res=[]
for u in olds:
    for i in range(6):
        x=page_info(u)
        if x.get('status')!=429: break
        time.sleep(5*(i+1))
    res.append(x); time.sleep(1.2)
out['old_links']=res
json.dump(out,open('scrape/result.json','w'),ensure_ascii=False)
print('api pages',len(api),'old',len(olds))
