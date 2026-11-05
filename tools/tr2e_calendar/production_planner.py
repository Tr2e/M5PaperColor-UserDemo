"""Offline editorial planning for the deployed 2026..2099 resource.

2026 and 2027 are frozen approvals. Later years use the reviewed pair metadata,
phased occasions and rolling history. Untagged legacy entries are not claimed
to have received the 2027 manual semantic review.
"""
import collections,datetime as dt,functools,hashlib,json,re,sys,unicodedata
from pathlib import Path
from calendar_data import Calendar
from planner import load_inputs
from production_layout import layout

ROOT=Path(__file__).resolve().parent;REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO/'research/owspace-calendar'))
from content_analysis_author_dates import AUTHORS
norm=lambda s:''.join(c for c in unicodedata.normalize('NFKC',s).lower() if c.isalnum())
ALIASES={norm(s):norm(a['name']) for a in AUTHORS for s in a['aliases']}
ALIASES[norm('幾米')]=norm('几米')
BIO={norm(a['name']):a for a in AUTHORS}
FROZEN={2026:REPO/'artifacts/tr2e_calendar_400x600/2026.json',2027:REPO/'artifacts/tr2e_calendar_2027_editorial_v2_1/2027.json'}
THEMES={'love':'亲密与欣赏','family':'相伴与体谅','women':'自我与边界','rest':'松弛与日常','reading':'阅读与表达','memory':'阅读与表达','childhood':'感官与自然','renewal':'行动与希望','journey':'感官与自然','spring':'感官与自然','summer':'感官与自然','autumn':'感官与自然','winter':'感官与自然'}
LUNAR={(12,8):'腊八',(1,1):'春节',(1,15):'元宵节',(5,5):'端午节',(7,7):'七夕',(8,15):'中秋节',(9,9):'重阳节'}
FIXED={'01-01':'元旦','02-14':'情人节','03-08':'妇女节','04-22':'地球日','04-23':'读书日','05-01':'劳动节','06-01':'儿童节','10-01':'国庆节','12-25':'圣诞'}

def read(p):return json.loads(p.read_text())
def author(r):return ALIASES.get(norm(r['author']),norm(r['author']))

def input_key():
    paths=[ROOT/'production_planner.py',ROOT/'production_layout.py',ROOT/'build_device_pack.py',ROOT/'assets/catalog.json',ROOT/'personal_rules.json',ROOT/'editorial_v2/curation.json',ROOT/'editorial_v2/rules_2027.json',REPO/'research/owspace-calendar/content_analysis_author_dates.py',*FROZEN.values()]
    return hashlib.sha256(b''.join(p.read_bytes() for p in paths)).hexdigest()

@functools.lru_cache(None)
def inputs():
    catalog,personal,_=load_inputs();curation=read(ROOT/'editorial_v2/curation.json');rules=read(ROOT/'editorial_v2/rules_2027.json')
    reviewed={x['record_id']:x for x in curation['reviewed']};rejected={x['record_id'] for x in curation['rejected']}
    records=[]
    for original in catalog['records']:
        if not original['eligible'] or original['id'] in rejected:continue
        if re.search(r'%0|灬|^[_ ]+[A-Z]|^[12][UL]',original['excerpt']):continue
        try:layout(original)
        except ValueError:continue
        r=dict(original);r['canonical_author']=author(r)
        r['editorial']=reviewed.get(r['id'],dict(theme=next((THEMES[t] for t in r['tags'] if t in THEMES),'自我与边界'),tone='未细分',context_flags=[],seasons=[],relation='原配保留',review='沿用旧库标签；未纳入2027人工通读批次'))
        r['manually_reviewed']=r['id'] in reviewed
        records.append(r)
    return records,personal,rules,reviewed

