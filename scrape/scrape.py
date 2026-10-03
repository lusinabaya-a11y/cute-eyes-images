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
# 1) Cute Eyes sitemap
def sitemap_urls(u,seen=None):
    seen=seen or set(); urls=[]
    r=get(u)
    if r is None or r.status_code!=200: return urls
    locs=re.findall(r'<loc>\s*([^<\s]+)\s*</loc>',r.text)
    for l in locs:
        l=l.replace('&amp;','&')
        if l.endswith('.xml') and l not in seen: seen.add(l); urls+=sitemap_urls(l,seen)
        else: urls.append(l)
    return urls
sm=sitemap_urls('https://cute-eyes.com/sitemap.xml')
out['ce_sitemap']=sm
prod=[u for u in sm if re.search(r'/p\d+(/|$|\?)',u)]
with cf.ThreadPoolExecutor(8) as ex: out['ce_products']=list(ex.map(page_info,prod))
# 2) storefront API attempt
api=[]
for p in range(1,30):
    r=get('https://api.salla.dev/store/v1/products?per_page=50&page=%d'%p,headers={'Store-Identifier':'45801993','Accept':'application/json'})
    if r is None: break
    try: j=r.json()
    except Exception: api.append({'status':r.status_code,'text':r.text[:500]}); break
    api.append(j)
    if not j.get('data') or not (j.get('cursor') or {}).get('next') and not (j.get('pagination') or {}).get('links',{}).get('next'): break
out['ce_api']=api
# 3) old links
olds=[l.strip() for l in open('scrape/old_links.txt') if l.strip()]
with cf.ThreadPoolExecutor(8) as ex: out['old_links']=list(ex.map(page_info,olds))
json.dump(out,open('scrape/result.json','w'),ensure_ascii=False)
print('sitemap',len(sm),'prod',len(prod),'old',len(olds))
