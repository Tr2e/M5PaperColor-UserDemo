"""Apply image date checks without replacing the URL-derived index key."""
import argparse
import json
from index_calendar import ROOT, BRANCH, git

p=argparse.ArgumentParser()
p.add_argument('--commit',action='store_true')
args=p.parse_args()
if args.commit and git('branch','--show-current')!=BRANCH:
    raise SystemExit('Unexpected branch')
checks=json.loads((ROOT/'verified_dates.json').read_text())
for month in sorted({date[:7] for date in checks}):
    path=ROOT/'months'/f'{month}.jsonl'
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    for row in rows:
        if row['date'] not in checks:
            continue
        printed=checks[row['date']]
        row['printed_date']=printed
        row['date_verification']='visually_checked_match' if printed==row['date'] else 'visually_checked_mismatch'
        flags=[f for f in row.get('review_flags',[]) if f!='image_date_mismatch']
        if printed!=row['date']:
            flags.append('image_date_mismatch')
        row['review_flags']=flags
    content=''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows)
    if path.read_text()==content:
        continue
    path.write_text(content)
    if args.commit:
        rel=str(path.relative_to(ROOT));git('add','--',rel)
        git('commit','--only','-m',f'review(owspace): flag image date conflicts in {month}','--',rel)
