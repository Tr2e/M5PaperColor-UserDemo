import copy,datetime as dt,hashlib,json,socket,tempfile,unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch
from calendar_data import Calendar
from planner import event_for,load_inputs,plan_year,save_plan
from render import layout,render,wrap

ROOT=Path(__file__).resolve().parent

class CalendarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog,cls.rules,_=load_inputs();cls.by_id={r['id']:r for r in cls.catalog['records']};cls.calendar=Calendar()
        with patch.object(socket,'socket',side_effect=AssertionError('Offline runtime attempted networking')):
            cls.plan=plan_year(2026);cls.leap=plan_year(2028)
        cls.by_date={d['date']:d for d in cls.plan['days']}

    def test_annual_no_repeat_and_replay(self):
        for plan,length in ((self.plan,365),(self.leap,366)):
            self.assertEqual(len(plan['days']),length)
            self.assertEqual(len({d['content_group'] for d in plan['days']}),length)
            self.assertEqual(len({d['title_key'] for d in plan['days']}),length)
        self.assertEqual(self.plan,plan_year(2026))

    def test_personal_overrides(self):
        for date,event in [('2026-05-08','wife_birthday'),('2026-06-21','wedding_anniversary'),('2026-11-11','son_birthday')]:
            d=self.by_date[date];self.assertEqual(d['event_id'],event);self.assertTrue(d['personal'])
            self.assertEqual(d['display_label'],'夏至' if date=='2026-06-21' else '')
        shifted=next(d for y in range(2026,2101) for d in self.calendar.year(y) if d['solar_term']=='夏至' and d['date'][8:]=='20')
        self.assertEqual(event_for(shifted,self.rules)['id'],'wedding_anniversary')
        self.assertNotEqual(event_for(self.calendar.day(shifted['date'][:8]+'21'),self.rules)['id'],'wedding_anniversary')

    def test_lunar_holidays_and_fixed_overlap(self):
        for date,label in [('2026-02-16','除夕'),('2026-02-17','春节'),('2026-03-03','元宵节'),('2026-06-19','端午节'),('2026-08-19','七夕'),('2026-09-25','中秋节'),('2026-10-18','重阳节')]:
            self.assertEqual(self.by_date[date]['event_label'],label)
        self.assertEqual(event_for(self.calendar.day('2020-10-01'),self.rules)['label'],'中秋节')
        leap_day=next(d for d in self.calendar.year(2025) if d['leap_month'])
        fake=dict(leap_day,lunar_month=8,lunar_day=15,solar_term=None)
        self.assertNotEqual(event_for(fake,self.rules)['label'],'中秋节')
        # No lunar month 12 day 30 in 2026: Eve must be day 29.
        self.assertEqual(self.by_date['2026-02-16']['lunar_day'],29)

    def test_positive_windows_are_curated(self):
        selected=[d for d in self.plan['days'] if d['event_id']=='year_boundary_window']
        self.assertEqual(len(selected),13)
        for day in selected:
            self.assertIn(day['record_id'],self.rules['year_boundary']['pool'])
            self.assertEqual(self.by_id[day['record_id']]['kind'],'宜')
        spring=[d for d in self.plan['days'] if d['event_id']=='lunar_new_year_window']
        self.assertEqual(len(spring),9)
        self.assertTrue(all(d['record_id'] in self.rules['lunar_new_year']['pool'] for d in spring))

    def test_no_unrelated_fallback(self):
        rules=copy.deepcopy(self.rules);rules['events'][0]['pool']=[]
        with self.assertRaisesRegex(ValueError,'Empty curated pool'):plan_year(2026,rules=rules)

    def test_persisted_year_cannot_silently_change(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'2026.json';save_plan(self.plan,path);save_plan(self.plan,path)
            other=copy.deepcopy(self.plan);other['owner_id']='different'
            with self.assertRaisesRegex(ValueError,'different annual plan'):save_plan(other,path)

    def test_calendar_full_range_consistency(self):
        for year in range(1901,2101):
            days=self.calendar.year(year)
            self.assertEqual(sum(d['solar_term'] is not None for d in days),24,year)
            self.assertEqual(sum((d['lunar_month'],d['lunar_day'],d['leap_month'])==(1,1,False) for d in days),1,year)
            self.assertTrue(all(1<=d['lunar_month']<=12 and 1<=d['lunar_day']<=30 for d in days))
        for date in ('1900-12-31','2101-01-01'):
            with self.assertRaises(ValueError):self.calendar.day(date)

    def test_duplicate_quote_and_source_integrity(self):
        self.assertEqual(self.by_id['2021-05-08']['content_group'],self.by_id['2021-08-25']['content_group'])
        directory=ROOT.parents[1]/'research/owspace-calendar/months'
        for name,digest in self.catalog['source_hashes'].items():self.assertEqual(hashlib.sha256((directory/name).read_bytes()).hexdigest(),digest,name)

    def test_all_eligible_text_fits_and_samples_are_binary(self):
        for r in self.catalog['records']:
            if r['eligible']:
                spec=layout(r)
                self.assertEqual(''.join(spec['quote_lines']),r['excerpt'].replace('\n',''))
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            for date in ('2026-01-01','2026-05-08','2026-06-21','2026-11-11'):
                day=self.by_date[date];target=Path(directory)/(date+'.png');result=render(day,self.by_id[day['record_id']],target)
                rendered_text=''.join(x['text'] for x in result['text'])
                for private_label in ('结婚纪念日','妻子生日','儿子生日'):self.assertNotIn(private_label,rendered_text)
                self.assertEqual(result['signature'],'Tr2e')
                self.assertEqual(next(t['font_px'] for t in result['text'] if t['text']=='Tr2e'),14)
                image=Image.open(target);self.assertEqual(image.size,(400,600));self.assertEqual(set(image.convert('L').tobytes()),{0,255})
                self.assertEqual(target.with_suffix('.bin').stat().st_size,30000)

if __name__=='__main__':unittest.main()
