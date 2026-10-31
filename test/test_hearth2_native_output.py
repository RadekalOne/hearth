"""Native output is bounded data, never launch or successful-exit authority."""
import importlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
from hearth2.store import RecordError


class OutputFixture:
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.native_output'),
                             'bounded native output adapter is not implemented')
        self.module=importlib.import_module('hearth2.native_output')


class NativeOutputTests(OutputFixture,unittest.TestCase):
    def test_split_utf8_lines_and_last_record_without_newline(self):
        stream=self.module.JsonLines()
        raw='{"text":"café"}\n{"id":2}'.encode()
        split=raw.index(b'\xc3')+1
        self.assertEqual(stream.feed(raw[:split]),[])
        self.assertEqual(stream.feed(raw[split:]),[{'text':'café'}])
        self.assertEqual(stream.finish(),[{'id':2}])
        with self.assertRaises(RecordError):stream.feed(b'{}\n')

    def test_duplicate_fields_nonfinite_values_and_nonobjects_are_refused(self):
        for raw in [b'{"id":1,"id":2}\n',b'{"n":NaN}\n',b'{"n":Infinity}\n',
                    b'[]\n',b'null\n',b'{"nested":{"x":1,"x":2}}\n',
                    b'{"text":"\xff"}\n',b'{"text":"\\ud800"}\n']:
            with self.subTest(raw=raw),self.assertRaises(RecordError):
                self.module.JsonLines().feed(raw)

    def test_line_total_and_record_limits_fail_closed(self):
        for options,chunks in [({'max_line':8},[b'{"text":"too long"}\n']),
                               ({'max_total':8},[b'{}\n',b'{}\n',b'{}\n']),
                               ({'max_records':2},[b'{}\n{}\n{}\n'])]:
            stream=self.module.JsonLines(**options)
            with self.subTest(options=options),self.assertRaises(RecordError):
                for chunk in chunks:stream.feed(chunk)
            with self.assertRaises(RecordError):stream.finish()

    def test_truncated_record_and_excessive_depth_are_refused(self):
        stream=self.module.JsonLines();stream.feed(b'{"unfinished":')
        with self.assertRaises(RecordError):stream.finish()
        deep=b'{"value":'*40+b'0'+b'}'*40+b'\n'
        with self.assertRaises(RecordError):self.module.JsonLines().feed(deep)

    def test_invalid_output_does_not_echo_private_data_or_accept_later_success(self):
        stream=self.module.JsonLines()
        with self.assertRaises(RecordError) as caught:stream.feed(b'private-auth-diagnostic\n')
        self.assertNotIn('private-auth-diagnostic',str(caught.exception))
        with self.assertRaises(RecordError):stream.feed(b'{"success":true}\n')

    def test_stream_poisoning_cannot_leave_a_previous_completed_result(self):
        self.assertTrue(hasattr(self.module,'NativeStream'),'native stream integration is not implemented')
        stream=self.module.NativeStream('claude',session_id='session-one')
        stream.feed(json.dumps({'type':'result','subtype':'success','is_error':False,
                    'session_id':'session-one','result':'answer'}).encode()+b'\n')
        self.assertEqual(stream.outcome()['state'],'completed')
        with self.assertRaises(RecordError):stream.feed(b'{"bad":"\xff"}\n')
        self.assertEqual(stream.outcome()['state'],'unknown')

    def test_typed_stop_survives_malformed_tail_at_every_chunk_partition(self):
        cases=[('claude',{'session_id':'session-one'},
                {'type':'system','subtype':'api_retry','session_id':'session-one',
                 'error_status':401,'error':'authentication_failed'},'authentication_stop'),
               ('codex',{'thread_id':'thread-one','turn_id':'turn-one'},
                {'method':'error','params':{'threadId':'thread-one','turnId':'turn-one',
                 'error':{'codexErrorInfo':'usageLimitExceeded'},'willRetry':True}},'allowance_stop')]
        for provider,identity,event,reason in cases:
            raw=json.dumps(event).encode()+b'\nnot json\n'
            for split in range(len(raw)+1):
                stream=self.module.NativeStream(provider,**identity)
                with self.assertRaises(RecordError):
                    stream.feed(raw[:split]);stream.feed(raw[split:]);stream.finish()
                result=stream.outcome()
                self.assertEqual(result['state'],'unknown')
                self.assertTrue(result['pause_role'],(provider,split))
                self.assertEqual(result['stop_reason'],reason)

    def test_typed_stop_survives_a_later_output_budget_violation_in_the_same_read(self):
        stream=self.module.NativeStream('claude',session_id='session-one')
        stream.decoder=self.module.JsonLines(max_total=1024,max_line=512)
        event={'type':'system','subtype':'api_retry','session_id':'session-one','error_status':429}
        with self.assertRaises(RecordError):stream.feed(json.dumps(event).encode()+b'\n'+b'x'*2000)
        self.assertTrue(stream.outcome()['pause_role'])
        self.assertEqual(stream.outcome()['stop_reason'],'rate_limit_stop')


