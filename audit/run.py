"""Audit every Cute Eyes product: gallery images (old logo), descriptions (old store name), links."""
import json, os, re, time, html, urllib.parse, concurrent.futures as cf
import requests, cv2, numpy as np
from PIL import Image

STORE = '45801993'
API = 'https://api.salla.dev/store/v1/products/%s/details'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
OUT = 'audit_out'; os.makedirs(OUT + '/thumbs', exist_ok=True); os.makedirs('imgs', exist_ok=True)
ids = [l.strip() for l in open('audit/ids.txt') if l.strip()]

OLD_NAME = re.compile(r'بيوت[يى]\s*لاين|beauty[\s\-_]*line|thebeautyline|الحطامي|مؤسسة\s+هالة|VZmWZ|yvXbz', re.I)
GAL = re.compile(r'https://cdn\.salla\.sa/mQNzdE/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})-([\d.]+)x([\d.]+)-([A-Za-z0-9]+)\.(jpe?g|png|webp|gif)', re.I)
HREF = re.compile(r'<a\b[^>]*href=(["\'])(.*?)\1', re.I | re.S)
IMGSRC = re.compile(r'<img\b[^>]*src=(["\'])(.*?)\1', re.I | re.S)

def get(u, **kw):
    for i in range(4):
        try:
            return requests.get(u, timeout=45, **kw)
        except Exception:
            time.sleep(2 * (i + 1))
    return None

def strip(h):
    return html.unescape(re.sub(r'<[^>]+>', ' ', h or '')).replace('\xa0', ' ')

def ctx(text, m, n=60):
    return ' '.join(text[max(0, m.start() - n): m.end() + n].split())

def product(pid):
    rec = {'id': pid}
    r = get(API % pid, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Store-Identifier': STORE, 'Accept-Language': 'ar'})
    if r is None or r.status_code != 200:
        rec['err'] = 'details %s' % (r.status_code if r is not None else 'fail'); return rec
    d = r.json().get('data') or {}
    desc = d.get('description') or ''
    rec.update(name=d.get('name'), url=d.get('url'), status=d.get('status'), promo=d.get('promotion_title'), subtitle=d.get('subtitle'),
               main_alt=(d.get('image') or {}).get('alt'), main_img=(d.get('image') or {}).get('url'))
    # text checks on name / promo / description / main alt
    hits = []
    for field, txt in [('name', d.get('name')), ('promo', d.get('promotion_title')), ('subtitle', d.get('subtitle')), ('alt', rec['main_alt']), ('desc', strip(desc))]:
        for m in OLD_NAME.finditer(txt or ''):
            hits.append([field, ctx(txt, m)])
    # raw html of description too (catches old names inside link targets / image urls)
    for m in OLD_NAME.finditer(desc):
        hits.append(['desc_html', ctx(desc, m, 80)])
    rec['text_hits'] = hits
    rec['links'] = [html.unescape(h[1]).strip() for h in HREF.findall(desc)]
    rec['desc_imgs'] = [html.unescape(s[1]).strip() for s in IMGSRC.findall(desc)]
    # product page: full gallery + any old name anywhere in the product page
    page = get(rec['url'], headers={'User-Agent': UA, 'Accept-Language': 'ar'}) if rec['url'] else None
    if page is None or page.status_code != 200:
        rec['page_err'] = page.status_code if page is not None else 'fail'
        rec['gallery'] = [rec['main_img']] if rec['main_img'] else []
        return rec
    t = page.text
    best = {}
    for m in GAL.finditer(t):
        uid, w, h = m.group(1), float(m.group(2)), float(m.group(3))
        if uid not in best or w * h > best[uid][0]:
            best[uid] = (w * h, m.group(0))
    desc_set = set(rec['desc_imgs'])
    rec['gallery'] = [u for _, u in best.values() if u not in desc_set]
    page_hits = []
    for m in OLD_NAME.finditer(t):
        page_hits.append(ctx(t, m, 80))
    rec['page_hits'] = page_hits[:20]
    alts = re.findall(r'alt=(["\'])(.*?)\1', t)
    rec['alt_hits'] = sorted({a[1] for a in alts if OLD_NAME.search(a[1])})
    return rec

t0 = time.time()
with cf.ThreadPoolExecutor(6) as ex:
    recs = list(ex.map(product, ids))
print('products', len(recs), 'errors', sum('err' in r for r in recs), 'page errors', sum('page_err' in r for r in recs), round(time.time() - t0), 's')

# ---- link checks
links = sorted({l for r in recs for l in r.get('links', [])})
def check(u):
    if not u.startswith('http'):
        return u, {'kind': 'relative/other'}
    host = urllib.parse.urlparse(u).netloc.lower()
    if 'cute-eyes.com' not in host:
        return u, {'kind': 'external', 'host': host}
    r = get(u, headers={'User-Agent': UA}, allow_redirects=True)
    if r is None: return u, {'kind': 'internal', 'status': 'fail'}
    final = urllib.parse.unquote(r.url)
    home = urllib.parse.urlparse(r.url).path in ('', '/', '/ar', '/ar/', '/en', '/en/')
    title = (re.findall(r'<title>(.*?)</title>', r.text, re.S) or [''])[0].strip()
    return u, {'kind': 'internal', 'status': r.status_code, 'final': final, 'went_home': home and urllib.parse.urlparse(u).path not in ('', '/'), 'redirects': [h.status_code for h in r.history], 'title': title[:150]}
with cf.ThreadPoolExecutor(6) as ex:
    link_res = dict(ex.map(check, links))
print('links', len(links), round(time.time() - t0), 's')

# ---- images: download + logo detection
sift = cv2.SIFT_create(); TS = 2.0; TPL = {}
for name, fn in [('A', 'audit/tpl.png'), ('B', 'audit/tplB.png')]:
    rgb = cv2.cvtColor(cv2.imread(fn), cv2.COLOR_BGR2RGB)
    g = cv2.cvtColor(cv2.resize(rgb, None, fx=TS, fy=TS, interpolation=cv2.INTER_CUBIC), cv2.COLOR_RGB2GRAY)
    k, dsc = sift.detectAndCompute(g, None); TPL[name] = (k, dsc)

def load_rgb(path):
    im = Image.open(path)
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA'); bg = Image.new('RGBA', im.size, (255, 255, 255, 255)); bg.alpha_composite(im); im = bg
    return np.array(im.convert('RGB'))

def match(name, ik, idd, k):
    tk, td = TPL[name]
    ms = cv2.BFMatcher(cv2.NORM_L2).knnMatch(td, idd, k=2)
    good = [m for m, n in (p for p in ms if len(p) == 2) if m.distance < 0.75 * n.distance]
    if len(good) < 6: return {'n': len(good), 'inl': 0}
    src = np.float32([tk[m.queryIdx].pt for m in good]) / TS
    dst = np.float32([ik[m.trainIdx].pt for m in good]) / k
    M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=4)
    if M is None: return {'n': len(good), 'inl': 0}
    return {'n': len(good), 'inl': int(inl.sum()), 's': float(np.hypot(M[0, 0], M[1, 0])), 'tx': float(M[0, 2]), 'ty': float(M[1, 2])}

