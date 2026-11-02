"""Typed timer readback through PRIVATE fake busctl, no real system bus."""
from datetime import datetime,timedelta,timezone
import copy
import importlib
import json
from pathlib import Path
import sys
import unittest
import test_hearth2_creation_binding as fixtures
from hearth2.store import RecordError
from hearth2.root_commands import BoundedCommand


class TimerReadbackTests(unittest.TestCase):
    def setUp(self):
        fixtures.CreationBindingTests.setUp(self)
        self.binding=self.bindings.bind(self.registration,self.claim,host_id='1'*64,container_id='b'*64)
        self.assertIsNotNone(importlib.util.find_spec('hearth2.timer_readback'),'typed original timer readback missing')
        self.module=importlib.import_module('hearth2.timer_readback')
        self.guard=self.binding['guard_id']
        from hearth2.store import timestamp
        deadline=timestamp(self.binding['deadline_at']).astimezone(timezone.utc)
        delta=deadline-datetime(1970,1,1,tzinfo=timezone.utc)
        self.usec=(delta.days*86400+delta.seconds)*1000000+delta.microseconds
        self.calendar=deadline.strftime('%Y-%m-%d %H:%M:%S')+('.%06d'%deadline.microsecond if deadline.microsecond else '')+' UTC'
        unit=lambda name,active,sub,invocation:{'Id':['s',name],'LoadState':['s','loaded'],
            'ActiveState':['s',active],'SubState':['s',sub],'Transient':['b',True],'InvocationID':['ay',invocation]}
        self.state={'timer_unit':unit(self.guard+'.timer','active','waiting',[1]*16),
            'service_unit':unit(self.guard+'.service','inactive','dead',[]),
            'timer':{'Unit':['s',self.guard+'.service'],
                'TimersMonotonic':['a(stt)',[]],
                'TimersCalendar':['a(sst)',[['OnCalendar',self.calendar,self.usec]]],
                'NextElapseUSecRealtime':['t',self.usec],'NextElapseUSecMonotonic':['t',0],
                'LastTriggerUSec':['t',0],'Result':['s','success'],'AccuracyUSec':['t',1000],
                'RandomizedDelayUSec':['t',0],'Persistent':['b',False],
                'OnClockChange':['b',False],'OnTimezoneChange':['b',False],'RemainAfterElapse':['b',True]},
            'exit':0}
        self.file=Path(self.tmp.name)/'bus-state.json';self.calls=Path(self.tmp.name)/'bus-calls.jsonl'
        self.file.write_text(json.dumps(self.state))
        script=Path(self.tmp.name)/'fake-busctl'
        script.write_text('#!'+sys.executable+'\nimport json,sys\nfrom pathlib import Path\ns=json.loads(Path('+repr(str(self.file))+').read_text())\na=sys.argv[1:]\nwith open('+repr(str(self.calls))+',"a") as f:f.write(json.dumps(a)+"\\n")\nif s["exit"]:sys.exit(s["exit"])\nif "call" in a:\n print(json.dumps({"type":"o","data":["/org/freedesktop/systemd1/unit/"+("timer" if a[-1].endswith(".timer") else "service")]}))\nelse:\n i=a.index("get-property");path=a[i+2];interface=a[i+3]\n fields=s["timer"] if interface.endswith(".Timer") else s["timer_unit" if path.endswith("/timer") else "service_unit"]\n for p in a[i+4:]:\n  t,v=fields[p];print(json.dumps({"type":t,"data":v}))\n')
        script.chmod(0o700)
        self.port=self.module.SystemdTimerProperties(BoundedCommand(script,timeout_seconds=1,max_output=16384))
        self.host='1'*64
        self.reader=self.module.RootTimerReadback(self.port,host_identity=lambda:self.host,clock=lambda:self.time)

    def change(self,section,key,value):
        self.state[section][key][1]=value;self.file.write_text(json.dumps(self.state))

    def read(self):return self.reader.inspect(self.binding)

    def test_exact_original_microsecond_deadline_and_target_match_without_mutating_units(self):
        proof=self.read()
        self.assertEqual(proof['deadline_at'],self.binding['deadline_at'])
        self.assertEqual(proof['timer_state'],'armed');self.assertEqual(proof['guard_id'],self.guard)
        calls=[json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertTrue(all('get-property' in call or 'GetUnit' in call for call in calls))
        self.assertTrue(all('StartUnit' not in call and 'LoadUnit' not in call and 'stop' not in call for call in calls))
        self.assertFalse(any('Environment' in call or 'ExecStart' in call for call in calls))

    def test_later_deadline_is_not_accepted_as_equivalent_guard(self):
        self.change('timer','NextElapseUSecRealtime',self.usec+1)
        with self.assertRaises(RecordError):self.read()

    def test_calendar_must_be_single_absolute_original_utc_time(self):
        self.change('timer','TimersCalendar',[['OnCalendar','*-*-* 00:00:00 UTC',self.usec]])
        with self.assertRaises(RecordError):self.read()
        self.change('timer','TimersCalendar',[['OnCalendar',self.calendar,self.usec],['OnCalendar',self.calendar,self.usec]])
        with self.assertRaises(RecordError):self.read()

    def test_extra_monotonic_or_clock_triggers_are_refused(self):
        self.change('timer','TimersMonotonic',[['OnActiveUSec',1000,1000]])
        with self.assertRaises(RecordError):self.read()
        self.change('timer','TimersMonotonic',[]);self.change('timer','OnClockChange',True)
        with self.assertRaises(RecordError):self.read()

    def test_wrong_trigger_service_cannot_authorize_start(self):
        self.change('timer','Unit','unrelated.service')
        with self.assertRaises(RecordError):self.read()

    def test_nontransient_alias_or_inactive_timer_is_refused(self):
        self.change('timer_unit','Transient',False)
        with self.assertRaises(RecordError):self.read()
        self.change('timer_unit','Transient',True);self.change('timer_unit','Id','alias.timer')
        with self.assertRaises(RecordError):self.read()
        self.change('timer_unit','Id',self.guard+'.timer');self.change('timer_unit','ActiveState','inactive')
        with self.assertRaises(RecordError):self.read()

    def test_already_running_guard_service_or_triggered_timer_refuses(self):
        self.change('service_unit','ActiveState','active')
        with self.assertRaises(RecordError):self.read()
        self.change('service_unit','ActiveState','inactive');self.change('timer','LastTriggerUSec',1)
        with self.assertRaises(RecordError):self.read()

    def test_random_delay_or_relaxed_accuracy_is_not_silently_tolerated(self):
        self.change('timer','RandomizedDelayUSec',1000)
        with self.assertRaises(RecordError):self.read()
        self.change('timer','RandomizedDelayUSec',0);self.change('timer','AccuracyUSec',1000000)
        with self.assertRaises(RecordError):self.read()

    def test_json_type_mismatch_and_bool_timestamp_are_refused(self):
        self.state['timer']['NextElapseUSecRealtime']=['s',str(self.usec)];self.file.write_text(json.dumps(self.state))
        with self.assertRaises(RecordError):self.read()
        self.state['timer']['NextElapseUSecRealtime']=['t',True];self.file.write_text(json.dumps(self.state))
        with self.assertRaises(RecordError):self.read()

    def test_failed_property_query_is_not_an_armed_timer(self):
        self.state['exit']=2;self.file.write_text(json.dumps(self.state))
        with self.assertRaises(RecordError):self.read()

    def test_new_host_cannot_verify_original_timer(self):
        self.host='2'*64
        with self.assertRaises(RecordError):self.read()
        self.assertFalse(self.calls.exists())

    def test_expired_sealed_deadline_cannot_be_rebased_to_now(self):
        self.time+=timedelta(hours=3)
        with self.assertRaises(RecordError):self.read()
        self.assertFalse(self.calls.exists())

    def test_changed_invocation_between_snapshots_is_refused(self):
        original=self.port.snapshot;seen=[]
        def changed(guard):
            value=original(guard);seen.append(value)
            if len(seen)==1:self.change('timer_unit','InvocationID',[2]*16)
            return value
        self.port.snapshot=changed
        with self.assertRaises(RecordError):self.read()

    def test_host_or_deadline_change_during_readback_is_refused(self):
        original=self.port.snapshot
        def changed(guard):
            value=original(guard);self.time+=timedelta(hours=3);return value
        self.port.snapshot=changed
        with self.assertRaises(RecordError):self.read()

    def test_timer_only_proof_cannot_replace_full_guard_and_container_attestation(self):
        proof=self.read();before=self.store.snapshot()
        with self.assertRaises(RecordError):self.bindings.consume_armed(self.claim,self.binding,proof=proof)
        self.assertEqual(self.store.snapshot(),before)

    def test_invalid_guard_id_is_refused_before_any_helper_execution(self):
        for guard in ['other.timer','--all','hearth2-deadline-'+'a'*63]:
            with self.subTest(guard=guard),self.assertRaises(RecordError):self.port.snapshot(guard)
        self.assertFalse(self.calls.exists())

    def test_untyped_injected_snapshot_cannot_exploit_bool_integer_equality(self):
        original=self.port.snapshot
        def wrong(guard):
            value=original(guard)
            value['timer']['LastTriggerUSec']=False
            value['timer']['OnClockChange']=0
            return value
        self.port.snapshot=wrong
        with self.assertRaises(RecordError):self.read()


if __name__=='__main__':unittest.main()
