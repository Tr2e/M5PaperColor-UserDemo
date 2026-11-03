# -*- coding: utf-8 -*-
"""Explore title/date association; leave source records unchanged."""
import collections,datetime as dt,json,re
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'title_date_analysis';RNG=np.random.default_rng(20261103)
raw=[json.loads(l) for p in sorted((ROOT/'months').glob('*.jsonl')) for l in p.read_text().splitlines()]
valid=[r for r in raw if r['status']=='indexed' and r.get('date_verification')!='visually_checked_mismatch']
rows=[r for r in valid if r.get('title_kind') in ('宜','忌') and r.get('title')]
calendar={r['date']:r for r in json.loads((OUT/'calendar_reference.json').read_text())['days']}
dates=[dt.date.fromisoformat(r['date']) for r in rows];years=np.array([d.year for d in dates]);yi=np.array([r['title_kind']=='宜' for r in rows],dtype=int);groups=[np.flatnonzero(years==y) for y in np.unique(years)]
def table(codes,values=yi):
 return [{'group':int(g),'n':int((codes==g).sum()),'yi':int(values[codes==g].sum()),'yi_pct':round(float(values[codes==g].mean()*100),2)} for g in np.unique(codes)]
def statistic(codes,values):
 n=np.bincount(codes);yes=np.bincount(codes,weights=values);p=values.mean();return float(np.sum((yes-n*p)**2/(n*p*(1-p))))
def assoc(codes,perms=5000):
 _,codes=np.unique(codes,return_inverse=True);obs=statistic(codes,yi);ge=0
 for _ in range(perms):
  a=yi.copy()
  for ix in groups:a[ix]=RNG.permutation(a[ix])
  ge+=statistic(codes,a)>=obs-1e-10
 return {'chi_square':round(obs,4),'cramers_v':round((obs/len(yi))**.5,4),'year_stratified_permutation_p':(ge+1)/(perms+1),'permutations':perms}
weekday=np.array([d.weekday() for d in dates]);month=np.array([d.month for d in dates]);dom=np.array([d.day for d in dates]);lunar=np.array([calendar[r['date']]['lunar_day'] for r in rows])
result={'counts':{'all_dates':len(raw),'missing':sum(r['status']!='indexed' for r in raw),'excluded_known_date_mismatches':sum(r.get('date_verification')=='visually_checked_mismatch' for r in raw),'eligible_pages':len(valid),'normal_titles':len(rows),'excluded_other_layouts':len(valid)-len(rows)},'year':table(years),'weekday':table(weekday),'month':table(month),'weekday_test':assoc(weekday),'month_test':assoc(month),'day_of_month_test':assoc(dom),'lunar_day_test':assoc(lunar),'weekend':table((weekday>=5).astype(int))}
print('BASIC',json.dumps(result,ensure_ascii=False),flush=True)
# Consecutive dates only; do not bridge missing dates, Q&A pages or years.
pairs=[(i-1,i) for i in range(1,len(rows)) if (dates[i]-dates[i-1]).days==1 and dates[i].year==dates[i-1].year]
ii=np.array([x for x,y in pairs]);jj=np.array([y for x,y in pairs]);obs=int((yi[ii]!=yi[jj]).sum());null=[]
for _ in range(5000):
 a=yi.copy()
 for ix in groups:a[ix]=RNG.permutation(a[ix])
 null.append(int((a[ii]!=a[jj]).sum()))
result['adjacency']={'pairs':len(pairs),'alternating':obs,'alternating_pct':round(obs/len(pairs)*100,2),'null_expected_pct':round(float(np.mean(null))/len(pairs)*100,2),'permutation_p':(1+sum(x>=obs for x in null))/5001,'transitions':dict(collections.Counter(rows[x]['title_kind']+'→'+rows[y]['title_kind'] for x,y in pairs))}
# Same Gregorian month/day across years: exact title reuse, not semantic similarity.
mds=collections.defaultdict(list)
for i,d in enumerate(dates):mds[d.strftime('%m-%d')].append(i)
pairs2=[(ix[a],ix[b]) for ix in mds.values() for a in range(len(ix)) for b in range(a+1,len(ix))];i2=np.array([a for a,b in pairs2]);j2=np.array([b for a,b in pairs2]);_,titles=np.unique([r['title'] for r in rows],return_inverse=True);observed=int((titles[i2]==titles[j2]).sum());null=[]
for _ in range(2000):
 a=titles.copy()
 for ix in groups:a[ix]=RNG.permutation(a[ix])
 null.append(int((a[i2]==a[j2]).sum()))
