"""Launch eligibility from trusted, sanitized native account observations."""
import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'mcp/memory'))
from hearth2.store import RecordError


class LaunchGuardTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.launch_guards'),
                             'native account launch guards are not implemented')
        self.guards = importlib.import_module('hearth2.launch_guards')
        self.now = datetime(2026, 10, 30, 16, tzinfo=timezone.utc)
        self.route = {'configured_provider':'openai', 'api_key_present':False,
                      'unexpected_environment':False, 'other_credentials_present':False,
                      'native_login_present':True}
        self.account = {'account':{'type':'chatgpt','email':'fixture@example.test'},
                        'requiresOpenaiAuth':True}
        self.limits = {'rateLimits':{'credits':{'hasCredits':False,'unlimited':False},
                       'primary':{'usedPercent':12},'secondary':{'usedPercent':25}}}
        self.review = {'billing_month':'2026-10','seat_limit':75,'extra_usage_enabled':True,
                       'reviewed_mtd':22.18,'positive_spend_reviewed':True,
                       'source':'human-accepted-policy-fixture'}

    def codex(self, **changes):
        fields = dict(account=self.account, limits=self.limits, route=self.route,
                      observed_at=self.now.isoformat(), now=self.now)
        fields.update(changes)
        return self.guards.codex_launch_check(**fields)

    def claude(self, **changes):
        fields = dict(auth={'loggedIn':True}, route={**self.route,'configured_provider':'anthropic'},
                      review=self.review, accepted_seat_limit=75,
                      observed_at=self.now.isoformat(), now=self.now)
        fields.update(changes)
        return self.guards.claude_launch_check(**fields)

    def test_chatgpt_native_account_with_nonexhausted_windows_has_no_paid_fallback(self):
        result = self.codex()
        self.assertEqual(result['provider'],'openai')
        self.assertEqual(result['used_percent'],{'primary':12,'secondary':25})
        self.assertNotIn('fixture@example.test',str(result))
        self.assertFalse(result['paid_fallback'])

    def test_every_returned_window_is_checked_and_no_window_is_unknown(self):
        one = {'rateLimits':{**self.limits['rateLimits'],'secondary':None}}
        self.assertEqual(self.codex(limits=one)['used_percent'],{'primary':12})
        for window in [None, {}, {'usedPercent':True}, {'usedPercent':'12'},
                       {'usedPercent':-1}, {'usedPercent':100}, {'usedPercent':float('nan')},
                       {'usedPercent':10**1000}]:
            rates = {**self.limits['rateLimits'],'primary':None,'secondary':window}
            with self.subTest(window=window), self.assertRaises(RecordError):
                self.codex(limits={'rateLimits':rates})

    def test_nonchatgpt_provider_missing_credits_or_paid_credits_are_refused(self):
        for account in [{}, {'account':None,'requiresOpenaiAuth':False},
                        {'account':{'type':'apiKey'},'requiresOpenaiAuth':True}]:
            with self.subTest(account=account), self.assertRaises(RecordError):
                self.codex(account=account)
        for credits in [{}, {'hasCredits':True,'unlimited':False},
                        {'hasCredits':False,'unlimited':True}, {'hasCredits':0,'unlimited':0}]:
            with self.subTest(credits=credits), self.assertRaises(RecordError):
                self.codex(limits={'rateLimits':{**self.limits['rateLimits'],'credits':credits}})

    def test_ambiguous_or_extra_credential_routes_fail_closed(self):
        for field in ['api_key_present','unexpected_environment','other_credentials_present']:
            for value in [True,None,0]:
                with self.subTest(field=field,value=value), self.assertRaises(RecordError):
                    self.codex(route={**self.route,field:value})
        for route in [{**self.route,'configured_provider':'minimax'},
                      {**self.route,'native_login_present':False}, {}]:
            with self.subTest(route=route), self.assertRaises(RecordError):
                self.codex(route=route)

    def test_stale_future_or_timezone_free_native_observation_is_refused(self):
        for observed in [(self.now-timedelta(seconds=61)).isoformat(),
                         (self.now+timedelta(seconds=1)).isoformat(), '2026-10-30T16:00:00']:
            with self.subTest(observed=observed), self.assertRaises(RecordError):
                self.codex(observed_at=observed)
            with self.assertRaises(RecordError):
                self.claude(observed_at=observed)

    def test_claude_uses_accepted_admin_review_without_inventing_numeric_allowance(self):
        result = self.claude()
        self.assertEqual(result['provider'],'anthropic')
        self.assertEqual(result['billing_policy'],'seat-cap-admin-review')
        self.assertIsNone(result['numeric_allowance'])
        self.assertEqual(result['reviewed_mtd'],22.18)
        self.assertNotIn('worst_case_loss',result)

    def test_unreviewed_positive_spend_wrong_month_or_changed_cap_are_refused(self):
        for changes in [{'positive_spend_reviewed':False}, {'billing_month':'2026-09'},
                        {'seat_limit':150}, {'source':''}, {'reviewed_mtd':float('nan')},
                        {'reviewed_mtd':75}, {'extra_usage_enabled':None}]:
            with self.subTest(changes=changes), self.assertRaises(RecordError):
                self.claude(review={**self.review,**changes})

    def test_claude_authentication_and_clean_route_are_required_every_time(self):
        for auth in [{}, {'loggedIn':False}, {'loggedIn':1}]:
            with self.subTest(auth=auth), self.assertRaises(RecordError):
                self.claude(auth=auth)
        with self.assertRaises(RecordError):
            self.claude(route={**self.route,'configured_provider':'anthropic','api_key_present':True})


if __name__ == '__main__':
    unittest.main()
