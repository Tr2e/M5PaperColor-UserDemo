"""Analyze existing excerpts and credits without changing monthly source data."""
import collections
import hashlib
import json
import re
from pathlib import Path
import numpy as np
from content_analysis_author_dates import AUTHORS, SPECIAL_DATES

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'content_logic_analysis'
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(20261103)
files = sorted((ROOT/'months').glob('*.jsonl'))
raw = [json.loads(line) for p in files for line in p.read_text().splitlines()]
valid = [r for r in raw if r['status']=='indexed' and r.get('date_verification')!='visually_checked_mismatch']
rows = [r for r in valid if r.get('title_kind') in ('宜','忌') and r.get('title') and r.get('excerpt')]
norm = lambda text: re.sub(r'[^\w]', '', text or '')
compact = lambda r: {k:r.get(k) for k in ('date','title','author','source','url')}
result = dict(counts=dict(all_dates=len(raw), eligible_pages=len(valid), title_excerpt_pairs=len(rows),
                         distinct_author_strings=len({r['author'] for r in valid if r.get('author')})),
              source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files})

# Exact contiguous characters are a reproducible lexical indicator, not semantics.
bodies = [norm(r['title'][1:]) for r in rows]
excerpts = [norm(r['excerpt']) for r in rows]
grams = [{s[i:i+2] for i in range(len(s)-1)} for s in bodies]
exgrams = [{s[i:i+2] for i in range(len(s)-1)} for s in excerpts]
years = np.array([int(r['date'][:4]) for r in rows])
groups = [np.flatnonzero(years==y) for y in np.unique(years)]
exact = np.array([bool(s) and s in e for s,e in zip(bodies,excerpts)])
overlap = np.array([bool(a&b) for a,b in zip(grams,exgrams)])
null_exact = []; null_overlap = []
for _ in range(1000):
    ix = np.arange(len(rows))
    for g in groups: ix[g] = rng.permutation(ix[g])
    null_exact.append(sum(bool(s) and s in excerpts[j] for s,j in zip(bodies,ix)))
    null_overlap.append(sum(bool(s & exgrams[j]) for s,j in zip(grams,ix)))
result['lexical'] = dict(exact_body_in_excerpt=int(exact.sum()), shared_two_character_sequence=int(overlap.sum()),
                        shuffled_exact_mean=round(float(np.mean(null_exact)),3), shuffled_overlap_mean=round(float(np.mean(null_overlap)),3),
                        permutations=1000, seed=20261103,
                        by_year=[dict(year=int(y),n=int((years==y).sum()),exact=int(exact[years==y].sum()),overlap=int(overlap[years==y].sum())) for y in np.unique(years)])

# Existing excerpt equality only; does not imply equality of the entire printed passage.
dups = collections.defaultdict(list)
for r in rows:
    if len(norm(r['excerpt']))>8: dups[norm(r['excerpt'])].append(r)
repeated = [rs for rs in dups.values() if len(rs)>1]
result['repeated_excerpts'] = dict(groups=len(repeated), records=sum(map(len,repeated)),
    changed_title_groups=sum(len({r['title'] for r in rs})>1 for rs in repeated),
    changed_polarity_groups=sum(len({r['title_kind'] for r in rs})>1 for rs in repeated),
    details=[dict(records=[compact(r) for r in rs],excerpt=rs[0]['excerpt']) for rs in repeated])

# Date recurrence on the full corpus, exact original author strings, before biography selection.
credited = [r for r in valid if r.get('author')]
md = collections.defaultdict(list)
for i,r in enumerate(credited): md[r['date'][5:]].append(i)
pairs=[(g[a],g[b]) for g in md.values() for a in range(len(g)) for b in range(a+1,len(g))]
ii=np.array([a for a,b in pairs]); jj=np.array([b for a,b in pairs])
_,ids=np.unique([r['author'] for r in credited],return_inverse=True)
yy=np.array([r['date'][:4] for r in credited]); gg=[np.flatnonzero(yy==y) for y in np.unique(yy)]
obs=int((ids[ii]==ids[jj]).sum()); null=[]
for _ in range(2000):
    a=ids.copy()
    for g in gg:a[g]=rng.permutation(a[g])
    null.append(int((a[ii]==a[jj]).sum()))
recurrence=collections.defaultdict(list)
for r in credited:recurrence[(r['author'],r['date'][5:])].append(r)
result['author_recurrence'] = dict(credited_pages=len(credited),cross_year_pairs=len(pairs),same_author_pairs=obs,
    shuffled_mean=round(float(np.mean(null)),3),permutations=2000,permutation_p=(1+sum(x>=obs for x in null))/2001,
    groups=[dict(author=a,md=d,records=[compact(r) for r in rs]) for (a,d),rs in sorted(recurrence.items(),key=lambda item:(-len(item[1]),item[0])) if len(rs)>1])

# Curated identities: all occurrences are scanned, but identities were selected purposefully.
alias = {s:a for a in AUTHORS for s in a['aliases']}
matches=[]; special=[]; covered=[]
for r in valid:
    a=alias.get(r.get('author'))
    if not a:continue
    covered.append(r)
    for kind in ('birth','death'):
        event=a[kind]
        if event and r['date'][5:]==event[5:] and r['date']>event:
            matches.append(dict(**compact(r),identity=a['name'],kind=kind,event_date=event,anniversary=int(r['date'][:4])-int(event[:4])))
    for s in SPECIAL_DATES:
        if s['name']==a['name'] and s['md']==r['date'][5:]:special.append(dict(**compact(r),identity=a['name'],kind=s['kind'],evidence=s['source']))