result['same_month_day']={'cross_year_pairs':len(pairs2),'same_title_pairs':observed,'rate_pct':round(observed/len(pairs2)*100,3),'random_expected_pairs':round(float(np.mean(null)),3),'permutation_p':(1+sum(x>=observed for x in null))/2001,'examples':[{'a':rows[a]['date'],'b':rows[b]['date'],'title':rows[a]['title']} for a,b in pairs2 if titles[a]==titles[b]]}
events=collections.defaultdict(list)
fixed={'01-01':'元旦','02-14':'情人节','03-08':'妇女节','04-01':'愚人节','04-23':'世界读书日','05-01':'劳动节','06-01':'儿童节','10-01':'国庆节','12-24':'平安夜','12-25':'圣诞节','12-31':'跨年'}
fixed['12-01']='世界艾滋病日'
lunar_events={('正月','初一'):'春节',('正月','十五'):'元宵节',('五月','初五'):'端午节',('七月','初七'):'七夕',('八月','十五'):'中秋节',('九月','初九'):'重阳节'}
for r in valid:
 c=calendar[r['date']];tags=[];md=r['date'][5:]
 if md in fixed:tags.append(fixed[md])
 if (c['lunar_month'],c['lunar_day']) in lunar_events:tags.append(lunar_events[(c['lunar_month'],c['lunar_day'])])
 if c['solar_term']:tags.append(c['solar_term'])
 tomorrow=calendar.get(str(dt.date.fromisoformat(r['date'])+dt.timedelta(days=1)),{})
 if (tomorrow.get('lunar_month'),tomorrow.get('lunar_day'))==('正月','初一'):tags.append('除夕')
 for tag in tags:events[tag].append({k:r.get(k) for k in ('date','title','title_kind','author','source','url')})
result['events']=dict(events)
# Transparent exploratory keyword counts. These are not full semantic labels.
wordsets={'阅读':r'书|读','春':r'春','夏':r'夏|暑|纳凉','秋':r'秋','冬':r'冬|雪','休息':r'休息|休假|偷懒|睡|赖床|放空|不劳动','出行':r'出行|远行|上路|旅行|踏秋|出游'}
result['keywords']={}
for label,pat in wordsets.items():
 hit=np.array([bool(re.search(pat,r['title'])) for r in rows]);result['keywords'][label]={'pattern':pat,'n':int(hit.sum()),'by_month':{str(m):{'hits':int(hit[month==m].sum()),'total':int((month==m).sum())} for m in range(1,13)},'weekend_hits':int(hit[weekday>=5].sum()),'weekday_hits':int(hit[weekday<5].sum()),'examples':[{'date':r['date'],'title':r['title']} for r,h in zip(rows,hit) if h]}
result['reading_day']={'event_hits':sum(bool(re.search(wordsets['阅读'],r.get('title') or '')) for r in events['世界读书日']),'event_n':sum(bool(r.get('title')) for r in events['世界读书日']),'all_hits':result['keywords']['阅读']['n'],'all_n':len(rows)}
(OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('ADJACENCY',result['adjacency']);print('REUSE',{k:v for k,v in result['same_month_day'].items() if k!='examples'});print('READING',result['reading_day'])
for name in ['春节','除夕','元宵节','七夕','中秋节','清明','立春','夏至','冬至']:
 print(name,[(r['date'],r['title']) for r in events[name]])
print('SEASONS',{k:v['by_month'] for k,v in result['keywords'].items() if k in ['春','夏','秋','冬']})
