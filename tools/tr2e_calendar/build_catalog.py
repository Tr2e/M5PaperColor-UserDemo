"""Export the existing private study data; no network, no source record edits."""
import collections,difflib,hashlib,json,re,sys,unicodedata
from pathlib import Path

ROOT=Path(__file__).resolve().parent;RESEARCH=ROOT.parents[1]/'research/owspace-calendar'
sys.path.insert(0,str(RESEARCH))
from content_analysis_author_dates import AUTHORS

PATTERNS={
 'reading':r'书|阅读|读书|朗读|写作|诗', 'love':r'爱|恋|亲密|相伴|相守|拥抱|温柔|婚姻',
 'childhood':r'孩子|儿童|童年|童心|天真|好奇|成长|想象', 'rest':r'休息|偷懒|睡|放空|闲|工作|劳作|劳动',
 'journey':r'旅行|远行|上路|出发|路途|远方|旅途|出游', 'renewal':r'新生|开始|重新|明天|未来|希望|翻页|梦想',
 'memory':r'回忆|思念|怀念|告别|遗忘|记忆', 'family':r'亲人|家人|回家|团圆|家乡|父亲|母亲|故乡|返乡',
 'moon':r'月亮|月光|赏月|明月', 'spring':r'春|发芽|花开|苏醒', 'summer':r'夏|暑|蝉|清凉|纳凉',
 'autumn':r'秋|落叶|收获', 'winter':r'冬|雪|寒冷|炉火|火锅', 'women':r'女性|女人|女孩|妇女|她们',
}
def normalize(s):return ''.join(c for c in unicodedata.normalize('NFKC',s or '') if c.isalnum()).lower()

def main():
    files=sorted((RESEARCH/'months').glob('*.jsonl'));rows=[json.loads(l) for p in files for l in p.read_text().splitlines()]
    aliases={s:a for a in AUTHORS for s in a['aliases']}
    records=[]
    for r in rows:
        if r['status']!='indexed' or r.get('date_verification')=='visually_checked_mismatch':continue
        text=r.get('excerpt') or '';norm=normalize(text);title=r.get('title') or '';author=aliases.get(r.get('author'))
        tags=[tag for tag,pattern in PATTERNS.items() if re.search(pattern,title+' '+text)]
        records.append(dict(id=r['date'],source_date=r['date'],title=title,kind=r.get('title_kind'),excerpt=text,author=r.get('author') or '',source=r.get('source') or '',roles=r.get('author_roles',[]),foreign_name=r.get('author_foreign_name') or '',url=r['url'],tags=tags,
          eligible=bool(norm and len(norm)>=8 and title and r.get('title_kind') in ('宜','忌')),
          quality='source_text_not_fully_reviewed',confidence=r.get('excerpt_ocr_confidence_min'),author_id=author['name'] if author else r.get('author') or '',
          birth_md=author['birth'][5:] if author and author['birth'] else None,death_md=author['death'][5:] if author and author['death'] else None,
          normalized=norm,title_key=normalize(title)))
    parent=list(range(len(records)))
    def find(i):
        while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
        return i
    def join(i,j):parent[find(j)]=find(i)
    exact={};inverted=collections.defaultdict(list);comparisons=0;near_merges=0
    for i,r in enumerate(records):
        s=r['normalized']
        if not s:continue
        if s in exact:join(i,exact[s])
        else:exact[s]=i
        grams={s[k:k+3] for k in range(len(s)-2)}
        candidates=collections.Counter(j for gram in grams for j in inverted[gram])
        for j,shared in candidates.items():
            t=records[j]['normalized']
            if find(i)==find(j) or min(len(s),len(t))<18 or min(len(s),len(t))/max(len(s),len(t))<.8:continue
            if shared/max(1,min(len(s),len(t))-2)<.48:continue
            comparisons+=1
            if difflib.SequenceMatcher(None,s,t,autojunk=False).ratio()>=.90:
                join(i,j);near_merges+=1
        for gram in grams:inverted[gram].append(i)
    members=collections.defaultdict(list)
    for i,r in enumerate(records):
        if r['normalized']:members[find(i)].append(i)
    for group in members.values():
        identity=min(records[i]['normalized'] for i in group);gid=hashlib.sha256(identity.encode()).hexdigest()[:20]
        for i in group:records[i]['content_group']=gid
    for r in records:
        r.setdefault('content_group','empty-'+r['id']);r.pop('normalized')
    # Known visibly damaged samples are retained as source data but not selected.
    blocked={'2015-02-23','2022-02-15','2022-05-16','2022-08-16','2022-11-18','2024-01-03','2024-03-10','2024-12-20','2025-12-06'}
    for r in records:
        if r['id'] in blocked:r['eligible']=False;r['quality']='known_text_review_needed'
    output=dict(schema=1,owner='TR2E',record_count=len(records),eligible_count=sum(r['eligible'] for r in records),dedup={'normalization':'NFKC + alphanumeric; exact + conservative character similarity >= 0.90 for length >= 18','groups':len(members),'near_merges':near_merges,'candidate_comparisons':comparisons,'note':'Cannot guarantee detection of every paraphrase or severe OCR variant; reviewed overrides may extend groups.'},
      source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},records=records)
    payload=json.dumps(output,ensure_ascii=False,separators=(',',':'))+'\n'
    (ROOT/'assets/catalog.json').write_text(payload)
    print(json.dumps({k:v for k,v in output.items() if k not in ('records','source_hashes')},ensure_ascii=False))

if __name__=='__main__':main()
