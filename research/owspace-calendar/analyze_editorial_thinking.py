"""Reproducible, exploratory editorial research; never changes source records.

Run with Python + NumPy. Uses only checked-in text/calendar/biography evidence.
Lexical flags measure words, not sentiment or an editor's private intention.
"""
import collections,datetime as dt,hashlib,json,re,sys
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'editorial_thinking';OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT.parents[1]/'tools/tr2e_calendar'))
from calendar_data import Calendar
from content_analysis_author_dates import AUTHORS

SEED=20261105;PERMS=2000
LEX={
 '更新与时间':['新年','明天','未来','开始','重新','告别','回首','过去','一年','新生','希望','翻页','迎新'],
 '亲密与家庭':['爱人','爱情','恋人','相爱','亲吻','拥抱','母亲','父亲','家人','故乡','团圆','团聚','思念','想念'],
 '休息与节奏':['休息','睡觉','睡眠','偷懒','懒惰','疲倦','疲惫','慢慢','缓慢','从容','放松','放空'],
 '孤独与自我':['孤独','独处','寂寞','自己','自我','自由','独立'],
 '阅读与表达':['读书','阅读','写作','诗歌','诗人','文字','书籍','表达','语言'],
 '自然与季节':['春天','夏天','秋天','冬天','阳光','月亮','落叶','雪花','花朵','树林','大海','星星'],
 '痛苦与困境':['痛苦','悲伤','绝望','恐惧','失败','失望','死亡','忧伤','伤心','苦难'],
 '行动与好奇':['行动','出发','旅行','冒险','勇敢','勇气','好奇','探索','尝试','创造'],
}
norm=lambda t:re.sub(r'[^\w]','',t or '')
def brief(r):return {k:r.get(k) for k in ('date','title','title_kind','excerpt','author','source','author_roles','url')}
def perm_result(obs,null,tail='two'):
 null=np.array(null);lo=(1+int((null<=obs+1e-12).sum()))/(len(null)+1);hi=(1+int((null>=obs-1e-12).sum()))/(len(null)+1)
 return dict(observed=float(obs),null_mean=float(null.mean()),null_95_interval=[float(x) for x in np.quantile(null,[.025,.975])],p=min(1,2*min(lo,hi)) if tail=='two' else lo if tail=='lower' else hi,tail=tail)

