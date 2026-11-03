#!/usr/bin/env python3
"""Remove newly recognized occupation prefixes, committing each changed month."""
import argparse
import json
import re
from index_calendar import ROOT, BRANCH, ROLE_RE, clean, git

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
        match=ROLE_RE.match(author)
        if not match:
            continue
        role=match.group()
        corrected=clean(author[match.end():]).strip(' ，,；;：:')
        if not corrected:
            continue
        row.setdefault('metadata_edits',[]).append({'field':'author','before':author,'after':corrected,'reason':'remove_known_occupation_prefix'})
        row['author']=corrected
        row['author_roles']=list(dict.fromkeys(row.get('author_roles',[])+[role]))
        changed+=1
    if changed:
        path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
        print(path.name,changed)
        if args.commit:
            rel=str(path.relative_to(ROOT));git('add','--',rel)
            git('commit','--only','-m',f'fix(owspace): separate occupation prefixes in {path.stem}','--',rel)
