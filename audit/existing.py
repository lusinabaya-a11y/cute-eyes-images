"""Audit every Cute Eyes product: gallery images (old logo), descriptions (old store name), links."""
import json, os, re, time, html, urllib.parse, concurrent.futures as cf
import requests, cv2, numpy as np
from PIL import Image

STORE = '45801993'
API = 'https://api.salla.dev/store/v1/products/%s/details'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36'
OUT = 'audit_out'; os.makedirs(OUT + '/thumbs', exist_ok=True); os.makedirs('imgs', exist_ok=True)
ids = [l.strip() for l in open('audit/existing_ids.txt') if l.strip()]

OLD_NAME = re.compile(r'بيوت[يى]\s*لاين|beauty[\s\-_]*line|thebeautyline|الحطامي|مؤسسة\s+هالة|VZmWZ|yvXbz', re.I)
GAL = re.compile(r'https://cdn\.salla\.sa/mQNzdE/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})-([\d.]+)x([\d.]+)-([A-Za-z0-9]+)\.(jpe?g|png|webp|gif)', re.I)
HREF = re.compile(r'<a\b[^>]*href=(["\'])(.*?)\1', re.I | re.S)
IMGSRC = re.compile(r'<img\b[^>]*src=(["\'])(.*?)\1', re.I | re.S)

import threading
_lock = threading.Lock(); _last = [0.0]; GAP = float(os.environ.get('GAP', '0.8'))
def get(u, **kw):
    site = 'cute-eyes.com' in u
    for i in range(8):
        if site:
            with _lock:
                wait = _last[0] + GAP - time.time()
                if wait > 0: time.sleep(wait)
                _last[0] = time.time()
        try:
            r = requests.get(u, timeout=45, **kw)
        except Exception:
            time.sleep(2 * (i + 1)); continue
        if r.status_code == 429 or (site and r.status_code >= 500):
            ra = r.headers.get('Retry-After')
            time.sleep(min(int(ra) if ra and ra.isdigit() else 20 * (i + 1), 120)); continue
        return r
    return r if 'r' in dir() else None

def strip(h):
    return html.unescape(re.sub(r'<[^>]+>', ' ', h or '')).replace('\xa0', ' ')

def ctx(text, m, n=60):
    return ' '.join(text[max(0, m.start() - n): m.end() + n].split())


def page(pid):
    r = get(API % pid, headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Store-Identifier': STORE, 'Accept-Language': 'ar'})
    if r is None or r.status_code != 200: return {'id': pid, 'err': 'details'}
    d = r.json().get('data') or {}
    url = d.get('url'); rec = {'id': pid, 'name': d.get('name'), 'url': url, 'main': (d.get('image') or {}).get('url')}
    p = get(url, headers={'User-Agent': UA, 'Accept-Language': 'ar'})
    if p is None or p.status_code != 200 or 'Just a moment' in p.text[:3000]:
        rec['page_err'] = p.status_code if p is not None else 'fail'; return rec
    best = {}
    for m in GAL.finditer(p.text):
        uid, w, h = m.group(1), float(m.group(2)), float(m.group(3))
        if uid not in best or w * h > best[uid][0]: best[uid] = (w * h, m.group(0))
    rec['gallery'] = [u for _, u in best.values()]
    return rec
recs = [page(pid) for pid in ids]
print('pages ok', sum('gallery' in r for r in recs), 'of', len(recs))
sift = cv2.SIFT_create(); TPL = {}; TSS = {}
for name, fn, ts in [('A', 'audit/tpl.png', 2.0), ('B', 'audit/tplB.png', 2.0), ('iA', 'audit/iconA.png', 3.0), ('iB', 'audit/iconB.png', 3.0), ('tA', 'audit/textA.png', 3.0), ('tB', 'audit/textB.png', 3.0)]:
    rgb = cv2.cvtColor(cv2.imread(fn), cv2.COLOR_BGR2RGB)
    g = cv2.cvtColor(cv2.resize(rgb, None, fx=ts, fy=ts, interpolation=cv2.INTER_CUBIC), cv2.COLOR_RGB2GRAY)
    k, dsc = sift.detectAndCompute(g, None); TPL[name] = (k, dsc); TSS[name] = ts
def gold(bgr):
    h = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    return ((h[..., 0] >= 5) & (h[..., 0] <= 25) & (h[..., 1] >= 35) & (h[..., 1] <= 200) & (h[..., 2] >= 90)).astype(np.float32)
GICONS = [gold(cv2.imread(f)) for f in ('audit/iconA.png', 'audit/iconB.png')]
def ncc_icons(bgr):
    G = gold(bgr); best = (0.0, None)
    if G.sum() < 20: return best
    for ic in GICONS:
        for sc in (0.35, 0.45, 0.55, 0.7, 0.85, 1.0, 1.2, 1.45, 1.75, 2.1, 2.5):
            t = cv2.resize(ic, None, fx=sc, fy=sc, interpolation=cv2.INTER_AREA)
            if t.shape[0] >= G.shape[0] or t.shape[1] >= G.shape[1] or t.shape[0] < 12: continue
            r = cv2.matchTemplate(G, t, cv2.TM_CCOEFF_NORMED); r[~np.isfinite(r)] = 0
            _, mx, _, loc = cv2.minMaxLoc(r)
            if mx > best[0]: best = (float(mx), [int(loc[0]), int(loc[1]), int(t.shape[1]), int(t.shape[0])])
    return best

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
    src = np.float32([tk[m.queryIdx].pt for m in good]) / TSS[name]
    dst = np.float32([ik[m.trainIdx].pt for m in good]) / k
    M, inl = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=4)
    if M is None: return {'n': len(good), 'inl': 0}
    return {'n': len(good), 'inl': int(inl.sum()), 's': float(np.hypot(M[0, 0], M[1, 0])), 'tx': float(M[0, 2]), 'ty': float(M[1, 2])}

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
        for t in TPL: res[t] = {'inl': 0}
    else:
        for t in TPL: res[t] = match(t, ik, idd, k)
    bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    if max(H, W) > 1000: bgr = cv2.resize(bgr, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    res['ncc'], res['ncc_box'] = ncc_icons(bgr)
    sane = lambda d: d.get('inl', 0) >= 6 and 0.15 < d.get('s', 0) < 3
    if any(sane(res[t]) for t in TPL) or res['ncc'] >= 0.6:
        res['thumb'] = '%s_%s.jpg' % (pid, abs(hash(u)) % 10**9)
        th = Image.fromarray(img); th.thumbnail((500, 500)); th.save('%s/thumbs/%s' % (OUT, res['thumb']), quality=80)
    os.remove(fn)
    return res

jobs = [(r['id'], 'gallery', u) for r in recs for u in r.get('gallery', [])]
with cf.ThreadPoolExecutor(8) as ex:
    img_res = list(ex.map(scan, jobs))
json.dump({'products': recs, 'images': img_res}, open(OUT + '/existing.json', 'w'), ensure_ascii=False)
print('images', len(img_res))
