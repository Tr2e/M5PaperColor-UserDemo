"""Audit the completed date index and its month-by-month Git history."""
from collections import Counter, defaultdict
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parent
expected_months=[f'{year}-{month:02d}' for year in range(2015,2026) for month in range(1,13)]
paths=sorted((ROOT/'months').glob('*.jsonl'))
assert [p.stem for p in paths]==expected_months
rows=[json.loads(line) for path in paths for line in path.read_text().splitlines()]
start=dt.date(2015,1,1)
expected_dates=[str(start+dt.timedelta(days=i)) for i in range(4018)]
assert [r['date'] for r in rows]==expected_dates
for row in rows:
    assert row['quotation_status']=='not_collected'
    assert not {'quote','quotation','body','ocr_text','text'} & set(row)
    assert row['status'] in ('indexed','missing_at_tested_url')
    date=dt.date.fromisoformat(row['date'])
    assert row['url']==f'https://img.owspace.com/Public/uploads/Download/{date.year}/{date:%m%d}.jpg'
    if row.get('date_verification')=='visually_checked_mismatch':
        assert row['printed_date']!=row['date']
        assert 'image_date_mismatch' in row['review_flags']
for year in range(2015,2026):
    review=json.loads((ROOT/'years'/f'{year}-review.json').read_text())
    assert review['date_coverage_pass'] and not review['error_dates']
    batch=[r for r in rows if r['date'].startswith(str(year))]
    assert review['record_count']==len(batch)
    assert review['field_counts']=={key:sum(bool(r.get(key)) for r in batch if r['status']=='indexed') for key in ['title','source','author']}
subjects=subprocess.check_output(['git','log','--format=%s','--','months'],cwd=ROOT,text=True)
committed=set(re.findall(r'^data\(owspace\): index (\d{4}-\d{2}) calendar metadata$',subjects,re.M))
assert set(expected_months)<=committed
tracked=subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines()
assert not any(Path(p).suffix.lower() in {'.jpg','.jpeg','.png','.webp','.gif'} for p in tracked)
indexed=[r for r in rows if r['status']=='indexed']
hashes=defaultdict(list)
for row in indexed:
    hashes[row['image_sha256']].append(row['date'])
audit={
    'date_range':[expected_dates[0],expected_dates[-1]],
    'date_records':len(rows),
    'months':len(paths),
    'months_with_dedicated_data_commit':len(set(expected_months)&committed),
    'status_counts':dict(Counter(r['status'] for r in rows)),
    'distinct_readable_image_hashes':len(hashes),
    'duplicate_image_groups':[dates for dates in hashes.values() if len(dates)>1],
    'confirmed_image_date_mismatches':[{k:r[k] for k in ['date','printed_date','url']} for r in rows if r.get('date_verification')=='visually_checked_mismatch'],
    'field_counts':{key:sum(bool(r.get(key)) for r in indexed) for key in ['title','author','source']},
    'title_kind_counts':dict(Counter(r.get('title_kind') for r in indexed)),
    'visually_verified_metadata_samples':sum(r.get('review_status')=='sample_metadata_verified' for r in rows),
    'review_flag_counts':dict(Counter(flag for r in rows for flag in r.get('review_flags',[]))),
    'quotation_text_collected':False,
    'month_sha256':{p.stem:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
    'limitations':'Metadata only. URL-derived dates and machine OCR are not fully human verified. Readable URLs do not imply distinct or correctly dated images.'
}
out=ROOT/'output'/'collection-audit.json'
out.parent.mkdir(exist_ok=True)
out.write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in audit.items() if k!='month_sha256'},ensure_ascii=False,indent=2))
