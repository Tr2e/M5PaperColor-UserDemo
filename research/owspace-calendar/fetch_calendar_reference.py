"""Cache parsed official date mappings, not source media."""
import concurrent.futures,json,re,time,urllib.request
from pathlib import Path
OUT=Path(__file__).resolve().parent/'title_date_analysis'/'calendar_reference.json'
def fetch(year):
 url=f'https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T{year}c.txt'
 for attempt in range(4):
  try:
   with urllib.request.urlopen(url,timeout=15) as response:text=response.read().decode('utf-8-sig')
   break
  except Exception:
   if attempt==3:raise
   time.sleep(1)
 rows=[];month=None
 for line in text.splitlines():
  m=re.match(r'(\d{4})年(\d+)月(\d+)日\s+(\S+)\s+(星期\S)(?:\s+(\S+))?',line)
  if not m:continue
  yy,mm,dd,ld,week,term=m.groups()
  if ld.endswith('月'):month=ld;day='初一'
  else:day=ld
  rows.append({'date':f'{int(yy):04}-{int(mm):02}-{int(dd):02}','lunar_month':month,'lunar_day':day,'solar_term':term})
 assert len(rows) in (365,366),(year,len(rows))
 return year,rows
existing=json.loads(OUT.read_text())['days'] if OUT.exists() else []
cache={y:[r for r in existing if r['date'].startswith(str(y))] for y in range(2015,2026)}
with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
 futures=[pool.submit(fetch,y) for y in cache if not cache[y]]
 for f in concurrent.futures.as_completed(futures):
  y,cache[y]=f.result();OUT.parent.mkdir(exist_ok=True);OUT.write_text(json.dumps({'source_template':'https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T{year}c.txt','days':[r for y in sorted(cache) for r in cache[y]]},ensure_ascii=False,separators=(',',':'))+'\n');print(y,len(cache[y]),flush=True)
