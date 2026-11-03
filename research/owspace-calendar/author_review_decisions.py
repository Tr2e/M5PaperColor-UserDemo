"""Record visual decisions separately from user-maintained calendar content."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
TMP=Path('/tmp/owspace-author-audit')
def record(start,end,changes=None):
    items=json.loads((TMP/'visual_items.json').read_text())
    path=ROOT/'author_audit/visual_decisions.json'
    decisions=json.loads(path.read_text()) if path.exists() else {}
    changes=changes or {}
    for i in range(start,end):
        row=items[i];evidence=json.loads((TMP/'ocr'/f"{row['date']}.json").read_text())
        decision={'author':row.get('author'),'method':'visual_attribution_crop','image_sha256':evidence['image_sha256'],'note':'对照原图署名区核对。'}
        decision.update(changes.get(i,{}))
        decisions[row['date']]=decision
    path.write_text(json.dumps(decisions,ensure_ascii=False,indent=2)+'\n')
    print('Visual author decisions:',len(decisions))