class CodexTurnTests(OutputFixture,unittest.TestCase):
    def turn(self):return self.module.CodexTurn(thread_id='thread-one',turn_id='turn-one')

    @staticmethod
    def item(text,phase='final_answer',identity='answer'):
        return {'id':identity,'type':'agentMessage','text':text,'phase':phase}

    def completed(self,items=None,status='completed',error=None):
        return {'method':'turn/completed','params':{'threadId':'thread-one',
            'turn':{'id':'turn-one','status':status,'items':items or [],'error':error}}}

    def test_commentary_is_not_the_final_result_and_missing_usage_stays_unknown(self):
        turn=self.turn()
        turn.accept({'method':'item/completed','params':{'threadId':'thread-one',
            'turnId':'turn-one','item':self.item('working','commentary','progress')}})
        final=self.item('{"status":"done"}')
        turn.accept(self.completed([final]))
        result=turn.outcome()
        self.assertEqual(result['state'],'completed')
        self.assertEqual(result['text'],'{"status":"done"}')
        self.assertEqual(result['usage'],{'state':'unknown','units':None,
                         'estimated_cost':None,'actual_charge':None})
        self.assertNotIn('exit_status',result)

    def test_cumulative_native_tokens_are_reported_once_without_invented_charge(self):
        turn=self.turn()
        units={'inputTokens':20,'outputTokens':4,'totalTokens':24,
               'cachedInputTokens':3,'reasoningOutputTokens':1}
        event={'method':'thread/tokenUsage/updated','params':{
            'threadId':'thread-one','turnId':'turn-one','tokenUsage':{
                'total':units,'last':units,'modelContextWindow':100000}}}
        turn.accept(event);turn.accept(event)
        turn.accept(self.completed([self.item('result')]))
        usage=turn.outcome()['usage']
        self.assertEqual(usage['state'],'measured')
        self.assertEqual(usage['units']['totalTokens'],24)
        self.assertIsNone(usage['actual_charge'])

    def test_foreign_thread_and_turn_cannot_supply_result_usage_or_allowance_stop(self):
        turn=self.turn()
        for event in [self.completed([self.item('foreign')]),
                      {'method':'error','params':{'threadId':'thread-one','turnId':'turn-one',
                       'error':{'message':'limit','codexErrorInfo':'usageLimitExceeded'},'willRetry':False}}]:
            for field,value in [('threadId','other-thread'),('turnId','other-turn')]:
                changed=json.loads(json.dumps(event))
                if field=='turnId' and 'turn' in changed['params']:
                    changed['params']['turn']['id']=value
                else:changed['params'][field]=value
                turn.accept(changed)
        self.assertEqual(turn.outcome()['state'],'unknown')
        self.assertFalse(turn.outcome()['pause_role'])

    def test_allowance_stop_is_typed_and_sticky_even_if_cli_says_it_will_retry(self):
        turn=self.turn()
        turn.accept({'method':'error','params':{'threadId':'thread-one','turnId':'turn-one',
            'error':{'message':'native diagnostic','codexErrorInfo':'usageLimitExceeded'},'willRetry':True}})
        turn.accept(self.completed([self.item('later result')]))
        self.assertEqual(turn.outcome()['state'],'allowance_stop')
        self.assertTrue(turn.outcome()['pause_role'])
        self.assertNotIn('native diagnostic',str(turn.outcome()))

    def test_quoted_error_text_cannot_pause_a_role(self):
        turn=self.turn();turn.accept(self.completed([self.item('usageLimitExceeded')]))
        self.assertEqual(turn.outcome()['state'],'completed')
        self.assertFalse(turn.outcome()['pause_role'])

    def test_missing_completion_failed_or_interrupted_output_is_never_success(self):
        self.assertEqual(self.turn().outcome()['state'],'unknown')
        for status,want in [('completed','unknown'),('failed','failed'),('interrupted','interrupted')]:
            turn=self.turn();turn.accept(self.completed(status=status))
            self.assertEqual(turn.outcome()['state'],want)

    def test_invalid_usage_or_conflicting_terminal_output_poison_the_turn(self):
        for invalid in [True,-1,1.5,2**63, '4']:
            turn=self.turn()
            units={'inputTokens':20,'outputTokens':4,'totalTokens':invalid,
                   'cachedInputTokens':3,'reasoningOutputTokens':1}
            with self.subTest(invalid=invalid),self.assertRaises(RecordError):
                turn.accept({'method':'thread/tokenUsage/updated','params':{
                    'threadId':'thread-one','turnId':'turn-one','tokenUsage':{'total':units,'last':units}}})
            self.assertEqual(turn.outcome()['state'],'unknown')
        turn=self.turn();turn.accept(self.completed([self.item('first')]))
        with self.assertRaises(RecordError):turn.accept(self.completed([self.item('different')]))
        self.assertEqual(turn.outcome()['state'],'unknown')

    def test_malformed_fields_and_post_completion_changes_never_preserve_success(self):
        for change in [{'status':[]},{'items':[self.item('text',phase=[])]},
                       {'error':{'message':'contradictory native error'}}]:
            turn=self.turn();event=self.completed([self.item('result')])
            event['params']['turn'].update(change)
            with self.subTest(change=change),self.assertRaises(RecordError):turn.accept(event)
            self.assertEqual(turn.outcome()['state'],'unknown')
        turn=self.turn();turn.accept(self.completed([self.item('result')]))
        with self.assertRaises(RecordError):
            turn.accept({'method':'item/completed','params':{'threadId':'thread-one',
                         'turnId':'turn-one','item':self.item('changed',identity='late')}})
        self.assertEqual(turn.outcome()['state'],'unknown')


