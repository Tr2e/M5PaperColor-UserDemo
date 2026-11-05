"""Editorial integration checks independent of ESP-IDF/firmware builds."""
import datetime as dt,json,unittest
from production_planner import calendar_days,events_for,context_fits,plan_year,FROZEN

class ProductionTests(unittest.TestCase):
    def test_approved_years_remain_frozen(self):
        for year,path in FROZEN.items():
            self.assertEqual(plan_year(year,[]),json.loads(path.read_text()))

    def test_year_boundary_has_distinct_phases(self):
        e=events_for(2028)
        for md,event in [('01-01','元旦'),('01-02','迎新'),('12-27','回望'),('12-28','宽慰'),('12-29','回望'),('12-30','期待'),('12-31','期待')]:
            self.assertEqual(e['2028-'+md]['id'],event)
        self.assertEqual(e['2028-01-04']['id'],'腊八')
        self.assertEqual(e['2028-01-07']['id'],'ordinary')

    def test_personal_dates_follow_solar_term_and_hide_identity(self):
        e=events_for(2048);days=calendar_days(2048)
        date=next(d['date'] for d in days if d['solar_term']=='夏至')
        self.assertEqual(date,'2048-06-20')
        for date,kind in [(date,'wedding_anniversary'),('2048-05-08','wife_birthday'),('2048-11-11','son_birthday')]:
            self.assertTrue(e[date]['personal']);self.assertEqual(e[date]['id'],kind)
            self.assertIn(e[date]['display_label'],('','夏至'))

    def test_lunar_dates_and_compound_labels(self):
        e=events_for(2027)
        self.assertEqual(e['2027-02-05']['id'],'除夕')
        self.assertEqual(e['2027-08-08']['display_label'],'七夕·立秋')
        self.assertEqual(e['2027-10-08']['display_label'],'重阳节·寒露')
        self.assertEqual(e['2027-09-15']['id'],'中秋节')
        e28=events_for(2028)
        for d in calendar_days(2028):
            if d['leap_month']:
                self.assertNotIn(e28[d['date']]['id'],('春节','元宵节','中秋节'))

    def test_context_not_yi_ji_sentiment(self):
        ordinary=dict(warm=False,child=False);warm=dict(warm=True,child=False);child=dict(warm=True,child=True)
        r=dict(kind='宜',editorial=dict(context_flags=['失落或离别']))
        self.assertTrue(context_fits(r,ordinary));self.assertFalse(context_fits(r,warm))
        r=dict(kind='忌',editorial=dict(context_flags=[]))
        self.assertTrue(context_fits(r,warm))
        r['editorial']['context_flags']=['成人亲密']
        self.assertTrue(context_fits(r,warm));self.assertFalse(context_fits(r,child))

if __name__=='__main__':unittest.main()
