import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;TMP=Path('/tmp/owspace-author-audit')
def record(start,end,overrides=None):
 rows=json.loads((TMP/'foreign_review.json').read_text());p=ROOT/'author_audit/foreign_decisions.json';decisions=json.loads(p.read_text()) if p.exists() else {}
 for i in range(start,end):
  r=rows[i];o=json.loads((TMP/'ocr'/f"{r['date']}.json").read_text())
  d={'author_foreign_name':r['multilingual'],'method':'visual_attribution_crop','image_sha256':o['image_sha256'],'note':'重新对照原图外文署名；保留原图拼写。'}
  x=(overrides or {}).get(i,{})
  if isinstance(x,str):x={'author_foreign_name':x}
  d.update(x);decisions[r['date']]=d
 p.write_text(json.dumps(decisions,ensure_ascii=False,indent=2)+'\n');print('Foreign visual decisions',len(decisions))
