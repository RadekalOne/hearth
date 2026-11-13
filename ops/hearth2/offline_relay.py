"""Disabled-by-default deterministic relay; no native/model/account launch port."""
import argparse
import hashlib
from dataclasses import dataclass
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import sys


def verify_install():
    program=Path(__file__).resolve().parent
    if program.name!='program':return # Source test harness, not an installed controller.
    root=Path(os.environ.get('LOCALAPPDATA',''))/'Hearth/OfflineRelay'
    if program!=root/'program' or root.resolve()!=root.absolute():raise RuntimeError('private installation path differs')
    manifest_file=root/'manifest.json'
    if manifest_file.stat().st_size>32768:raise RuntimeError('bounded controller manifest required')
    manifest=json.loads(manifest_file.read_text(encoding='utf-8-sig'))
    files={'offline_relay.py','offline_relay_state.py','offline_relay_ports.py','offline_relay_windows.py','pause-offline-relay.ps1','relay_matrix.py','relay_native.py','relay_launch.py','relay_live.py'}
    if (manifest.get('host')!=os.environ.get('COMPUTERNAME') or manifest.get('task')!='Hearth-Codex-Offline-Relay'
        or set(manifest.get('source_hashes',{}))!=files):raise RuntimeError('controller binding differs')
    for name in files:
        path=program/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=manifest['source_hashes'][name]:
            raise RuntimeError('installed source differs; refuse execution')
    recovery=manifest.get('recovery_hashes',{})
    if set(recovery)!={'offline_relay_pause.py'}:raise RuntimeError('recovery binding differs')
    path=root/'recovery/offline_relay_pause.py'
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=recovery['offline_relay_pause.py']:
        raise RuntimeError('installed recovery differs; refuse execution')


verify_install()
sys.path.insert(0,str(Path(__file__).resolve().parent))
from offline_relay_state import State

ROOM='!0SCHqdoKZOs53xq1DH4zTL0SLz4aKiD16y7Wo7xnIG0'
THREAD='$f13r0i8hHq1yC_HB9hLoVyLJuSp_-6PUGiGFPrzIV7I'
HOST='RSLABINSKI-PC'


@dataclass(frozen=True)
class Approval:
    room:str
    thread:str
    sender:str
    work_id:str
    generation:int
    base_commit:str
    paths:tuple
    event_id:str
    source:str
    aliases:tuple=()
    review_event:str=''


@dataclass(frozen=True)
class PostReceipt:
    room:str
    thread:str
    sender:str
    event_id:str
    body_sha256:str
    source:str


def admit(work,proof,*,acceptance=False):
    keys={'work_id','aliases','generation','review_event','base_commit','paths','scope'}
    if type(work) is not dict or set(work)!=keys or type(proof) is not Approval:raise ValueError('unverified work')
    def ident(v):return type(v) is str and re.fullmatch(r'[A-Za-z0-9_-]{1,128}',v)
    if (not ident(work['work_id']) or type(work['generation']) is not int or not 1<=work['generation']<=10000
        or type(work['base_commit']) is not str or not re.fullmatch('[0-9a-f]{40}',work['base_commit'])
        or type(work['review_event']) is not str or not work['review_event'].startswith('$')
        or len(work['review_event'])>200 or work['scope']!='hearth2-offline'
        or type(work['aliases']) is not list or len(work['aliases'])>16 or not all(ident(x) for x in work['aliases'])
        or type(work['paths']) is not list or not 1<=len(work['paths'])<=32):raise ValueError('bounded work required')
    for p in work['paths']:
        if (type(p) is not str or len(p)>240 or not re.fullmatch(r'[A-Za-z0-9_./-]+',p)
            or '..' in p.split('/') or not p.startswith(('mcp/memory/hearth2/','test/test_hearth2_','docs/hearth2/'))
            or not p.endswith(('.py','.md','.json')) or p.rsplit('/',1)[-1].startswith('.')
            or any(x in p.lower() for x in ['credential','minimax','mcode','source_map','/.git'])):
            raise ValueError('path outside approved offline scope')
    if (proof.room!=ROOM or proof.thread!=THREAD or proof.sender!='@rad:hearth.radekal.me'
        or proof.work_id!=work['work_id'] or proof.generation!=work['generation']
        or proof.base_commit!=work['base_commit'] or proof.paths!=tuple(work['paths'])
        or proof.aliases!=tuple(work['aliases']) or proof.review_event!=work['review_event']
        or type(proof.event_id) is not str or not proof.event_id.startswith('$') or len(proof.event_id)>200
        or proof.source!=('fixture' if acceptance else 'server_authenticated')):raise ValueError('approval differs')
    return {**json.loads(json.dumps(work)),'kind':'trial','approval_event':proof.event_id}