@functools.lru_cache(None)
def pools():
    records,personal,rules,reviewed=inputs();by={r['id']:r for r in records}
    def safe(r):return not(set(r['editorial']['context_flags'])-{'成人亲密'})
    themes=lambda *names:[r['id'] for r in records if r['manually_reviewed'] and safe(r) and r['editorial']['theme'] in names]
    warm=['2024-01-01','2019-01-02','2023-03-02','2023-02-16','2025-07-01','2020-08-28','2021-01-02','2025-01-06','2019-03-06','2024-01-04','2025-05-13','2021-01-25','2023-12-15','2020-05-03']
    family=personal['lunar_new_year']['pool'][:8]+['2023-01-14','2023-01-23','2025-06-17','2020-11-08','2023-09-18','2017-02-02','2023-10-26','2025-11-15']
    result={e['id']:e['pool'][:] for e in personal['events']}
    result['wife_birthday']+=['2019-04-09','2024-03-09','2023-03-02']
    result['son_birthday']+=['2024-09-23','2025-06-01','2019-06-01']
    result['wedding_anniversary']+=['2023-06-23','2023-12-30','2021-02-16']
    result.update({'迎新':warm,'元旦':warm,'回望':['2023-08-29','2025-06-25','2019-12-20','2021-10-09','2023-02-24','2025-09-19','2023-06-27'],
                   '宽慰':['2025-01-06','2023-03-02','2024-01-04','2019-07-07','2021-01-25','2024-12-16','2023-08-31'],
                   '期待':['2020-08-28','2025-07-01','2023-02-16','2021-01-02','2020-05-03','2023-12-15'],
                   '归家':family,'团聚':family,'春节':family+warm,'除夕':family+['2023-01-21'],
                   '节后舒展':themes('松弛与日常'),'节后启程':warm,
                   '腊八':['2018-01-24']+family,'元宵节':personal['lunar_festival_pools']['元宵节']+['2023-09-29'],
                   '端午节':personal['lunar_festival_pools']['端午节']+['2018-06-18','2023-06-22'],
                   '七夕':personal['lunar_festival_pools']['七夕']+themes('亲密与欣赏'),
                   '中秋节':personal['lunar_festival_pools']['中秋节']+['2023-09-29','2018-08-20','2018-11-25'],
                   '重阳节':personal['lunar_festival_pools']['重阳节']+['2021-10-14','2025-09-18','2019-03-06'],
                   '母亲节':family,'情人节':themes('亲密与欣赏'),'妇女节':['2023-03-08','2020-09-16','2020-08-03'],
                   '地球日':['2023-04-22','2025-06-04','2024-06-14','2024-02-02','2024-07-25'],
                   '读书日':themes('阅读与表达'),'劳动节':themes('松弛与日常'),
                   '儿童节':result['son_birthday']+['2025-06-01','2023-03-05'],
                   '国庆节':['2019-06-04','2023-08-18','2025-08-28','2020-09-19','2024-06-05'],
                   '圣诞':['2023-12-25']+family,
                   '清明':['2023-04-05','2024-04-04','2020-04-04','2021-02-06','2020-01-28'],
                   '立春':['2023-02-04','2023-03-05','2019-03-06','2024-07-25'],
                   '冬至':['2024-12-16','2018-01-24','2021-12-21','2020-11-08']})
    result['祝福邻日']=themes('相伴与体谅','松弛与日常','行动与希望','感官与自然','自我与边界')
    return {k:list(dict.fromkeys(x for x in v if x in by)) for k,v in result.items()}

def calendar_days(year):
    cal=Calendar();days=cal.year(year)
    for day in days:
        tomorrow=cal.day(dt.date.fromisoformat(day['date'])+dt.timedelta(days=1))
        day['is_lunar_new_year_eve']=not tomorrow['leap_month'] and (tomorrow['lunar_month'],tomorrow['lunar_day'])==(1,1)
    return days

def events_for(year,days=None):
    days=days or calendar_days(year);cny=next(dt.date.fromisoformat(d['date']) for d in days if not d['leap_month'] and (d['lunar_month'],d['lunar_day'])==(1,1))
    mothers=[d['date'] for d in days if d['date'][5:7]=='05' and d['weekday']==6][1]
    wedding=next(d['date'] for d in days if d['solar_term']=='夏至')
    result={}
    for d in days:
        date=d['date'];md=date[5:];distance=(dt.date.fromisoformat(date)-cny).days
        lunar=LUNAR.get((d['lunar_month'],d['lunar_day']),'') if not d['leap_month'] else ''
        label='除夕' if d['is_lunar_new_year_eve'] else lunar or ('母亲节' if date==mothers else FIXED.get(md,''))
        term=d['solar_term'] or '';display='·'.join(dict.fromkeys(s for s in [label,term] if s))
        event=label or (term if term in pools() else 'ordinary');priority=80 if label else 55 if event!='ordinary' else 0
        personal=md in ('05-08','11-11') or date==wedding
        if personal:
            event='wife_birthday' if md=='05-08' else 'son_birthday' if md=='11-11' else 'wedding_anniversary'
            display=term;priority=1000
        elif d['is_lunar_new_year_eve']:event='除夕';priority=95
        elif label:pass
        elif -4<=distance<=-2:event='归家';priority=90
        elif 1<=distance<=3:event='团聚';priority=90
        elif 4<=distance<=5:event='节后舒展';priority=85
        elif distance==6:event='节后启程';priority=85
        elif md in ('01-02','01-03'):event='迎新';priority=90
        elif md=='12-27':event='回望';priority=90
        elif md=='12-28':event='宽慰';priority=90
        elif md=='12-29':event='回望';priority=90
        elif md in ('12-30','12-31'):event='期待';priority=90
        # Celebratory windows are context checks, not forced positive sentiment.
        near=lambda value:abs((dt.date.fromisoformat(date)-dt.date.fromisoformat(value)).days)<=1
        warm=('01-01'<=md<='01-03' or '12-27'<=md<='12-31' or -4<=distance<=9 or any(near(value) for value in [f'{year}-05-08',f'{year}-06-01',wedding,f'{year}-11-11',f'{year}-02-14']))
        child=near(f'{year}-06-01') or near(f'{year}-11-11')
        if warm and event not in pools():event='祝福邻日';priority=60
        result[date]=dict(id=event,display_label=display,personal=personal,priority=priority,warm=warm,child=child,pool=pools().get(event))
    return result

