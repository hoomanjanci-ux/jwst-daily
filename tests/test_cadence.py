import sys
from pathlib import Path
import unittest
from datetime import datetime, timezone, timedelta
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'pipeline'))
import cadence

NOW = datetime(2026, 10, 24, 20, tzinfo=timezone.utc)
def state(hours=5):
    return {'products': {'p': {'published_utc': (NOW-timedelta(hours=hours)).isoformat(),
                               'channels': {'fa_ai': 'sent', 'en_ai': 'sent'}}}}

class CadenceTests(unittest.TestCase):
    def test_empty_queue_does_not_publish_and_refills(self):
        p = cadence.plan(state(), 0, NOW)
        self.assertFalse(p['publish_due'])
        self.assertTrue(p['refill_due'])
    def test_no_second_post_on_next_cron(self):
        self.assertFalse(cadence.plan(state(.25), 6, NOW)['publish_due'])
    def test_shorter_gap_only_with_healthy_reserve(self):
        self.assertTrue(cadence.plan(state(5), 5, NOW)['publish_due'])
        self.assertFalse(cadence.plan(state(5), 3, NOW)['publish_due'])
        self.assertFalse(cadence.plan(state(7), 1, NOW)['publish_due'])
        self.assertTrue(cadence.plan(state(8), 1, NOW)['publish_due'])
    def test_delayed_cron_can_publish_but_no_catchup_burst(self):
        self.assertTrue(cadence.plan(state(18), 6, NOW)['publish_due'])
        self.assertFalse(cadence.plan(state(0), 6, NOW)['publish_due'])
    def test_rolling_day_cap(self):
        s = {'products': {str(i): {'published_utc': (NOW-timedelta(hours=h)).isoformat(),
                                  'channels': {'fa_ai':'sent'}}
                          for i,h in enumerate([23,17,11,5])}}
        self.assertFalse(cadence.plan(s,6,NOW)['publish_due'])
        self.assertTrue(cadence.plan(s,6,NOW+timedelta(hours=1))['publish_due'])
    def test_news_and_test_posts_do_not_affect_cadence(self):
        s = {'products': {'p': {'published_utc': NOW.isoformat(),
                               'channels': {'test_fa':'sent','fa_official':'sent'}}}}
        self.assertTrue(cadence.plan(s,3,NOW)['publish_due'])
    def test_failed_attempt_backoff(self):
        s = state(12);s['analysis_publish_attempt_utc']=NOW.isoformat()
        self.assertFalse(cadence.plan(s,6,NOW)['publish_due'])
    def test_refill_backoff(self):
        s=state();s['analysis_refill_attempt_utc']=(NOW-timedelta(hours=3)).isoformat()
        self.assertFalse(cadence.plan(s,0,NOW)['refill_due'])
    def test_reserve_cap(self):
        self.assertFalse(cadence.plan(state(),4,NOW)['refill_due'])
    def test_daily_bytes_and_reset(self):
        s=state();cadence.account_bytes(s,900_000_000,NOW)
        self.assertFalse(cadence.plan(s,0,NOW)['refill_due'])
        self.assertTrue(cadence.plan(s,0,NOW+timedelta(days=1))['refill_due'])
    def test_malformed_dates_are_safe(self):
        self.assertTrue(cadence.plan({'analysis_refill_attempt_utc':'bad'},0,NOW)['refill_due'])
    def test_partial_real_send_counts_against_burst(self):
        s=state(.5);s['products']['p']['channels']={'en_ai':'sent','fa_ai':'error'}
        self.assertFalse(cadence.plan(s,6,NOW)['publish_due'])

if __name__ == '__main__': unittest.main()
