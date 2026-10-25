import sys
from pathlib import Path
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'pipeline'))
import analysis_slots as slots

TZ=ZoneInfo('Asia/Tehran')
def at(hour,minute=0,day=25):return datetime(2026,10,day,hour,minute,tzinfo=TZ)

class SlotTests(unittest.TestCase):
    def test_all_four_inclusive_starts_and_exclusive_ends(self):
        for h in (6,9,12,18):
            self.assertEqual(slots.current(at(h))[0],f'2026-10-25/{h:02}')
            self.assertIsNotNone(slots.current(at(h,59)))
            self.assertIsNone(slots.current(at(h+1)))
    def test_outside_windows_never_catches_up(self):
        for h in (0,5,7,8,10,11,13,14,15,16,17,19,23):
            self.assertIsNone(slots.current(at(h)))
    def test_utc_conversion(self):
        self.assertEqual(slots.current(datetime(2026,10,25,2,30,tzinfo=timezone.utc))[0],
                         '2026-10-25/06')
    def test_no_rolling_cap_from_yesterday(self):
        s={'products':{str(i):{'published_utc':at(6,day=24).isoformat()} for i in range(20)}}
        key,slot=slots.refresh(s,at(6))
        self.assertEqual(slot['status'],'waiting')
    def test_sent_slot_is_not_reset_by_next_cron(self):
        s={};key,slot=slots.refresh(s,at(6));slot['status']='sent'
        self.assertEqual(slots.refresh(s,at(6,30))[1]['status'],'sent')
    def test_missed_and_partial_are_audited(self):
        s={};key,slot=slots.refresh(s,at(6));slot.update(product='p',status='reserved')
        slots.refresh(s,at(8))
        self.assertEqual(s['analysis_slots'][key]['status'],'partial_expired')
        self.assertEqual(slots.refresh({},at(8))[0],None)
    def test_next_day_reset(self):
        self.assertEqual(slots.next_window(at(23))[1],at(6,day=26))
    def test_per_day_four_slots_only(self):
        self.assertEqual(len(slots.windows(at(12))),4)
    def test_45_day_audit_bound(self):
        s={'analysis_slots':{'2026-01-01/06':{'end':'2026-01-01T07:00:00+03:30','status':'sent'}}}
        slots.refresh(s,at(6));self.assertNotIn('2026-01-01/06',s['analysis_slots'])
