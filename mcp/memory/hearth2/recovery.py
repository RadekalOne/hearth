"""Inactive trusted recovery coordinator; no OS collection or worker authority."""
import hashlib
import json
import re
from .dispatch import validate_os_observation
from .store import RecordError,safe_payload,timestamp,native_receipt_metadata


def _references(value):
    if (not isinstance(value,list) or not 1<=len(value)<=100
            or any(not isinstance(v,str) or not v.strip() or len(v)>4096 for v in value)):
        raise RecordError('bounded root evidence references required')


class RecoveryCoordinator:
    def __init__(self,registry):
        self.registry=registry
        self.store=registry.store
        self.controller=registry.controller

    def recover(self,registration,*,expected_epoch,expected_generation,outcome,proof):
        if (not isinstance(registration,dict) or not isinstance(registration.get('run_id'),str)
                or any(type(v) not in {str,int,type(None)} for v in registration.values())
                or not isinstance(proof,dict) or set(proof)!={'recovery_id','observation','removal','classification_evidence'}
                or not isinstance(outcome,str) or outcome not in {'failed','completed','preserve'}
                or not isinstance(proof['recovery_id'],str)
                or re.fullmatch(r'[A-Za-z0-9_-]{1,128}',proof['recovery_id']) is None):
            raise RecordError('exact root recovery contract required')
        observed,ended=validate_os_observation(proof['observation'])
        osproof=proof['observation'];removal=proof['removal']
        if not isinstance(removal,dict) or set(removal)!={'container_id','workload_id','observed_at','references'}:
            raise RecordError('separate immutable-container absence proof required')
        removed=timestamp(removal['observed_at'])
        _references(removal['references']);_references(proof['classification_evidence'])
        digest=hashlib.sha256(safe_payload({'registration':registration,'restore_epoch':expected_epoch,
            'generation':expected_generation,'outcome':outcome,'proof':proof}).encode()).hexdigest()
        with self.store.transaction() as db:
            epoch=db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
            current=self.registry._owned(self.registry._latest(db),registration['run_id'])
            if not isinstance(expected_epoch,str) or epoch!=expected_epoch:
                raise RecordError('recovery epoch changed since inspection')
            run=self.store.row(db,'runs',current['run_id'])
            claim=self.store.row(db,'claims',run['claim_id'])
            task=self.store.row(db,'tasks',run['task_id'])
            if current['phase']=='released':
                if current.get('recovery_sha256')!=digest:
                    raise RecordError('released recovery replay conflicts')
                return {'run':run,'task':task,'registration':current}
            if (safe_payload(current)!=safe_payload(registration)
                    or current['phase'] not in {'reserved','launching'}
                    or claim['runner']!=self.controller.id or claim['id']!=current['claim_id']
                    or type(expected_generation) is not int or claim['generation']!=expected_generation
                    or claim['generation']<current['generation']
                    or claim['restore_epoch']!=current['restore_epoch']
                    or claim['attempt']!=current['attempt'] or task['attempts']!=claim['attempt']
                    or osproof['workload_id']!=current['workload_id']
                    or removal['workload_id']!=current['workload_id']
                    or removal['container_id']!=osproof['container_id']):
                raise RecordError('recovery owner or workload context changed')
            now=self.store.now()
            if (any(value>now or (now-value).total_seconds()>60 for value in [observed,removed])
                    or observed<timestamp(run['started_at']) or ended is None
                    or not timestamp(run['started_at'])<=ended<=observed
                    or osproof['containment_state']!='verified_empty'
                    or osproof['exit_status'] is None):
                raise RecordError('fresh known termination and removal required')
            metadata=json.loads(run['data']);prior=metadata.get('os_observation')
            if (prior is not None and (not isinstance(prior,dict) or prior.get('container_id')!=osproof['container_id'])
                    or run['exit_status'] is not None and run['exit_status']!=osproof['exit_status']):
                raise RecordError('recovery conflicts with immutable historical evidence')
            if claim['state']=='closed':
                if outcome!='preserve' or task['generation'] not in {claim['generation'],claim['generation']+1}:
                    raise RecordError('closed recovery only preserves current history')
            else:
                if outcome not in {'failed','completed'}:
                    raise RecordError('open recovery requires explicit classification')
                run=self.registry._observe_termination(db,current,expected_epoch=epoch,
                    expected_generation=expected_generation,observation=osproof)
                latest=json.loads(run['data'])['os_observation']
                if latest!={**osproof,'restore_epoch':epoch,'generation':expected_generation,'registration_seq':current['seq']}:
                    raise RecordError('recovery cannot reuse superseded OS observation')
                native_state,_,_=native_receipt_metadata(json.loads(run['data']))
                if outcome=='failed' and native_state=='unknown' and run['exit_status']==0:
                    raise RecordError('zero exit without native outcome remains uncertain')
                references=osproof['termination_evidence']+removal['references']+proof['classification_evidence']
                task=self.store._reconcile(db,self.controller,run['id'],outcome=outcome,termination_evidence=references)
            self.store.audit(db,self.controller,run['id'],'dispatch_recovery',
                {'recovery_id':proof['recovery_id'],'restore_epoch':epoch,
                 'generation':expected_generation,'registration_seq':current['seq'],
                 'outcome':outcome,'sha256':digest,'proof':proof})
            released=self.registry._release(db,run['id'],recovery_sha256=digest)
            return {'run':self.store.row(db,'runs',run['id']),'task':task,'registration':released}
