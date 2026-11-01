"""Inactive TIMER-ONLY readback, using documented typed systemd D-Bus values.

No arming/start/stop/LoadUnit method is issued. This does not validate the guard
service's executable, credentials, placement or actual deadline enforcement.
"""
from datetime import datetime,timezone
import hashlib
import json
import re
import time
from .root_commands import BoundedCommand,_object
from .root_guard import _identity
from .store import RecordError,safe_payload,timestamp


_SERVICE='org.freedesktop.systemd1'
_MANAGER='/org/freedesktop/systemd1'
_UNIT=[('Id','s'),('LoadState','s'),('ActiveState','s'),('SubState','s'),('Transient','b'),('InvocationID','ay')]
_TIMER=[('Unit','s'),('TimersMonotonic','a(stt)'),('TimersCalendar','a(sst)'),
        ('NextElapseUSecRealtime','t'),('NextElapseUSecMonotonic','t'),('LastTriggerUSec','t'),
        ('Result','s'),('AccuracyUSec','t'),('RandomizedDelayUSec','t'),('Persistent','b'),
        ('OnClockChange','b'),('OnTimezoneChange','b'),('RemainAfterElapse','b')]


def _uint(value):return type(value) is int and 0<=value<(1<<64)


def _typed(signature,value):
    if signature=='s':return isinstance(value,str) and len(value)<=512
    if signature=='b':return type(value) is bool
    if signature=='t':return _uint(value)
    if signature=='ay':
        return isinstance(value,list) and len(value)<=16 and all(type(v) is int and 0<=v<=255 for v in value)
    if signature in {'a(sst)','a(stt)'}:
        return (isinstance(value,list) and len(value)<=16 and all(
            isinstance(row,list) and len(row)==3 and _typed('s',row[0])
            and (_typed('s',row[1]) if signature=='a(sst)' else _uint(row[1])) and _uint(row[2]) for row in value))
    return False


def _json(raw):
    try:
        return json.loads(raw,object_pairs_hook=_object,
            parse_constant=lambda _:(_ for _ in ()).throw(ValueError('nonfinite')))
    except (ValueError,UnicodeError,RecursionError,TypeError):
        raise RecordError('systemd typed JSON invalid') from None


class SystemdTimerProperties:
    def __init__(self,runner=None):
        self.runner=runner if runner is not None else BoundedCommand('/usr/bin/busctl')

    def _run(self,args):
        return self.runner.run(['--system','--no-pager','--allow-interactive-authorization=no','--json=short',*args])

    def _lookup(self,unit):
        value=_json(self._run(['call',_SERVICE,_MANAGER,_SERVICE+'.Manager','GetUnit','s',unit]))
        if (not isinstance(value,dict) or set(value)!={'type','data'} or value['type']!='o'
                or not isinstance(value['data'],list) or len(value['data'])!=1
                or not isinstance(value['data'][0],str)
                or re.fullmatch(r'/org/freedesktop/systemd1/unit/[A-Za-z0-9_]{1,512}',value['data'][0]) is None):
            raise RecordError('systemd existing unit path invalid')
        return value['data'][0]

    def _properties(self,path,interface,fields,*,validator=_typed):
        raw=self._run(['get-property',_SERVICE,path,interface,*[name for name,_ in fields]])
        lines=raw.splitlines()
        if len(lines)!=len(fields):raise RecordError('systemd property count differs')
        result={}
        for line,(name,signature) in zip(lines,fields):
            value=_json(line)
            if (not isinstance(value,dict) or set(value)!={'type','data'}
                    or value['type']!=signature or not validator(signature,value['data'])):
                raise RecordError('systemd property type or shape differs')
            result[name]=value['data']
        return result

    def snapshot(self,guard):
        if not isinstance(guard,str) or re.fullmatch(r'hearth2-deadline-[a-f0-9]{64}',guard) is None:
            raise RecordError('sealed original guard identity required')
        timer=self._lookup(guard+'.timer');service=self._lookup(guard+'.service')
        return {'timer_path':timer,'service_path':service,
            'timer_unit':self._properties(timer,_SERVICE+'.Unit',_UNIT),
            'timer':self._properties(timer,_SERVICE+'.Timer',_TIMER),
            'service_unit':self._properties(service,_SERVICE+'.Unit',_UNIT)}


