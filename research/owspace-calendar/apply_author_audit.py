"""Apply image-verified author decisions, protecting all user-maintained content."""
import argparse,copy,hashlib,json,subprocess
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent;AUDIT=ROOT/'author_audit'
EDITABLE={'author','author_foreign_name','review_flags','metadata_edits','author_name_audit'}
def protected(row):
 return hashlib.sha256(json.dumps({k:v for k,v in row.items() if k not in EDITABLE},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def run(apply=False,commit=False):
 baseline={r['date']:r for r in json.loads((AUDIT/'baseline.json').read_text())}
 decisions={}
 for name in ['visual_decisions','foreign_decisions']:
  for date,d in json.loads((AUDIT/f'{name}.json').read_text()).items():decisions[date]={**decisions.get(date,{}),**d}
 paths=sorted((ROOT/'months').glob('*.jsonl'));batches={p:[json.loads(l) for l in p.read_text().splitlines()] for p in paths}
 # Validate every record before the first write, not just changed records.
 for batch in batches.values():
  for r in batch:assert protected(r)==baseline[r['date']]['protected_sha256'],f"Protected content changed: {r['date']}"
 changes=[];changed_months=[]
 for p,batch in batches.items():
  before=copy.deepcopy(batch)
  for r in batch:
   d=decisions.get(r['date'])
   if not d:continue
   assert d['image_sha256']==r['image_sha256'],r['date']
   assert not d.get('needs_full_image'),r['date']
   fields=[k for k in ('author','author_foreign_name') if k in d]
   delta={k:{'before':baseline[r['date']].get(k),'after':d[k]} for k in fields if baseline[r['date']].get(k)!=d[k]}
   for k in fields:r[k]=d[k]
   flags=list(r.get('review_flags',[]))
   if 'author' in fields:
    flags=[f for f in flags if f not in ('author_unresolved','author_format_review','author_not_credited_in_reviewed_region')]
    if r['author'] is None:flags.append('author_not_credited_in_reviewed_region')
   for flag in ['source_name_conflict','source_name_suspect']:
    if d.get(flag) and flag not in flags:flags.append(flag)
   r['review_flags']=flags
   r['author_name_audit']={'date':'2026-11-03','method':d['method'],'fields':fields,'image_sha256':d['image_sha256'],'note':d['note']}
   if delta:
    changes.append({'date':r['date'],'url':r['url'],'changes':delta,'note':d['note'],'source_issue':bool(d.get('source_name_conflict') or d.get('source_name_suspect'))})
    edits=r.setdefault('metadata_edits',[])
    edit={'audit':'author_names_2026-11-03','changes':delta,'evidence_image_sha256':d['image_sha256']}
    if edit not in edits:edits.append(edit)
   assert protected(r)==baseline[r['date']]['protected_sha256']
  if batch!=before:
   changed_months.append(p.stem)
   if apply:
    p.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in batch))
    if commit:
     subprocess.run(['git','add','--',str(p)],check=True)
     subprocess.run(['git','commit','--only','-m',f'fix(owspace): verify author names in {p.stem}','--',str(p)],check=True,stdout=subprocess.DEVNULL)
 allrows=[r for b in batches.values() for r in b]
 summary={'baseline_commit':json.loads((AUDIT/'scan.json').read_text())['summary']['baseline_commit'],'date_records_scanned':len(allrows),'distinct_original_author_values':2187,'original_image_regions_reprocessed':2177,'visually_reviewed_records':len(decisions),'changed_records':len(changes),'changed_author_fields':sum('author' in c['changes'] for c in changes),'changed_foreign_name_fields':sum('author_foreign_name' in c['changes'] for c in changes),'changed_records_by_month':dict(sorted(Counter(c['date'][:7] for c in changes).items())),'source_conflicts':[r['date'] for r in allrows if 'source_name_conflict' in r.get('review_flags',[])],'source_suspected_errors':[r['date'] for r in allrows if 'source_name_suspect' in r.get('review_flags',[])],'protected_records_verified':len(allrows),'protected_fields':'All fields except author, author_foreign_name, review_flags, metadata_edits, author_name_audit; includes excerpts, occupations, source, title and dates.','scope':'All existing author values inventoried; suspicious names visually compared with source images. Other foreign names compared by new OCR, not individually visually verified. No blanket accuracy claim.'}
 if apply:
  (AUDIT/'changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
  (AUDIT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(summary,ensure_ascii=False,indent=2));print('Months requiring writes:',len(changed_months))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--commit',action='store_true');a=p.parse_args();assert not a.commit or a.apply;run(a.apply,a.commit)
