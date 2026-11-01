"""Inactive outside collector: historical exit facts plus NEW OS queries.

Ports are trusted original-host reads. Process/privilege independence and host
authentication remain deployment gates, not properties proven by Python types.
"""
import hashlib
import time
import uuid
from .creation import _digest
from .root_guard import _identity,_empty_frozen
from .store import RecordError,safe_payload,timestamp


class RootTerminationCollector:
    def __init__(self,files,commands,evidence,*,host_identity,clock,
                 classification_evidence,monotonic=time.monotonic):
        if (not isinstance(classification_evidence,list) or not 1<=len(classification_evidence)<=100
                or any(not isinstance(v,str) or not v.strip() or len(v)>4096 for v in classification_evidence)):
            raise RecordError('bounded explicit root classification references required')
        safe_payload(classification_evidence)
        self.files,self.commands,self.evidence=files,commands,evidence
        self.host_identity,self.clock,self.monotonic=host_identity,clock,monotonic
        self.classification_evidence=tuple(classification_evidence)

    def _known_exit(self,binding,records):
        """Never choose a convenient latest value over conflicting history."""
        if not isinstance(records,list) or len(records)>256:
            raise RecordError('bounded original root evidence required')
        key=hashlib.sha256(safe_payload(binding).encode()).hexdigest()
        facts=set();references=[];now=self.clock();created=timestamp(binding['at'])
        try:
            for record in records:
                if (not isinstance(record,dict)
                        or set(record)!={'version','binding','stage','observation','reference','sha256'}
                        or type(record['version']) is not int or record['version']!=1
                        or safe_payload(record['binding'])!=safe_payload(binding)
                        or not isinstance(record['stage'],str) or record['stage'] not in {'observed','removed'}
                        or not _digest(record['sha256'])
                        or record['reference']!=key+'-'+record['stage']+'-'+record['sha256']+'.json'):
                    raise ValueError('mixed original evidence')
                body={k:record[k] for k in ['version','binding','stage','observation']}
                if hashlib.sha256(safe_payload(body).encode()+b'\n').hexdigest()!=record['sha256']:
                    raise ValueError('evidence checksum changed')
                observation=record['observation'];stage=record['stage']
                fields={'observed_at','exit_status','ended_at'} if stage=='observed' else {'observed_at','verified_empty','immutable_absent'}
                if not isinstance(observation,dict) or set(observation)!=fields:
                    raise ValueError('unexpected historical fields')
                observed=timestamp(observation['observed_at'])
                if not created<=observed<=now:raise ValueError('historical time impossible')
                if stage=='removed':
                    if observation['verified_empty'] is not True or observation['immutable_absent'] is not True:
                        raise ValueError('historical removal unknown')
                    continue  # NEVER use historical empty/removal as current proof.
                code=observation['exit_status'];ended=observation['ended_at']
                if code is None:
                    if ended is not None:raise ValueError('unknown exit invented end')
                    continue
                if type(code) is not int or not -(1<<63)<=code<(1<<63) or ended is None:
                    raise ValueError('historical exit invalid')
                end=timestamp(ended)
                if not created<=end<=observed:raise ValueError('historical end invalid')
                facts.add((code,end));references.append(record['sha256'])
            if len(facts)>1:raise ValueError('conflicting known original exit/end')
        except (ValueError,TypeError,KeyError,RecursionError):
            raise RecordError('original root exit evidence invalid or conflicting') from None
        if not facts:return None,None,[]
        code,end=next(iter(facts))
        return code,end.isoformat(),['root-evidence:'+min(references)]

    def inspect_termination(self,binding):
        """Read only. Caller captures registration/epoch/generation BEFORE this.

        This function cannot classify a task, mutate the record, kill/remove a
        workload or disarm a guard. Strict recovery decides what can be released.
        """
        try:return self._inspect(binding)
        except RecordError:raise
        except Exception:
            raise RecordError('outside original-host observation unavailable') from None

    def _inspect(self,binding):
        start=self.clock();started=self.monotonic()
        _identity(binding,self.host_identity)
        if hasattr(self.files,'verify_binding'):self.files.verify_binding(binding)
        code,ended,evidence=self._known_exit(binding,self.evidence.read(binding))
        # Timestamp BEFORE each query: a delayed response cannot relabel an old
        # acquisition as fresh. Refuse an overlong/rolled-back collection window.
        removed_at=self.clock()
        if self.commands.absent(binding['container_id']) is not True:
            raise RecordError('fresh successful original immutable-ID absence required')
        # Absence must precede the final kernel read: an in-flight start may
        # populate the frozen parent while the daemon inventory is being read.
        empty_at=self.clock()
        if not _empty_frozen(self.files.state(binding['parent_cgroup'])):
            raise RecordError('fresh original parent empty/frozen query required')
        _identity(binding,self.host_identity)
        finished=self.clock();elapsed=self.monotonic()-started
        if (not start<=removed_at<=empty_at<=finished
                or (finished-start).total_seconds()>60 or not 0<=elapsed<=60):
            raise RecordError('outside collection stale or clock changed')
        nonce=uuid.uuid4().hex
        return {'recovery_id':'root-recovery-'+nonce,
            'observation':{'observation_id':'root-observation-'+nonce,'host_id':binding['host_id'],
                'container_id':binding['container_id'],'workload_id':binding['workload_id'],
                'observed_at':empty_at.isoformat(),'ended_at':ended,'exit_status':code,
                'containment_state':'verified_empty',
                'termination_evidence':['root-query:'+nonce+':empty-frozen']+evidence},
            'removal':{'host_id':binding['host_id'],'container_id':binding['container_id'],
                'workload_id':binding['workload_id'],'observed_at':removed_at.isoformat(),
                'references':['root-query:'+nonce+':immutable-ID-absent']},
            'classification_evidence':list(self.classification_evidence)}