def _deadline(binding):
    deadline=timestamp(binding['deadline_at']).astimezone(timezone.utc)
    delta=deadline-datetime(1970,1,1,tzinfo=timezone.utc)
    usec=(delta.days*86400+delta.seconds)*1000000+delta.microseconds
    if not 1970<=deadline.year<=2199 or not 0<usec<(1<<64)-1:
        raise RecordError('systemd absolute deadline outside supported calendar range')
    calendar=deadline.strftime('%Y-%m-%d %H:%M:%S')
    if deadline.microsecond:calendar+='.%06d'%deadline.microsecond
    return deadline,usec,calendar+' UTC'


class RootTimerReadback:
    def __init__(self,properties,*,host_identity,clock,monotonic=time.monotonic):
        self.properties,self.host_identity,self.clock,self.monotonic=properties,host_identity,clock,monotonic

    def _check(self,snapshot,binding,usec,calendar):
        if not isinstance(snapshot,dict) or set(snapshot)!={'timer_path','service_path','timer_unit','timer','service_unit'}:
            raise RecordError('exact timer-only snapshot required')
        unit=snapshot['timer_unit'];service=snapshot['service_unit'];timer=snapshot['timer']
        if (not isinstance(unit,dict) or set(unit)!={k for k,_ in _UNIT}
                or not isinstance(service,dict) or set(service)!={k for k,_ in _UNIT}
                or not isinstance(timer,dict) or set(timer)!={k for k,_ in _TIMER}):
            raise RecordError('timer/service selected properties differ')
        if (any(not _typed(kind,unit[name]) or not _typed(kind,service[name]) for name,kind in _UNIT)
                or any(not _typed(kind,timer[name]) for name,kind in _TIMER)):
            raise RecordError('timer/service property types differ')
        guard=binding['guard_id']
        if (unit['Id']!=guard+'.timer' or service['Id']!=guard+'.service'
                or unit['LoadState']!='loaded' or service['LoadState']!='loaded'
                or unit['ActiveState']!='active' or unit['SubState']!='waiting'
                or unit['Transient'] is not True or service['Transient'] is not True
                or service['ActiveState']!='inactive' or service['SubState']!='dead'
                or not _typed('ay',unit['InvocationID']) or len(unit['InvocationID'])!=16 or not any(unit['InvocationID'])
                or service['InvocationID'] not in ([],[0]*16)):
            raise RecordError('original transient timer/service not safely waiting')
        expected={'Unit':guard+'.service','TimersMonotonic':[],
            'TimersCalendar':[['OnCalendar',calendar,usec]],'NextElapseUSecRealtime':usec,
            'NextElapseUSecMonotonic':0,'LastTriggerUSec':0,'Result':'success','AccuracyUSec':1000,
            'RandomizedDelayUSec':0,'Persistent':False,'OnClockChange':False,
            'OnTimezoneChange':False,'RemainAfterElapse':True}
        if timer!=expected:raise RecordError('original absolute timer deadline/trigger policy changed')

    def inspect(self,binding):
        """Return TIMER evidence only, never a full consume/start authorization."""
        try:return self._inspect(binding)
        except RecordError:raise
        except Exception:raise RecordError('original timer readback unavailable') from None

    def _inspect(self,binding):
        start=self.clock();began=self.monotonic();_identity(binding,self.host_identity)
        deadline,usec,calendar=_deadline(binding)
        if start>=deadline:raise RecordError('original deadline already elapsed')
        first=self.properties.snapshot(binding['guard_id']);self._check(first,binding,usec,calendar)
        second=self.properties.snapshot(binding['guard_id']);self._check(second,binding,usec,calendar)
        _identity(binding,self.host_identity);finished=self.clock();elapsed=self.monotonic()-began
        if (safe_payload(first)!=safe_payload(second) or not start<=finished<deadline
                or (finished-start).total_seconds()>60 or not 0<=elapsed<=60):
            raise RecordError('timer readback changed, expired or stale')
        digest=hashlib.sha256(safe_payload(first).encode()).hexdigest()
        return {'host_id':binding['host_id'],'guard_id':binding['guard_id'],
            'deadline_at':binding['deadline_at'],'observed_at':start.isoformat(),
            'timer_state':'armed','service_id':binding['guard_id']+'.service',
            'invocation_id':bytes(first['timer_unit']['InvocationID']).hex(),
            'references':['root-timer:'+digest]}
