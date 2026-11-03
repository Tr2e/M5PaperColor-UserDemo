"""Deterministic offline annual content allocation. Standard library only.

Personal dates are reserved first. Content groups and complete titles are never
reused within a plan. Runtime performs no web access and never rewrites sources.
"""
import argparse,datetime as dt,hashlib,json
from pathlib import Path
from calendar_data import Calendar

ROOT=Path(__file__).resolve().parent
FIXED={'01-01':('元旦',['renewal']),'02-14':('情人节',['love']),'03-08':('妇女节',['women']),'04-23':('读书日',['reading']),'05-01':('劳动节',['rest']),'06-01':('儿童节',['childhood']),'10-01':('国庆节',['journey']),'12-31':('岁末',['memory','renewal'])}
LUNAR={(1,1):('春节',['family','renewal']),(1,15):('元宵节',['family','moon']),(5,5):('端午节',['family','journey']),(7,7):('七夕',['love']),(8,15):('中秋节',['moon','family']),(9,9):('重阳节',['family','memory'])}

def load_inputs():
    catalog_bytes=(ROOT/'assets/catalog.json').read_bytes();rules_bytes=(ROOT/'personal_rules.json').read_bytes()
    return json.loads(catalog_bytes),json.loads(rules_bytes),hashlib.sha256(catalog_bytes+rules_bytes).hexdigest()

def event_for(day,rules):
    md=day['date'][5:]
    for event in rules['events']:
        if event.get('month_day')==md or (event.get('solar_term') and event['solar_term']==day['solar_term']):
            return dict(event,personal=True,tags=[])
    lunar=(day['lunar_month'],day['lunar_day'])
    festival=LUNAR.get(lunar) if not day['leap_month'] else None
    if day.get('is_lunar_new_year_eve'):festival=('除夕',['family','renewal'])
    spring=rules['lunar_new_year']
    if not day['leap_month'] and ((lunar[0]==12 and lunar[1]>=spring['last_month_start_day']) or (lunar[0]==1 and lunar[1]<=spring['first_month_end_day'])):
        return dict(id='lunar_new_year_window',label=festival[0] if festival else '迎春',tags=['family','renewal'],priority=spring['priority'],personal=False,pool=spring['pool'],curation='lunar_new_year_curated_pool')
    boundary=rules['year_boundary']
    if md>=boundary['start'] or md<=boundary['end']:
        label=FIXED[md][0] if md in FIXED else '岁末' if md>=boundary['start'] else '迎新'
        return dict(id='year_boundary_window',label=label,tags=['renewal'],priority=boundary['priority'],personal=False,pool=boundary['pool'],curation='positive_year_boundary_curated_pool')
    if festival:
        label,tags=festival
        return dict(id=label,label=label,tags=tags,priority=85,personal=False,pool=rules['lunar_festival_pools'][label],curation='lunar_festival_curated_pool')
    if md in FIXED:
        label,tags=FIXED[md];return dict(id=md,label=label,tags=tags,priority=80,personal=False)
    if day['solar_term']:
        month=int(day['date'][5:7]);season='spring' if 2<=month<=4 else 'summer' if 5<=month<=7 else 'autumn' if 8<=month<=10 else 'winter'
        return dict(id=day['solar_term'],label=day['solar_term'],tags=[season],priority=50,personal=False)
    return dict(id='ordinary',label='',tags=[],priority=0,personal=False)