def main():
 rng=np.random.default_rng(SEED);files=sorted((ROOT/'months').glob('*.jsonl'))
 raw=[json.loads(line) for p in files for line in p.read_text().splitlines()]
 valid=[r for r in raw if r['status']=='indexed' and r.get('date_verification')!='visually_checked_mismatch']
 rows=[r for r in valid if r.get('title_kind') in ('宜','忌') and r.get('excerpt') and r.get('title')]
 dates=[dt.date.fromisoformat(r['date']) for r in rows];ordinals=np.array([d.toordinal() for d in dates]);years=np.array([d.year for d in dates]);ym=np.array([r['date'][:7] for r in rows])
 yy=[np.flatnonzero(years==y) for y in sorted(set(years))];mm=[np.flatnonzero(ym==m) for m in sorted(set(ym))]
 cal=Calendar();lunar={r['date']:cal.day(r['date']) for r in valid}
 aliases={s:a['name'] for a in AUTHORS for s in a['aliases']}
 unknown={'佚名','无名氏','匿名','未知','不详',None,''}
 names=[f'__missing_{i}' if r.get('author') in unknown else aliases.get(r['author'],r['author']) for i,r in enumerate(rows)]
 _,aids=np.unique(names,return_inverse=True)
 text=[(r['title'] or '')+' '+r['excerpt'] for r in rows]
 flags=np.array([[any(word in t for word in words) for words in LEX.values()] for t in text],dtype=float)
 lengths=np.array([len(norm(r['excerpt'])) for r in rows]);yi=np.array([r['title_kind']=='宜' for r in rows])
 # Exact consecutive calendar days only; no bridging gaps or years.
 pairs=[(i-1,i) for i in range(1,len(rows)) if ordinals[i]-ordinals[i-1]==1 and years[i]==years[i-1]]
 ii,jj=np.array(pairs).T
 near=[(i,j) for i in range(len(rows)) for j in range(i+1,min(i+8,len(rows))) if years[i]==years[j] and 0<ordinals[j]-ordinals[i]<=7]
 i7,j7=np.array(near).T
 def rhythm(ix):
  f=flags[ix];inter=(f[ii]*f[jj]).sum(axis=1);union=((f[ii]+f[jj])>0).sum(axis=1)
  similarity=np.divide(inter,union,out=np.zeros_like(inter),where=union>0).mean()
  return np.array([(aids[ix[ii]]==aids[ix[jj]]).sum(),(aids[ix[i7]]==aids[ix[j7]]).sum(),similarity,np.abs(lengths[ix[ii]]-lengths[ix[jj]]).mean()])
 observed=rhythm(np.arange(len(rows)));null=[]
 for _ in range(PERMS):
  ix=np.arange(len(rows))
  for g in mm:ix[g]=rng.permutation(g)
  null.append(rhythm(ix))
 null=np.array(null)
 rhythm_tests={name:perm_result(observed[k],null[:,k]) for k,name in enumerate(['adjacent_same_author','within_7_days_same_author','adjacent_lexical_jaccard','adjacent_excerpt_length_difference'])}
 for name,v in rhythm_tests.items():v['comparison']='shuffle within each year-month; missing-date positions retained'
 # Predeclared transparent windows; examine tails and window width separately.
 cny={y:next(dt.date.fromisoformat(r['date']) for r in valid if int(r['date'][:4])==y and not lunar[r['date']]['leap_month'] and (lunar[r['date']]['lunar_month'],lunar[r['date']]['lunar_day'])==(1,1)) for y in range(2015,2026)}
 jan_distance=np.array([(d-dt.date(d.year,1,1)).days if d.month<=6 else (d-dt.date(d.year+1,1,1)).days for d in dates])
 cny_distance=np.array([(d-cny[d.year]).days for d in dates])
 probes=[('gregorian_new_year_3day',np.isin(jan_distance,[-1,0,1]),0),('gregorian_new_year_13day',(jan_distance>=-6)&(jan_distance<=6),0),('lunar_new_year_3day',np.isin(cny_distance,[-1,0,1]),1),('lunar_new_year_10day',(cny_distance>=-3)&(cny_distance<=6),1)]
 window_tests={};tests=[]
 for name,mask,col in probes:
  hits=flags[:,col];obs=hits[mask].mean()-hits[~mask].mean();sim=[]
  for _ in range(PERMS):
   copy=hits.copy()
   for g in yy:copy[g]=rng.permutation(copy[g])
   sim.append(copy[mask].mean()-copy[~mask].mean())
  result=perm_result(obs,sim,'upper');result.update(n=int(mask.sum()),hits=int(hits[mask].sum()),outside_n=int((~mask).sum()),outside_hits=int(hits[~mask].sum()),lexicon=list(LEX)[col],yi=int(yi[mask].sum()),records=[brief(r) for r,m in zip(rows,mask) if m]);window_tests[name]=result
 for family in (rhythm_tests,window_tests):
  ordered=sorted(family,key=lambda k:family[k]['p']);last=1
  for rank in range(len(ordered),0,-1):
   key=ordered[rank-1];last=min(last,family[key]['p']*len(ordered)/rank);family[key]['bh_q']=last
 curves={}
 for name,distance,col in [('公历年界',jan_distance,0),('春节',cny_distance,1)]:
  curves[name]=[dict(offset=k,n=int((distance==k).sum()),hits=int(flags[distance==k,col].sum()),yi=int(yi[distance==k].sum())) for k in range(-10,11)]
 music_words=['音乐','歌手','乐队','词作','作曲','原唱','摇滚','民谣','说唱']
 annual=[];repeat_details=[]
 for year in range(2015,2026):
  vv=[r for r in valid if r['date'].startswith(str(year))];rr=[r for r in rows if r['date'].startswith(str(year))]
  dupt=collections.defaultdict(list);dupe=collections.defaultdict(list)
  for r in rr:dupt[norm(r['title'])].append(r['date']);dupe[norm(r['excerpt'])].append(r['date'])
  matches=[]
  for r in vv:
   a=next((a for a in AUTHORS if r.get('author') in a['aliases']),None)
   if a and any(a[k] and a[k][5:]==r['date'][5:] for k in ('birth','death')):matches.append(r['date'])
  entry=dict(year=year,pages=len(vv),normal_pairs=len(rr),known_roles=sum(bool(r.get('author_roles')) for r in vv),music_role_pages=sum(any(w in role for w in music_words for role in r.get('author_roles',[])) for r in vv),question_pages=sum(r.get('title_kind')=='问答' for r in vv),yi=sum(r['title_kind']=='宜' for r in rr),excerpt_median=float(np.median([len(norm(r['excerpt'])) for r in rr])),title_median=float(np.median([len(norm(r['title'][1:])) for r in rr])),unique_credited_authors=len({aliases.get(r.get('author'),r.get('author')) for r in rr if r.get('author')}),matched_26_author_dates=len(matches),covered_26_author_pages=sum(r.get('author') in aliases for r in vv),repeat_title_groups=sum(len(v)>1 for v in dupt.values()),repeat_excerpt_groups=sum(len(v)>1 for v in dupe.values()))
  annual.append(entry)
  repeat_details += [dict(year=year,kind=kind,dates=v) for kind,dd in [('title',dupt),('excerpt',dupe)] for v in dd.values() if len(v)>1]
 # Separate fixed sample, drawn before semantic annotation. One page from
 # every two-month stratum in each year. 2015 Jan/Feb uses available Feb pages.
 sample_rng=np.random.default_rng(SEED);sample=[]
 for year in range(2015,2026):
  for start in (1,3,5,7,9,11):
   candidates=[r for r in rows if int(r['date'][:4])==year and start<=int(r['date'][5:7])<=start+1]
   sample.append(brief(candidates[int(sample_rng.integers(len(candidates)))]))
 qa=[r for r in valid if r.get('title_kind')=='问答'];qa_dates=[dt.date.fromisoformat(r['date']) for r in qa]
 result=dict(schema=1,analysis_date='2026-11-05',seed=SEED,permutations=PERMS,counts=dict(all_dates=len(raw),valid_pages=len(valid),normal_pairs=len(rows)),source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},lexicons=LEX,rhythm=dict(pairs=len(pairs),within_7_pairs=len(near),tests=rhythm_tests,adjacent_author_examples=[[rows[i]['date'],rows[j]['date'],names[i]] for i,j in pairs if aids[i]==aids[j]]),windows=window_tests,curves=curves,annual=annual,within_year_duplicates=repeat_details,question_layout=dict(count=len(qa),weekday_counts=dict(collections.Counter(d.weekday() for d in qa_dates)),gap_days=dict(collections.Counter((b-a).days for a,b in zip(qa_dates,qa_dates[1:])))),sample_design='One random normal-title/excerpt page per year and two-month stratum; seed 20261105; 66 records. Model coding is not independent human ground truth.',semantic_sample=sample)
 (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('counts','rhythm','annual','question_layout')},ensure_ascii=False,indent=2))
 print('WINDOWS',json.dumps({k:{a:b for a,b in v.items() if a!='records'} for k,v in window_tests.items()},ensure_ascii=False))

if __name__=='__main__':main()