def context_fits(r,event):
    flags=set(r['editorial']['context_flags'])
    # Warm/child windows only use semantically reviewed material or explicit
    # legacy occasion pools, never an unreviewed word match masquerading as it.
    if event['warm'] and flags-{'成人亲密'}:return False
    if event['child'] and '成人亲密' in flags:return False
    return True

def plan_year(year,history):
    if year in FROZEN:return read(FROZEN[year])
    records,personal,rules,reviewed=inputs();by={r['id']:r for r in records};days=calendar_days(year);events=events_for(year,days)
    last_g={};last_t={}
    for plan in history:
        for d in plan['days']:last_g[d['content_group']]=plan['year'];last_t[d['title_key']]=plan['year']
    previous_g={d['content_group'] for d in history[-1]['days']} if history else set()
    previous_t={d['title_key'] for d in history[-1]['days']} if history else set()
    used_g=set();used_t=set();chosen={};authors=collections.Counter();positions=collections.defaultdict(list);repeat=0
    ords={d['date']:dt.date.fromisoformat(d['date']).toordinal() for d in days}
    def eligible(r,d,e):
        if r['content_group'] in used_g or r['title_key'] in used_t or authors[r['canonical_author']]>=5:return False
        if not context_fits(r,e):return False
        if not e['pool']:
            if year-last_g.get(r['content_group'],-100)<=5 or year-last_t.get(r['title_key'],-100)<=2:return False
            if (e['warm'] or e['child']) and not r['manually_reviewed']:return False
            season='冬' if int(d['date'][5:7]) in (12,1,2) else '春' if int(d['date'][5:7])<=5 else '夏' if int(d['date'][5:7])<=8 else '秋'
            if r['editorial']['seasons'] and season not in r['editorial']['seasons']:return False
        return not(r['content_group'] in previous_g and repeat>=18)
    def score(r,d,e):
        m=r['editorial'];date=d['date'];key=r['canonical_author'];n=ords[date]
        value=int(hashlib.sha256(f'editorial-production-v3|{date}|{r["id"]}'.encode()).hexdigest()[:8],16)/2**32*15
        value+=6 if m['theme'] in rules['monthly_lenses'][str(int(date[5:7]))] else 0
        value+=4 if r['manually_reviewed'] else 0
        value-=9*authors[key]
        value-=90*sum(abs(n-o)<=21 for o in positions[key])
        for offset in (-3,-2,-1,1,2,3):
            other=chosen.get(n+offset)
            if other:
                value-= (14 if abs(offset)==1 else 5) if m['theme']==other['editorial']['theme'] else 0
                value-=40 if abs(offset)==1 and m['tone']==other['editorial']['tone']=='沉思' else 0
        biography=BIO.get(key)
        if biography and r['manually_reviewed'] and not(e['warm'] or e['child']) and context_fits(r,e):
            value+=22 if biography['birth'] and biography['birth'][5:]==date[5:] else 0
            value+=12 if biography['death'] and biography['death'][5:]==date[5:] else 0
        # The rare pool is selected by least-recent use before stylistic score.
        return ((-last_g.get(r['content_group'],-100),-last_t.get(r['title_key'],-100),value,r['id']) if e['pool'] else (value,-last_g.get(r['content_group'],-100),r['id']))
    assigned={}
    for d in sorted(days,key=lambda d:(-events[d['date']]['priority'],d['date'])):
        e=events[d['date']]
        candidates=[by[x] for x in e['pool']] if e['pool'] else records
        options=[r for r in candidates if eligible(r,d,e)]
        if not options:raise ValueError(f'No unique contextual candidate on {d["date"]}: {e["id"]}')
        r=max(options,key=lambda r:score(r,d,e));key=r['canonical_author'];n=ords[d['date']]
        used_g.add(r['content_group']);used_t.add(r['title_key']);authors[key]+=1;positions[key].append(n);chosen[n]=r
        repeat+=r['content_group'] in previous_g
        assigned[d['date']]=dict(d,record_id=r['id'],content_group=r['content_group'],title_key=r['title_key'],display_label=e['display_label'],personal=e['personal'],event_id=e['id'],theme=r['editorial']['theme'],review=r['editorial']['review'])
    assert len(used_g)==len(used_t)==len(days) and repeat<=18
    return dict(schema=3,year=year,input_version=input_key(),days=[assigned[d['date']] for d in days],unique_content_groups=len(used_g),unique_titles=len(used_t),note='Frozen offline allocation; reviewed pair metadata plus explicitly marked legacy tags. No forced 宜 quota. Ordinary groups cool down 5 years; titles 2 years; scarce occasions rotate by least recent use.')
