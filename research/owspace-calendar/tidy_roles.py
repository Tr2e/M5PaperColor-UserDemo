#!/usr/bin/env python3
"""Remove newly recognized occupation prefixes, committing each changed month."""
import argparse
import json
import re
from index_calendar import ROOT, BRANCH, ROLE_RE, clean, clean_author_footer, git

p=argparse.ArgumentParser()
p.add_argument('year',type=int)
p.add_argument('--commit',action='store_true')
args=p.parse_args()
if args.commit and git('branch','--show-current') != BRANCH:
    raise SystemExit('Unexpected branch')
for path in sorted((ROOT/'months').glob(f'{args.year}-*.jsonl')):
    rows=[json.loads(l) for l in path.read_text().splitlines()]
    changed=0
    for row in rows:
        author=row.get('author')
        if not author:
            continue
        if row.get('review_status')=='sample_metadata_verified':
            continue
        match=ROLE_RE.match(author)
        role=match.group() if match else None
        corrected=clean(author[match.end():]).strip(' ，,；;：:') if match else author
        corrected=clean_author_footer(corrected)
        if corrected==author:
            continue
        row.setdefault('metadata_edits',[]).append({'field':'author','before':author,'after':corrected,'reason':'remove_known_occupation_prefix_or_footer_ocr_noise'})
        row['author']=corrected
        if role:
            row['author_roles']=list(dict.fromkeys(row.get('author_roles',[])+[role]))
        if not corrected:
            row['review_flags']=list(dict.fromkeys(row.get('review_flags',[])+['author_unresolved']))
        changed+=1
    if changed:
        path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
        print(path.name,changed)
        if args.commit:
            rel=str(path.relative_to(ROOT));git('add','--',rel)
            git('commit','--only','-m',f'fix(owspace): separate occupation prefixes in {path.stem}','--',rel)