class ClaudeTurnTests(OutputFixture,unittest.TestCase):
    def setUp(self):
        OutputFixture.setUp(self)
        self.assertTrue(hasattr(self.module,'ClaudeTurn'),'Claude output adapter is not implemented')
    def turn(self):return self.module.ClaudeTurn(session_id='session-one')

    @staticmethod
    def result(**changes):
        value={'type':'result','subtype':'success','is_error':False,
               'session_id':'session-one','result':'final answer'}
        value.update(changes);return value

    def test_success_does_not_invent_missing_usage_or_billing(self):
        turn=self.turn();turn.accept(self.result())
        self.assertEqual(turn.outcome()['state'],'completed')
        self.assertEqual(turn.outcome()['text'],'final answer')
        self.assertEqual(turn.outcome()['usage']['state'],'unknown')
        self.assertIsNone(turn.outcome()['usage']['units'])
        self.assertIsNone(turn.outcome()['usage']['actual_charge'])

    def test_partial_main_loop_counts_do_not_invent_cache_or_complete_totals(self):
        turn=self.turn();turn.accept(self.result(usage={'input_tokens':2,'output_tokens':3}))
        self.assertEqual(turn.outcome()['usage']['units'],{'inputTokens':2,'outputTokens':3})
        self.assertEqual(turn.outcome()['usage_scope'],'main_loop_partial')

    def test_model_totals_include_auxiliary_usage_and_cost_is_only_an_estimate(self):
        turn=self.turn()
        turn.accept(self.result(usage={'input_tokens':1,'output_tokens':1},total_cost_usd=0.02,
            modelUsage={'model-a':{'inputTokens':20,'outputTokens':4,
                'cacheReadInputTokens':3,'cacheCreationInputTokens':2},
                        'model-b':{'inputTokens':10,'outputTokens':1,
                'cacheReadInputTokens':0,'cacheCreationInputTokens':0}}))
        result=turn.outcome()
        self.assertEqual(result['usage_scope'],'query_model_totals')
        self.assertEqual(result['usage']['units']['totalTokens'],40)
        self.assertEqual(result['usage']['estimated_cost']['amount'],0.02)
        self.assertIsNone(result['usage']['actual_charge'])

    def test_observed_native_auth_and_rate_limit_retries_request_immediate_stop(self):
        for status,want in [(401,'authentication_stop'),(403,'authentication_stop'),
                            (429,'rate_limit_stop')]:
            turn=self.turn()
            turn.accept({'type':'system','subtype':'api_retry','session_id':'session-one',
                         'error_status':status,'error':'private diagnostic',
                         'attempt':1,'max_retries':10,'retry_delay_ms':600})
            self.assertEqual(turn.outcome()['state'],want)
            self.assertTrue(turn.outcome()['pause_role'])
            self.assertNotIn('private diagnostic',str(turn.outcome()))

    def test_only_rejected_primary_rate_status_pauses_not_overage_metadata(self):
        turn=self.turn()
        turn.accept({'type':'rate_limit_event','session_id':'session-one',
            'rate_limit_info':{'status':'allowed','overageStatus':'rejected'}})
        self.assertFalse(turn.outcome()['pause_role'])
        turn.accept({'type':'rate_limit_event','session_id':'session-one',
            'rate_limit_info':{'status':'rejected'}})
        turn.accept(self.result())
        self.assertEqual(turn.outcome()['state'],'allowance_stop')
        self.assertTrue(turn.outcome()['pause_role'])

    def test_foreign_or_child_sessions_cannot_finish_or_pause_the_root(self):
        turn=self.turn()
        turn.accept(self.result(session_id='other-session'))
        turn.accept(self.result(parent_tool_use_id='child'))
        turn.accept({'type':'rate_limit_event','session_id':'other-session',
                     'rate_limit_info':{'status':'rejected'}})
        self.assertEqual(turn.outcome()['state'],'unknown')
        self.assertFalse(turn.outcome()['pause_role'])

    def test_error_budget_stop_missing_result_and_local_command_never_complete_a_task(self):
        for fields,want in [({'is_error':True,'subtype':'error_during_execution'},'failed'),
                            ({'is_error':True,'subtype':'error_max_budget_usd'},'budget_stop'),
                            ({'result':''},'unknown'),({'local_command':'context'},'unknown')]:
            turn=self.turn();turn.accept(self.result(**fields))
            self.assertEqual(turn.outcome()['state'],want)
        self.assertEqual(self.turn().outcome()['state'],'unknown')

    def test_malformed_or_conflicting_results_poison_the_session(self):
        for change in [{'is_error':0},{'subtype':[]},{'usage':{'input_tokens':True}},
                       {'total_cost_usd':float('nan')},{'total_cost_usd':True},
                       {'modelUsage':{'model':{'inputTokens':-1}}}]:
            turn=self.turn()
            with self.subTest(change=change),self.assertRaises(RecordError):turn.accept(self.result(**change))
            self.assertEqual(turn.outcome()['state'],'unknown')
        turn=self.turn();turn.accept(self.result())
        with self.assertRaises(RecordError):turn.accept(self.result(result='conflict'))
        self.assertEqual(turn.outcome()['state'],'unknown')


if __name__=='__main__':unittest.main()
