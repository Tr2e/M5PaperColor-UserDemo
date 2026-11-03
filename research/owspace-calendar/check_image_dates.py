"""Check URL dates against image month/day candidates in 2024 and 2025."""
import argparse
import concurrent.futures
import json
import subprocess
import tempfile
import threading
from pathlib import Path
from index_calendar import ROOT, fetch, git, BRANCH

p=argparse.ArgumentParser();p.add_argument('year',type=int,choices=[2024,2025]);p.add_argument('--commit',action='store_true');p.add_argument('--normalize-existing',action='store_true');args=p.parse_args()
if args.commit and git('branch','--show-current')!=BRANCH:raise SystemExit('Unexpected branch')
local=threading.local();processes=[]
def classify(result,row):
    if result.get('status') in ('request_error','ocr_error'):return result
    result.pop('candidate_date',None)
    if args.year==2024 and len(result['months'])==1:
        result['day_status']='unsupported_split_numeral_layout'
        result['candidate_month']=result['months'][0]
        result['status']='month_candidate_match' if result['candidate_month']==int(row['date'][5:7]) else 'month_candidate_mismatch'
    elif len(result['months'])==len(result['days'])==1:
        result['candidate_date']=f"{args.year}-{result['months'][0]:02d}-{result['days'][0]:02d}"
        result['status']='candidate_match' if result['candidate_date']==row['date'] else 'candidate_mismatch'
    elif len(result['months'])==1 and result['months'][0]!=int(row['date'][5:7]):
        result['candidate_month']=result['months'][0];result['status']='month_candidate_mismatch'
    else:result['status']='unresolved'
    return result

def check(row):
    status,body,_,_,error=fetch(row['url'],.25)
    if status!=200 or body is None:return {'status':'request_error','http_status':status}
    try:
        with tempfile.NamedTemporaryFile(suffix='.jpg',prefix='owspace-date-') as f:
            f.write(body);f.flush()
            if not hasattr(local,'ocr'):
                local.ocr=subprocess.Popen(['/tmp/owspace-research/ocr_dates'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1);processes.append(local.ocr)
            local.ocr.stdin.write(json.dumps({'path':f.name,'year':args.year})+'\n');local.ocr.stdin.flush()
            result=json.loads(local.ocr.stdout.readline())
        return classify(result,row)
    except Exception as e:return {'status':'ocr_error','error':str(e)}

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    for path in sorted((ROOT/'months').glob(f'{args.year}-*.jsonl')):
        rows=[json.loads(l) for l in path.read_text().splitlines()]
        todo=[] if args.normalize_existing else [r for r in rows if r['status']=='indexed' and not r.get('image_date_ocr')]
        futures={pool.submit(check,r):r for r in todo}
        for future in concurrent.futures.as_completed(futures):
            row=futures[future];result=future.result();row['image_date_ocr']=result
        for row in rows:
            if not row.get('image_date_ocr'):continue
            result=classify(row['image_date_ocr'],row)
            row['review_flags']=[f for f in row.get('review_flags',[]) if f!='image_date_suspected_mismatch']
            if result['status'] in ('candidate_mismatch','month_candidate_mismatch') and not row.get('date_verification','').startswith('visually_checked'):
                row['review_flags'].append('image_date_suspected_mismatch')
        path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
        print(path.stem,[(r['date'],r['image_date_ocr']) for r in rows if r.get('image_date_ocr',{}).get('status') in ('candidate_mismatch','month_candidate_mismatch','request_error','ocr_error')],flush=True)
        if args.commit:
            rel=str(path.relative_to(ROOT));git('add','--',rel)
            if git('diff','--cached','--name-only','--',rel):git('commit','--only','-m',f'review(owspace): check printed month and day in {path.stem}','--',rel)
for proc in processes:
    proc.stdin.close();proc.wait()
