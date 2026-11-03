"""Compare attribution-only OCR against existing names; never modify data."""
import json,re,unicodedata,difflib
from pathlib import Path
ROOT=Path(__file__).resolve().parent;TMP=Path('/tmp/owspace-author-audit')
def norm(s):return ''.join(c.lower() for c in unicodedata.normalize('NFKC',s or '') if c.isalpha())
def candidates(lines,old):
    found=[]
    for line in lines:
        text=line['text']
        # Foreign runs may share a line with the Chinese credit. Exclude source titles.
        text=re.split('[《〈]',text)[0]
        for s in re.findall(r'[A-Za-zÀ-ɏЀ-ӿ][A-Za-zÀ-ɏЀ-ӿ\s.·•,&’\x27\-]+',text):
            s=s.strip(' .·•,');n=norm(s)
            if len(n)<3 or n in ('owspace','owspacc','owspce'):continue
            if s.lower().startswith(('actor,','philosopher,','poet,')):s=s.split(',',1)[1].strip()
            score=difflib.SequenceMatcher(None,n,norm(old)).ratio()
            found.append((score,s,line['confidence']))
    return sorted(found,reverse=True)
def main():
    rows=json.loads((ROOT/'author_audit/scan.json').read_text())['candidates']
    decisions=json.loads((ROOT/'author_audit/visual_decisions.json').read_text())
    comparisons=[];review=[]
    for row in rows:
        old=row.get('author_foreign_name')
        if not old or 'author_foreign_name' in decisions.get(row['date'],{}):continue
        p=TMP/'ocr'/f"{row['date']}.json"
        if not p.exists():continue
        o=json.loads(p.read_text());m=candidates(o['multilingual'],old);l=candidates(o['latin'],old)
        ms=m[0][1] if m else None;ls=l[0][1] if l else None
        same=norm(old)==norm(ms) or norm(old)==norm(ls)
        item=dict(row,multilingual=ms,latin=ls,ocr_agrees=norm(ms)==norm(ls),same_letters=same)
        comparisons.append(item)
        if not same:review.append(item)
    (TMP/'foreign_comparisons.json').write_text(json.dumps(comparisons,ensure_ascii=False,indent=2))
    # Stable date order. Only render complete-year batches while collection runs.
    (TMP/'foreign_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2))
    print('compared',len(comparisons),'different',len(review))
if __name__=='__main__':main()
