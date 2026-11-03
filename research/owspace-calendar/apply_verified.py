#!/usr/bin/env python3
"""Apply visually checked metadata samples, grouped into monthly commits."""
import argparse
import json
from index_calendar import ROOT, BRANCH, git

p=argparse.ArgumentParser()
p.add_argument('year',type=int)
p.add_argument('--commit',action='store_true')
args=p.parse_args()
if args.commit and git('branch','--show-current') != BRANCH:
    raise SystemExit('Unexpected branch')
verified=json.loads((ROOT/'verified_samples.json').read_text())
for path in sorted((ROOT/'months').glob(f'{args.year}-*.jsonl')):
    rows=[json.loads(l) for l in path.read_text().splitlines()]
    changed=0
    for row in rows:
        if row['date'] not in verified or row['status']!='indexed' or row.get('review_status')=='sample_metadata_verified':
            continue
        values=verified[row['date']]
        for field,value in zip(['title','author','source'],values):
            if row.get(field)!=value:
                row.setdefault('metadata_edits',[]).append({'field':field,'before':row.get(field),'after':value,'reason':'visually_checked_against_official_image'})
            row[field]=value
        row['title_kind']=next((c for c in ['宜','忌'] if c in (row.get('title') or '')), '其他') if row.get('title') else '问答' if row.get('layout_variant')=='reader_question' else None
        row['review_status']='sample_metadata_verified'
        row['manual_review_fields']=['title','author','source']
        row['source_status']='printed' if row['source'] else 'not_printed_in_reviewed_sample'
        row['author_status']='printed' if row['author'] else 'not_printed_in_reviewed_sample'
        row['review_flags']=[]
        changed+=1
    if changed:
        path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
        print(path.name,changed)
        if args.commit:
            rel=str(path.relative_to(ROOT));git('add','--',rel)
            git('commit','--only','-m',f'review(owspace): verify metadata samples in {path.stem}','--',rel)