def plan_year(year,catalog=None,rules=None):
    loaded,personal,_=load_inputs();catalog=loaded if catalog is None else catalog;rules=personal if rules is None else rules
    version=hashlib.sha256(json.dumps([catalog,rules],ensure_ascii=False,sort_keys=True).encode()+Path(__file__).read_bytes()).hexdigest()
    calendar=Calendar();days=calendar.year(year);records=[r for r in catalog['records'] if r['eligible']]
    for day in days:
        tomorrow=dt.date.fromisoformat(day['date'])+dt.timedelta(days=1)
        # Lunar New Year cannot occur after the table's final December day.
        next_day=calendar.day(tomorrow) if tomorrow.isoformat()<=calendar.meta['end'] else None
        day['is_lunar_new_year_eve']=bool(next_day and not next_day['leap_month'] and (next_day['lunar_month'],next_day['lunar_day'])==(1,1))
    by_id={r['id']:r for r in records};used_groups=set();used_titles=set();assigned={};author_days={}
    events={d['date']:event_for(d,rules) for d in days}
    # Reserve scarce personal/festival/anniversary content before ordinary days.
    def ordering(day):
        e=events[day['date']];has_author=any(day['date'][5:] in (r['birth_md'],r['death_md']) for r in records)
        return (-max(e['priority'],65 if has_author and not e['personal'] else 0),day['date'])
    for day in sorted(days,key=ordering):
        date=day['date'];event=events[date];ordinal=dt.date.fromisoformat(date).toordinal();md=date[5:]
        if 'pool' in event:
            pool=event['pool']
            if not pool:raise ValueError(f'Empty curated pool for {event["id"]}')
            # Keep family-first order across the spring window; rotate other pools yearly.
            shift=0 if event['id']=='lunar_new_year_window' else (year-2026)%len(pool)
            ordered=pool[shift:]+pool[:shift]
            options=[by_id[i] for i in ordered if i in by_id]
        else:
            month=int(date[5:7]);season='spring' if 3<=month<=5 else 'summer' if 6<=month<=8 else 'autumn' if 9<=month<=11 else 'winter'
            def score(r):
                tags=set(r['tags']);value=0
                value+=120*len(tags&set(event['tags']))
                value+=90 if md in (r['birth_md'],r['death_md']) else 0
                value+=12 if season in tags else 0
                value+=5 if day['weekday']>=5 and 'rest' in tags else 0
                if event['label'] in ('元旦','春节','岁末') and r['kind']=='宜':value+=12
                value-=80 if any(abs(ordinal-o)<14 for o in author_days.get(r['author_id'],[])) else 0
                value-=8*len(author_days.get(r['author_id'],[]))
                value-=10 if r.get('confidence') is not None and r['confidence']<.8 else 0
                tie=hashlib.sha256((str(year)+'|'+date+'|'+r['id']).encode()).digest()
                return (-value,tie)
            options=sorted(records,key=score)
        chosen=next((r for r in options if r['content_group'] not in used_groups and (not rules['annual_unique_title'] or r['title_key'] not in used_titles)),None)
        if chosen is None:raise ValueError(f'No unique eligible content for {date} ({event["id"]}); no silent repetition or unrelated personal-date fallback')
        used_groups.add(chosen['content_group']);used_titles.add(chosen['title_key']);author_days.setdefault(chosen['author_id'],[]).append(ordinal)
        reasons=[]
        if event['personal']:reasons.append('personal_curated_pool')
        elif event.get('curation'):reasons.append(event['curation'])
        else:
            if set(chosen['tags'])&set(event['tags']):reasons.append('calendar_theme')
            if md==chosen['birth_md']:reasons.append('author_birthday')
            if md==chosen['death_md']:reasons.append('author_death_anniversary')
            if not reasons:reasons.append('season_weekday_variety')
        display_label=(day['solar_term'] or '') if event['personal'] else event['label']
        assigned[date]=dict(**day,record_id=chosen['id'],content_group=chosen['content_group'],title_key=chosen['title_key'],event_id=event['id'],event_label=event['label'],display_label=display_label,personal=event['personal'],selection_reasons=reasons)
    result=dict(schema=1,year=year,owner_id=rules['owner_id'],timezone=rules['timezone'],input_version=version,calendar_sha256=calendar.meta['sha256'],
                days=[assigned[d['date']] for d in days],unique_content_groups=len(used_groups),unique_titles=len(used_titles),
                note='Historical source_date stays separate from display date; ordinary rules use lexical tags, not an on-device language model.')
    assert len(used_groups)==len(days)
    return result

def save_plan(plan,path):
    if path.exists():
        existing=json.loads(path.read_text())
        if existing!=plan:raise ValueError('A different annual plan already exists; preserve it and its use history instead of silently reshuffling this year')
        return
    path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n');temp.replace(path)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--year',type=int,default=dt.date.today().year);ap.add_argument('--output',type=Path);args=ap.parse_args()
    plan=plan_year(args.year);target=args.output or ROOT.parents[1]/f'artifacts/tr2e_calendar_400x600/{args.year}.json';save_plan(plan,target)
    print(target);print('days',len(plan['days']),'unique content',plan['unique_content_groups'],'unique titles',plan['unique_titles'])
    for day in plan['days']:
        if day['personal']:print(day['date'],day['event_label'],day['record_id'])

if __name__=='__main__':main()