jobs = []
for r in recs:
    for u in r.get('gallery', []): jobs.append((r['id'], 'gallery', u))
    for u in r.get('desc_imgs', []):
        if u.startswith('http'): jobs.append((r['id'], 'desc', u))
def scan(job):
    pid, kind, u = job
    fn = 'imgs/%s_%d' % (pid, abs(hash(u)) % 10**9)
    r = get(u, headers={'User-Agent': UA})
    if r is None or r.status_code != 200 or len(r.content) < 200:
        return {'id': pid, 'kind': kind, 'url': u, 'err': r.status_code if r is not None else 'fail'}
    open(fn, 'wb').write(r.content)
    try:
        img = load_rgb(fn)
    except Exception as e:
        return {'id': pid, 'kind': kind, 'url': u, 'err': 'decode'}
    H, W = img.shape[:2]
    g = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY); k = 1.0
    if max(H, W) > 1000: k = 1000 / max(H, W); g = cv2.resize(g, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    ik, idd = sift.detectAndCompute(g, None)
    res = {'id': pid, 'kind': kind, 'url': u, 'W': W, 'H': H}
    if idd is None or len(ik) < 2:
        res['A'] = res['B'] = {'inl': 0}
    else:
        res['A'] = match('A', ik, idd, k); res['B'] = match('B', ik, idd, k)
    if max(res['A'].get('inl', 0), res['B'].get('inl', 0)) >= 8:
        res['thumb'] = '%s_%s.jpg' % (pid, abs(hash(u)) % 10**9)
        th = Image.fromarray(img); th.thumbnail((500, 500)); th.save('%s/thumbs/%s' % (OUT, res['thumb']), quality=80)
    os.remove(fn)
    return res
with cf.ThreadPoolExecutor(8) as ex:
    img_res = list(ex.map(scan, jobs))
print('images', len(img_res), 'errors', sum('err' in i for i in img_res), round(time.time() - t0), 's')

json.dump({'products': recs, 'links': link_res, 'images': img_res}, open(OUT + '/audit.json', 'w'), ensure_ascii=False)
