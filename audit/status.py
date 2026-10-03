import json, time, requests, concurrent.futures as cf
ids = [l.strip() for l in open('audit/ids.txt') if l.strip()]
H = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'Store-Identifier': '45801993', 'Accept-Language': 'ar'}
def get(pid):
    for i in range(4):
        try:
            r = requests.get('https://api.salla.dev/store/v1/products/%s/details' % pid, headers=H, timeout=40)
            if r.status_code == 200:
                d = r.json()['data']
                return pid, {k: d.get(k) for k in ('name', 'status', 'quantity', 'is_available', 'is_out_of_stock', 'type', 'max_quantity')}
            if r.status_code == 404: return pid, {'err': 404}
        except Exception: pass
        time.sleep(2 * (i + 1))
    return pid, {'err': 'fail'}
with cf.ThreadPoolExecutor(6) as ex: res = dict(ex.map(get, ids))
import os; os.makedirs('status_out', exist_ok=True)
json.dump(res, open('status_out/status.json', 'w'), ensure_ascii=False)
print(len(res))
