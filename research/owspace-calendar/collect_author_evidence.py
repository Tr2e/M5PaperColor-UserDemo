"""Re-read only attribution regions; never change existing calendar content."""
import concurrent.futures,hashlib,json,subprocess,threading
from pathlib import Path
from index_calendar import ROOT,fetch
TMP=Path('/tmp/owspace-author-audit');(TMP/'images').mkdir(parents=True,exist_ok=True);(TMP/'ocr').mkdir(exist_ok=True)
items=json.loads((ROOT/'author_audit/scan.json').read_text())['candidates']
items.sort(key=lambda r:(r['reasons']==['foreign_script_parser_review'],r['date']))
local=threading.local();processes=[]
def one(row):
    target=TMP/'ocr'/f"{row['date']}.json"
    if target.exists():return 'cached'
    image=TMP/'images'/f"{row['date']}.jpg"
    if not image.exists() or image.stat().st_size==0:
        status,body,_,_,error=fetch(row['url'],.3)
        if status!=200 or body is None:return 'request_error:'+row['date']
        image.write_bytes(body)
    if not hasattr(local,'ocr'):
        local.ocr=subprocess.Popen([str(TMP/'ocr_author_review')],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1);processes.append(local.ocr)
    local.ocr.stdin.write(json.dumps({'path':str(image),'year':int(row['date'][:4]),'layout_variant':row.get('layout_variant')})+'\n');local.ocr.stdin.flush()
    result=json.loads(local.ocr.stdout.readline())
    if 'error' in result:return 'ocr_error:'+row['date']
    result.update(date=row['date'],url=row['url'],image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),baseline_image_sha256=row['image_sha256'])
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    return 'ok'
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for i,result in enumerate(pool.map(one,items),1):
        if result not in ('cached','ok'):print(result,flush=True)
        if i%50==0:print(f'{i}/{len(items)} attribution regions processed',flush=True)
for proc in processes:proc.stdin.close();proc.wait()
print('Completed author evidence collection',flush=True)
