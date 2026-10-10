"""Round-one regressions: declared monitors, durable attention and lifecycle."""
import unittest
from test.test_dashboard_slice import dashboard

NOW=1791507600
REGISTRY=[{'id':'watcher_sweep','agent':'claude','surface':'desktop (auto)',
           'monitor':'hourly-room-sweep','cadence_minutes':60,'active':True,'kind':'recurring',
           'receipt_monitors':['hourly-room-sweep-runner']}]


class DashboardRoundOneTests(unittest.TestCase):
    def checkpoint(self, cid, monitor, at='2026-10-09T01:00:00Z', content='{}', surface='desktop (auto)'):
        return (cid,{'agent':'claude','surface':surface,'monitor':monitor,'updated_at':at},content)

    def watchers(self, rows, registry=REGISTRY):
        self.assertTrue(hasattr(dashboard,'watchers'),'Declared watcher projection is missing')
        return dashboard.watchers(rows,registry,NOW)

    def test_runner_failure_folds_into_parent_and_cites_both_receipts(self):
        rows=[self.checkpoint('checkpoint_parent','hourly-room-sweep','2026-10-04T01:00:00Z'),
              self.checkpoint('checkpoint_runner','hourly-room-sweep-runner',content='{"process_exit":1,"secret":"hidden"}')]
        result=self.watchers(rows)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['monitor'],'hourly-room-sweep')
        self.assertEqual(result[0]['state'],'failed')
        self.assertEqual(result[0]['source_refs'],['checkpoint_parent','checkpoint_runner'])
        self.assertNotIn('hidden',str(result))

    def test_undeclared_hourly_retired_surface_and_probe_are_not_watchers(self):
        rows=[self.checkpoint('checkpoint_probe','hourly-room-sweep-probe',content='process_exit=1'),
              self.checkpoint('checkpoint_legacy','hourly-room-sweep',surface='desktop'),
              self.checkpoint('checkpoint_unknown','hourly-new-monitor')]
        result=self.watchers(rows)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['state'],'unknown')
        self.assertEqual(result[0]['source_refs'],['watcher_sweep'])

    def test_inactive_and_one_shot_declarations_are_excluded(self):
        registry=[{**REGISTRY[0],'active':False},{**REGISTRY[0],'id':'one','kind':'one-shot'}]
        self.assertEqual(self.watchers([],registry),[])

    def test_missing_declared_cadence_never_becomes_late(self):
        result=self.watchers([self.checkpoint('checkpoint_parent','hourly-room-sweep','2020-01-01')],
                             [{**REGISTRY[0],'cadence_minutes':None}])
        self.assertEqual(result,[])

    def test_failed_runner_is_not_hidden_by_newer_parent_closeout(self):
        rows=[self.checkpoint('checkpoint_runner','hourly-room-sweep-runner','2026-10-09T00:00:00Z','process_exit=1'),
              self.checkpoint('checkpoint_parent','hourly-room-sweep',content='process_exit=0')]
        self.assertEqual(self.watchers(rows)[0]['state'],'failed')

    def test_latest_runner_success_clears_earlier_failure(self):
        rows=[self.checkpoint('checkpoint_old','hourly-room-sweep-runner','2026-10-09T00:00:00Z','process_exit=1'),
              self.checkpoint('checkpoint_new','hourly-room-sweep-runner',content='process_exit=0 closeout_verified=true')]
        self.assertEqual(self.watchers(rows)[0]['state'],'ok')

    def test_event_driven_declaration_is_exempt_from_elapsed_time(self):
        registry=[{**REGISTRY[0],'kind':'event-driven','cadence_minutes':None}]
        self.assertEqual(self.watchers([self.checkpoint('checkpoint_parent','hourly-room-sweep','2020-01-01')],registry)[0]['state'],'on-demand')

    def test_failed_watchers_and_queues_strictly_over_three_days_reach_inbox(self):
        self.assertTrue(hasattr(dashboard,'attention_inbox'),'Durable inbox projection is missing')
        watcher={'state':'failed','agent':'claude','surface':'desktop','monitor':'sweep','source_refs':['checkpoint_fail'],'age_minutes':2}
        work=[{'id':'relay_old','state':'queued','age_minutes':4320.01,'title':'Old handoff','source_refs':['relay_old']},
              {'id':'task_edge','state':'queued','age_minutes':4320,'source_refs':['task_edge']},
              {'id':'relay_done','state':'done','age_minutes':9999,'source_refs':['relay_done']}]
        result=dashboard.attention_inbox({'items':[]},[watcher],work)
        self.assertEqual([i['kind'] for i in result['items']],['failed_watcher','overdue_work'])
        self.assertEqual(result['total'],2)
        self.assertEqual(result['items'][1]['source_refs'],['relay_old'])

    def test_relay_summaries_and_open_before_done(self):
        relays=[{'relay_id':'relay_done','state':'resolved','request':'Closed request'},
                {'relay_id':'relay_design','state':'queued','request':'Review the dashboard design'},
                {'relay_id':'relay_auth','state':'queued','request':'Investigate authorization'},
                {'relay_id':'relay_empty','state':'queued','target_agent':'codex'}]
        result=dashboard.work_items({},relays,NOW)
        self.assertEqual(result[-1]['state'],'done')
        self.assertEqual(len(set(i['title'] for i in result)),4)
        self.assertIn('dashboard design',next(i['title'] for i in result if i['id']=='relay_design'))
