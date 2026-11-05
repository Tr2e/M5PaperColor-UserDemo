"""Validate all deployed years and compare the actual C++ renderer to Python."""
import collections,datetime as dt,hashlib,json,struct,subprocess,sys,tempfile,zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(REPO/'tools/tr2e_calendar'))
from planner import load_inputs
from production_planner import FROZEN,events_for,inputs,context_fits
from production_layout import render,layout
from calendar_data import Calendar
from PIL import Image,ImageChops

def main():
    catalog,rules,_=load_inputs();by={r['id']:r for r in catalog['records']};cal=Calendar()
    manifest=json.loads((ROOT/'main/assets/manifest.json').read_text());path=ROOT/'main/assets/calendar.pack';blob=path.read_bytes()
    fields=struct.unpack_from('<16I',blob,8);start,count,day_table=fields[2],fields[3],fields[8]
    assert hashlib.sha256(blob).hexdigest()==manifest['sha256']
    assert zlib.crc32(blob[:12]+bytes(4)+blob[16:])==fields[1]
    assert fields[14]==3 and fields[15]==len(manifest['digit_heights'])
    frozen={year:json.loads(p.read_text()) for year,p in FROZEN.items()}
    frozen_days={d['date']:d for p in frozen.values() for d in p['days']}
    event_years={year:events_for(year) for year in range(2028,2100)}
    production={r['id']:r for r in inputs()[0]}
    years=collections.defaultdict(list);days={}
    for index in range(count):
        date=dt.date.fromordinal(start+index);day=cal.day(date);next_day=cal.day(date+dt.timedelta(days=1))
        day['is_lunar_new_year_eve']=not next_day['leap_month'] and (next_day['lunar_month'],next_day['lunar_day'])==(1,1)
        if date.year in frozen:
            approved=frozen_days[date.isoformat()]
            day.update(personal=approved['personal'],display_label=approved['display_label'])
            event=dict(pool=None,personal=approved['personal'],id='frozen')
        else:
            event=event_years[date.year][date.isoformat()]
            day.update(personal=event['personal'],display_label=event['display_label'])
        record,lunar,label=struct.unpack_from('<HHH',blob,day_table+index*6)
        assert lunar==day['lunar_month']|(day['lunar_day']<<4)|(int(day['leap_month'])<<9)
        r=by[manifest['record_ids'][record]];years[date.year].append((day,r,event));days[date.isoformat()]=(day,r)
        assert manifest['labels'][label-72]==day['display_label'],date
        if date.year in frozen:assert r['id']==frozen_days[date.isoformat()]['record_id'],date
        else:
            assert r['id'] in production,date
            assert context_fits(production[r['id']],event),date
            if event['pool']:assert r['id'] in event['pool'],date
        if event['personal']:assert day['display_label'] in ('','夏至')
    groups={};titles={};overlaps=[]
    for year,entries in years.items():
        n=(dt.date(year+1,1,1)-dt.date(year,1,1)).days
        g={r['content_group'] for _,r,_ in entries};t={r['title_key'] for _,r,_ in entries}
        assert len(entries)==len(g)==len(t)==n,year
        if year-1 in groups:overlaps.append(len(g&groups[year-1]));assert overlaps[-1]/n<=.05
        old_groups=set().union(*(groups.get(y,set()) for y in range(year-5,year)))
        old_titles=set().union(*(titles.get(y,set()) for y in range(year-2,year)))
        for day,r,e in entries:
            if year>=2028 and not e['pool']:
                assert r['content_group'] not in old_groups,day['date']
                assert r['title_key'] not in old_titles,day['date']
        groups[year]=g;titles[year]=t
    comparisons=[];differences=[]
    with tempfile.TemporaryDirectory(prefix='tr2e-engine-') as temporary:
        directory=Path(temporary);exe=directory/'engine'
        subprocess.run(['clang++','-std=c++17','-Wall','-Wextra','-Werror','-O2','-I'+str(ROOT/'main'),str(ROOT/'main/calendar_engine.cpp'),str(ROOT/'tests/engine_test.cpp'),'-o',str(exe)],check=True)
        # A valid CRC must not make malformed variable-height tables acceptable.
        corruptions=[(68,'<I',0),(68,'<I',129),
                     (struct.unpack_from('<I',blob,fields[7])[0]+6,'<H',fields[15]),
                     (fields[11],'<H',fields[4])]
        for offset,fmt,value in corruptions:
            bad=bytearray(blob);struct.pack_into(fmt,bad,offset,value)
            struct.pack_into('<I',bad,12,0);struct.pack_into('<I',bad,12,zlib.crc32(bad))
            target=directory/'malformed.pack';target.write_bytes(bad)
            subprocess.run([str(exe),str(target),'--reject'],check=True)
        # Every approved current/next-year page, plus future leap, term and
        # every variable date height actually present in the new pack.
        dates=[d for d in days if d.startswith(('2026-','2027-'))]+['2028-02-29','2028-03-01','2048-06-20','2099-12-31']
        seen_heights=set()
        for date,(day,r) in days.items():
            h=layout(r)['digit_h']
            if h not in seen_heights:dates.append(date);seen_heights.add(h)
            if len(seen_heights)==len(manifest['digit_heights']):break
        dates=list(dict.fromkeys(dates))
        date_list=directory/'dates.txt';date_list.write_text('\n'.join(d.replace('-',' ') for d in dates)+'\n')
        subprocess.run([str(exe),str(path),'--batch',str(directory),str(date_list)],check=True,stdout=subprocess.DEVNULL)
        for date in dates:
            native=directory/(date+'.bin');day,r=days[date];expected=directory/'python.png';render(day,r,expected)
            a=native.read_bytes();b=expected.with_suffix('.bin').read_bytes();assert len(a)==len(b)==30000
            if date.startswith('2027-'):
                with Image.open(expected) as reference,Image.open(REPO/'artifacts/tr2e_calendar_2027_editorial_v2_1/days'/(date+'.png')) as approved:
                    assert ImageChops.difference(reference,approved).getbbox() is None,date
            difference=sum((x^y).bit_count() for x,y in zip(a,b))
            # The pack includes sparse glyph-overlap ink corrections, so even
            # author-credit edge pixels must match, not just text positions.
            assert difference==0,(date,difference)
            differences.append(dict(date=date,pixels=difference))
            comparisons.append(date)
    result=dict(years=len(years),days=count,annual_repeats=0,max_adjacent_repeated_groups=max(overlaps),min_adjacent_distinct_fraction=1-max(overlaps)/365,ordinary_group_cooldown_years=5,ordinary_title_cooldown_years=2,native_compared_pages=len(comparisons),native_pixel_exact_pages=sum(d['pixels']==0 for d in differences),max_pixel_difference=max(d['pixels'] for d in differences),nonexact_pages=[d for d in differences if d['pixels']],native_cases=comparisons,pack_sha256=manifest['sha256'],approved_2027_pages_exact_in_python=365,frozen_years=[2026,2027],pack_schema=3,digit_heights_checked=sorted(seen_heights),signature_variant='A',quote_bottom_gap_px=16,title_to_divider_gap_px=20,firmware_compiled=False,host_core_compiled=True,physical_device_verified=False)
    (ROOT/'tests/verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='native_cases'},ensure_ascii=False))

if __name__=='__main__':main()
