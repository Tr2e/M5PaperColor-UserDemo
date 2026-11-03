"""Build the offline 1901–2100 UTC+8 calendar table from HKO text tables.

Network is used only by this build tool, never by planner.py or render.py.
Binary: <8sII header (magic, start ordinal, day count), followed by <H per day.
Bits: lunar month 0..3, day 4..8, leap 9, solar-term-index+1 10..14.
"""
import argparse,concurrent.futures,datetime as dt,hashlib,json,re,struct,time,urllib.request
from pathlib import Path

TERMS='小寒 大寒 立春 雨水 驚蟄 春分 清明 穀雨 立夏 小滿 芒種 夏至 小暑 大暑 立秋 處暑 白露 秋分 寒露 霜降 立冬 小雪 大雪 冬至'.split()
MONTHS='正月 二月 三月 四月 五月 六月 七月 八月 九月 十月 十一月 十二月'.split()
DAYS='初一 初二 初三 初四 初五 初六 初七 初八 初九 初十 十一 十二 十三 十四 十五 十六 十七 十八 十九 二十 廿一 廿二 廿三 廿四 廿五 廿六 廿七 廿八 廿九 三十'.split()
ROOT=Path(__file__).resolve().parent

def fetch(year,cache):
    p=cache/f'{year}.json'
    if p.exists():return json.loads(p.read_text())
    url=f'https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T{year}c.txt'
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url,timeout=25) as response:raw=response.read()
            break
        except Exception:
            if attempt==3:raise
            time.sleep(attempt+1)
    rows=[]
    for line in raw.decode('utf-8-sig').splitlines():
        m=re.match(r'(\d{4})年(\d+)月(\d+)日\s+(\S+)\s+星期\S(?:\s+(\S+))?',line)
        if m:
            y,mo,da,label,term=m.groups()
            rows.append([f'{int(y):04}-{int(mo):02}-{int(da):02}',label,term])
    assert len(rows)==(dt.date(year+1,1,1)-dt.date(year,1,1)).days,(year,len(rows))
    result={'year':year,'url':url,'source_sha256':hashlib.sha256(raw).hexdigest(),'rows':rows}
    p.write_text(json.dumps(result,ensure_ascii=False));time.sleep(.65)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cache',type=Path,default=Path('/tmp/tr2e-calendar-study/calendars'));args=ap.parse_args()
    args.cache.mkdir(parents=True,exist_ok=True)
    years={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures={pool.submit(fetch,y,args.cache):y for y in range(1901,2101)}
        for f in concurrent.futures.as_completed(futures):
            item=f.result();years[item['year']]=item
            if len(years)%20==0:print('completed',len(years),'of 200 years',flush=True)
    rows=[r for y in sorted(years) for r in years[y]['rows']]
    first_month=next(r[1] for r in rows if r[1].endswith('月'))
    month=(MONTHS.index(first_month.replace('閏','')) if not first_month.startswith('閏') else MONTHS.index(first_month[1:])+1) or 12
    leap=False;values=[]
    for date,label,term in rows:
        if label.endswith('月'):
            leap=label.startswith('閏');month=MONTHS.index(label.replace('閏',''))+1;day=1
        else:day=DAYS.index(label)+1
        term_id=TERMS.index(term)+1 if term else 0
        values.append(month|(day<<4)|(int(leap)<<9)|(term_id<<10))
    start=dt.date(1901,1,1).toordinal();payload=struct.pack('<8sII','TR2ECAL1'.encode(),start,len(values))+struct.pack('<'+'H'*len(values),*values)
    out=ROOT/'assets';out.mkdir(exist_ok=True)
    (out/'calendar.bin').write_bytes(payload)
    meta={'schema':1,'start':'1901-01-01','end':'2100-12-31','timezone':'UTC+08:00','terms':TERMS,'months':MONTHS,'days':DAYS,
          'sha256':hashlib.sha256(payload).hexdigest(),'bytes':len(payload),'sources':[{k:v for k,v in years[y].items() if k!='rows'} for y in sorted(years)]}
    (out/'calendar.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    print('offline calendar bytes',len(payload),flush=True)

if __name__=='__main__':main()