result['author_dates'] = dict(checked_identities=len(AUTHORS),covered_pages=len(covered),
    strict_matched_pages=len({r['date'] for r in matches}),birth_pages=sum(r['kind']=='birth' for r in matches),
    death_pages=sum(r['kind']=='death' for r in matches),matches=matches,special_memorial_dates=special,
    identities=AUTHORS,by_year=[dict(year=y,covered=sum(r['date'].startswith(str(y)) for r in covered),matched=sum(r['date'].startswith(str(y)) for r in matches)) for y in range(2015,2026)])

# Fixed, non-random 44-page reading sample: midpoint valid record of four months/year.
# Categories are model readings, not human gold labels or population prevalence estimates.
labels = [
 ('待核对','标题“冠开”疑似 OCR 错误，暂不作语义归类。'),
 ('修辞回应','用书名式群体标签回应群体的非理性，带反讽色彩。'),
 ('情绪概括','把离别时意识到爱情的心情概括为怦然心动。'),
 ('修辞回应','点出美德受阻、恶习得运的反讽结构。'),
 ('场景化改写','把天气渐暖与生活渐有意味写成放晴。'),
 ('情绪概括','把黑白和彩色之间的爱与朝圣概括为迷情。'),
 ('场景化改写','把天空、风和眼泪的意象转为哭泣的许可。'),
 ('场景化改写','把漫长无事可做的下午转成发呆的建议。'),
 ('情绪概括','把不依赖恋爱也能快乐概括为怡然自得。'),
 ('反向提醒','选句倡导改变，标题告诫不要被动等待。'),
 ('反向提醒','选句否定绝对断言，标题压缩为忌绝对。'),
 ('直接提词','选句重复“写诗”，标题直接抽取行动。'),
 ('场景化改写','除夕不眠的古诗，被转接到当代抢红包的生活场景。'),
 ('反向提醒','选句恳求爱人留下，标题反向禁止诀别。'),
 ('反向提醒','选句强调自由的代价，标题禁止不劳而获。'),
 ('反向提醒','把吃亏与占便宜的对比转成戒贪提醒。'),
 ('情绪概括','名字与经历不足以说明人的本质，标题概括为深不可测。'),
 ('场景化改写','把灵魂与负重的比喻转为日常放轻松的提示。'),
 ('场景化改写','把观看影像与发现自己的论述转成看展建议。'),
 ('场景化改写','把与猫建立信任的描述转为网络用语“吸猫”。'),
 ('情绪概括','把相信行动与生命需要力量的论述概括为坚强。'),
 ('情绪概括','把街道激发拍摄的瞬间概括为灵光乍现。'),
 ('反向提醒','通过家庭与自选知己的对比，引出关系不应绑架人的解读。'),
 ('直接提词','把在地板上来回滚动的身体动作改写为辗转反侧。'),
 ('修辞回应','选句表达求而不得的爱，标题以“忌自怜”回应，而非照搬说话者情绪。'),
 ('反向提醒','把加快脚步躲开霉气事的描写转成避免晦气的提示。'),
 ('情绪概括','把每代人寻找自身命题概括为自省。'),
 ('直接提词','选句围绕空与填满，标题抽取“空”的意象。'),
 ('待核对','选句“孩于、骨山”等字样损坏，暂不作语义归类。'),
 ('待核对','选句“越杀近、越深发”疑似严重 OCR 错误，暂不判断。'),
 ('待核对','选句多处文字损坏；不能凭作者或题名补写选句。'),
 ('反向提醒','选句描写压抑情感的代价，宜释放是对其困境的回应。'),
 ('情绪概括','反复写爱你的日记，被概括为情话连篇。'),
 ('反向提醒','选句将说谎联系到害怕失去，标题提醒珍视关系。'),
 ('修辞回应','以恶趣味评价榴莲与厕所、冰激凌的夸张比喻。'),
 ('修辞回应','困境中渴望光和奇迹，标题作主动、逆向的赞美式回应。'),
 ('反向提醒','选句以雷鸟归来反衬人的失约，标题提醒勿轻信。'),
 ('情绪概括','把心是否跳动比地位财富重要概括为做情感动物。'),
 ('直接提词','从不要考虑跳舞的意义提取停止思考的行动指令。'),
 ('情绪概括','把走向担当的叙述概括为看清使命。'),
 ('反向提醒','用谁能说明时间的反问，引出不要擅自定义的解读。'),
 ('修辞回应','把浪漫需要希望的论断强化为“浪漫至死”。'),
 ('反向提醒','选句否定无始无终宇宙的人造尺度，标题概括为忌衡量永恒。'),
 ('反向提醒','选句赞赏变化与差异，标题反向禁止一成不变。'),
]
sample=[]
for year in range(2015,2026):
    for month in (2,5,8,11):
        rr=[r for r in rows if r['date'].startswith(f'{year}-{month:02}')]
        sample.append(rr[len(rr)//2])
assert len(sample)==len(labels)==44
result['semantic_sample']=dict(method='每年 2、5、8、11 月有效标题与摘录记录的中间一条；非随机样本；模型逐条判读；允许类别边界重叠，记录主要关系。',
    counts=dict(collections.Counter(k for k,n in labels)),records=[dict(**compact(r),excerpt=r['excerpt'],relation=k,reason=n) for r,(k,n) in zip(sample,labels)])
(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:({kk:vv for kk,vv in v.items() if kk not in ('details','groups','identities','matches','special_memorial_dates','records')} if isinstance(v,dict) else v) for k,v in result.items() if k!='source_hashes'},ensure_ascii=False,indent=2))
