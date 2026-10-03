import os, sys, time, urllib.request, concurrent.futures as cf
os.makedirs('originals', exist_ok=True)
urls=[u.strip() for u in open('urls.txt') if u.strip()]
def get(u):
    dst=os.path.join('originals', os.path.basename(u))
    if os.path.exists(dst) and os.path.getsize(dst)>0: return u, 'skip'
    for i in range(4):
        try:
            req=urllib.request.Request(u, headers={'User-Agent':'Mozilla/5.0'})
            data=urllib.request.urlopen(req, timeout=60).read()
            open(dst,'wb').write(data); return u, 'ok'
        except Exception as e:
            err=str(e); time.sleep(2*(i+1))
    return u, 'fail '+err
res=list(cf.ThreadPoolExecutor(16).map(get, urls))
fails=[f'{u}\t{s}' for u,s in res if s.startswith('fail')]
open('download_failures.txt','w').write('\n'.join(fails)+'\n')
print('total',len(urls),'fail',len(fails))
