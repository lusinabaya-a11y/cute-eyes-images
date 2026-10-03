import os, time, urllib.request, concurrent.futures as cf
os.makedirs('ce_images', exist_ok=True)
items=[l.rstrip('\n').split('\t') for l in open('ce_urls.txt') if l.strip()]
def get(it):
    pid,u=it; dst=f'ce_images/{pid}_'+os.path.basename(u)
    for i in range(4):
        try:
            data=urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=60).read()
            open(dst,'wb').write(data); return 'ok'
        except Exception as e: err=str(e); time.sleep(2*(i+1))
    return 'fail '+err
print(list(cf.ThreadPoolExecutor(8).map(get,items)).count('ok'),'of',len(items))