class GateUnavailable(RuntimeError):pass


class Dispatcher:
    def __init__(self,state,ports,*,acceptance=False,clock=None):
        self.state,self.ports,self.acceptance=state,ports,acceptance
        self.clock=clock or (lambda:datetime.now(timezone.utc))

    def _allowed_time(self):
        from zoneinfo import ZoneInfo,ZoneInfoNotFoundError
        now=self.clock()
        try:local=now.astimezone(ZoneInfo('America/New_York'))
        except ZoneInfoNotFoundError:
            if os.name!='nt':raise GateUnavailable('timezone_unavailable') from None
            local=now.astimezone() # Live host port separately verifies Eastern Standard Time.
        return 7<=local.hour<=23

    def _post(self):
        row=self.state.take_post()
        if row:
            try:
                event=self.ports.post(ROOM,THREAD,row['body'])
                if type(event) is str and event.startswith('$') and len(event)<=200:self.state.posted(row['id'],event)
            except Exception:pass # Uncertain send is never blindly replayed.

    def reconcile_post(self,ident,proof):
        if (type(proof) is not PostReceipt or proof.room!=ROOM or proof.thread!=THREAD
            or proof.sender!='@codex:hearth.radekal.me'
            or proof.source!=('fixture' if self.acceptance else 'server_authenticated')
            or type(proof.event_id) is not str or not proof.event_id.startswith('$') or len(proof.event_id)>200):return False
        return self.state.reconcile_post(ident,proof.body_sha256,proof.event_id)

    def _message(self,job,state,usage):
        prefix='[STATUS]' if state=='complete' else '[BLOCKED]'
        return (f'{prefix} I finished the offline relay attempt for {job["work_id"]}. '
            f'The result is {state}; independent review or the required human decision is next.\n'
            +json.dumps({'job':job['id'],'generation':job['generation'],'base_commit':job['base_commit'],
                'seat_usage':usage,'execution':'synthetic' if self.acceptance else 'unattended',
                'understanding':'unknown','human_acceptance':False},sort_keys=True))

    def check(self):
        at=self.clock().astimezone(timezone.utc).isoformat()
        control=self.state.control()
        if control['paused']:
            self.state.tick(at,control['status']);return {'state':control['status'],'launched':False}
        if not self.acceptance and not self.ports.host_ok():raise GateUnavailable('host_binding_unverified')
        if not self._allowed_time():self.state.tick(at,'outside_window');return {'state':'outside_window'}
        self._post() # Recover known-unsent durable receipts before any new claim.
        active=[j for j in self.state.jobs() if j['state'] in {'claimed','dispatching','active','held'}]
        if active:
            status='held' if any(j['state']=='held' for j in active) else 'active_or_unresolved'
            self.state.tick(at,status);return {'state':status,'launched':False}
        try:events=self.ports.poll()
        except Exception:
            self.state.notice('coordination_unavailable','[BLOCKED] I could not read the authorized coordination source. '
                'A verified controller adapter is required before work can proceed. seat_usage=unavailable; worker_launches=0.')
            self._post();self.state.tick(at,'blocked');return {'state':'blocked','launched':False}
        if type(events) is not list or len(events)>100:raise GateUnavailable('bounded_poll_unavailable')
        ready=getattr(self.ports,'ready_for_claim',None)
        if ready is not None and not ready():
            status=self.ports.poll_status();self.state.tick(at,status);return {'state':status,'launched':False,'pending':len(events)}
        for work in events:
            try:
                approved=admit(work,self.ports.verify(work),acceptance=self.acceptance)
                if self.ports.base_commit()!=approved['base_commit']:continue
            except Exception:continue # Untrusted room text never authorizes or creates new work.
            job=self.state.claim(approved)
            if not job:continue
            usage={'state':'unavailable','actual_charge':None}
            receipt={'confirmed_empty':True,'reason':'included_allowance_unverified'};status='blocked'
            try:
                e=self.ports.allowance()
                good=(type(e) is dict and set(e)=={'source','included_only','fresh','fallback'}
                    and e['included_only'] is True and e['fresh'] is True and e['fallback'] is False
                    and e['source']==('fixture' if self.acceptance else 'verified_included_route'))
                if good and self.state.dispatch(job):
                    receipt={'confirmed_empty':False,'reason':'dispatch_outcome_unknown'}
                    result=self.ports.launch(job)
                    if (type(result) is not dict or result.get('confirmed_empty') is not True
                        or type(result.get('exit_code')) is not int):raise GateUnavailable('unconfirmed_stop')
                    status='complete' if result['exit_code']==0 else 'blocked'
                    receipt={'confirmed_empty':True,'exit_code':result['exit_code'],'reason':'bounded_run_ended'}
                    if self.acceptance:usage={'state':'synthetic','actual_charge':None}
            except BaseException as error:
                if not receipt['confirmed_empty']:
                    try:receipt['confirmed_empty']=self.ports.stop(job) is True
                    except BaseException:pass
                status='held' if receipt['reason']=='dispatch_outcome_unknown' or not receipt['confirmed_empty'] else 'blocked'
                self.state.finish(job,status,receipt,self._message(job,status,usage));self._post()
                if not isinstance(error,Exception):raise
                self.state.tick(at,status);return {'state':status,'launched':False}
            if not self.state.finish(job,status,receipt,self._message(job,status,usage)):
                return {'state':self.state.control()['status'],'launched':False}
            self._post()
            self.state.tick(at,status);return {'state':status,'launched':status=='complete'}
        self.state.tick(at,'idle');return {'state':'idle','launched':False}

    def pause(self):
        jobs=self.state.pause();confirmed={}
        for job in jobs:
            try:confirmed[job['id']]=self.ports.stop(job) is True
            except BaseException:confirmed[job['id']]=False
        # The persisted latch already blocks claims. Stop workloads before a
        # potentially slow scheduler query; disable still runs after stop errors.
        try:disabled=self.ports.disable() is True
        except BaseException:disabled=False
        result=self.state.paused_result(jobs,confirmed,disabled)
        return {'state':result,'scheduler_disabled':disabled,'stops':confirmed}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['check','pause','status','diagnose'])
    parser.add_argument('--state',type=Path,required=True)
    args=parser.parse_args()
    from offline_relay_ports import HostPorts
    ports=HostPorts()
    if args.command=='check' and not ports.host_ok():raise GateUnavailable('host_binding_unverified')
    if args.command=='pause' and not ports.host_identity():raise GateUnavailable('host_binding_unverified')
    state=State(args.state);runner=Dispatcher(state,HostPorts(state))
    if args.command=='status':result={'control':state.control(),'jobs':state.jobs(),'outbox':state.outbox()}
    elif args.command=='diagnose':
        live=runner.ports.live(diagnostic=True);live.bootstrap();live.poll();result=live.last
    else:result=getattr(runner,args.command)()
    print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
