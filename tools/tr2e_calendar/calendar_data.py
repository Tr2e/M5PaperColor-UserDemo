"""Read-only offline civil/lunar calendar, with explicit supported bounds."""
import datetime as dt
import hashlib
import json
import struct
from pathlib import Path

ASSETS=Path(__file__).resolve().parent/'assets'

class Calendar:
    def __init__(self,assets=ASSETS):
        self.meta=json.loads((assets/'calendar.json').read_text())
        self.data=(assets/'calendar.bin').read_bytes()
        magic,self.start,self.count=struct.unpack_from('<8sII',self.data)
        if magic!=b'TR2ECAL1' or len(self.data)!=16+self.count*2 or hashlib.sha256(self.data).hexdigest()!=self.meta['sha256']:
            raise ValueError('Invalid offline calendar table')

    def day(self,date):
        if isinstance(date,str):date=dt.date.fromisoformat(date)
        index=date.toordinal()-self.start
        if not 0<=index<self.count:raise ValueError('Calendar supports 1901-01-01 through 2100-12-31; do not guess solar terms outside this range')
        value=struct.unpack_from('<H',self.data,16+2*index)[0]
        month=value&15;day=(value>>4)&31;leap=bool(value&512);term_id=(value>>10)&31
        return dict(date=date.isoformat(),weekday=date.weekday(),lunar_month=month,lunar_day=day,leap_month=leap,
                    lunar_label=('闰' if leap else '')+self.meta['months'][month-1]+self.meta['days'][day-1],
                    solar_term=self.meta['terms'][term_id-1] if term_id else None)

    def year(self,year):
        start=dt.date(year,1,1);end=dt.date(year+1,1,1)
        return [self.day(start+dt.timedelta(days=i)) for i in range((end-start).days)]
