"""Validate all deployed years and compare the actual C++ renderer to Python."""
import collections,datetime as dt,hashlib,json,struct,subprocess,sys,tempfile,zlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1];REPO=ROOT.parent
sys.path.insert(0,str(REPO/'tools/tr2e_calendar'))
from planner import load_inputs,event_for
from calendar_data import Calendar
from render import render

def main():
    catalog,rules,_=load_inputs();by={r['id']:r for r in catalog['records']};cal=Calendar()
    manifest=json.loads((ROOT/'main/assets/manifest.json').read_text());path=ROOT/'main/assets/calendar.pack';blob=path.read_bytes()
    fields=struct.unpack_from('<16I',blob,8);start,count,day_table=fields[2],fields[3],fields[8]
    assert hashlib.sha256(blob).hexdigest()==manifest['sha256']
    assert zlib.crc32(blob[:12]+bytes(4)+blob[16:])==fields[1]
    years=collections.defaultdict(list);days={}
    for index in range(count):
        date=dt.date.fromordinal(start+index);day=cal.day(date);next_day=cal.day(date+dt.timedelta(days=1))
        day['is_lunar_new_year_eve']=not next_day['leap_month'] and (next_day['lunar_month'],next_day['lunar_day'])==(1,1)
        event=event_for(day,rules);day['personal']=event['personal'];day['display_label']=(day['solar_term'] or '') if event['personal'] else event['label']
        record,lunar,label=struct.unpack_from('<HHH',blob,day_table+index*6)
        assert lunar==day['lunar_month']|(day['lunar_day']<<4)|(int(day['leap_month'])<<9)
        r=by[manifest['record_ids'][record]];years[date.year].append((day,r,event));days[date.isoformat()]=(day,r)
        if 'pool' in event:assert r['id'] in event['pool'],date
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
            if 'pool' not in e:
                assert r['content_group'] not in old_groups,day['date']
                assert r['title_key'] not in old_titles,day['date']
        groups[year]=g;titles[year]=t
    comparisons=[];differences=[]
    with tempfile.TemporaryDirectory(prefix='tr2e-engine-') as temporary:
        directory=Path(temporary);exe=directory/'engine'
        subprocess.run(['clang++','-std=c++17','-Wall','-Wextra','-Werror','-O2','-I'+str(ROOT/'main'),str(ROOT/'main/calendar_engine.cpp'),str(ROOT/'tests/engine_test.cpp'),'-o',str(exe)],check=True)
        # Every current-year page, plus future rollover/leap/last-day cases.
        dates=[d for d in days if d.startswith('2026-')]+['2027-01-01','2027-12-31','2028-02-29','2028-03-01','2048-06-20','2099-12-31']
        for date in dates:
            native=directory/'native.bin';day,r=days[date];expected=directory/'python.png';render(day,r,expected)
            subprocess.run([str(exe),str(path),str(native),*date.split('-')],check=True,stdout=subprocess.DEVNULL)
            a=native.read_bytes();b=expected.with_suffix('.bin').read_bytes();difference=sum((x^y).bit_count() for x,y in zip(a,b))
            # Independent 1-bit glyphs cannot accumulate two overlapping gray
            # antialias edges as Pillow does. Permit only tiny raster differences;
            # large displacement, missing glyphs or truncation still fail.
            assert difference<=32,(date,difference)
            differences.append(dict(date=date,pixels=difference))
            comparisons.append(date)
    result=dict(years=len(years),days=count,annual_repeats=0,max_adjacent_repeated_groups=max(overlaps),min_adjacent_distinct_fraction=1-max(overlaps)/365,ordinary_group_cooldown_years=5,ordinary_title_cooldown_years=2,native_compared_pages=len(comparisons),native_pixel_exact_pages=sum(d['pixels']==0 for d in differences),max_pixel_difference=max(d['pixels'] for d in differences),nonexact_pages=[d for d in differences if d['pixels']],native_cases=comparisons,pack_sha256=manifest['sha256'],physical_device_verified=False)
    (ROOT/'tests/verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='native_cases'},ensure_ascii=False))

if __name__=='__main__':main()
