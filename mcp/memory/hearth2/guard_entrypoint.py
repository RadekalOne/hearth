"""Sealed root guard ABI/composition, not installed or activated.

The default CLI has NO runtime. A later trusted root wrapper must supply original
host authentication and a seal directory; command arguments cannot configure it.
"""
import hashlib
import os
import secrets
import sys
from .guard_evidence import GuardEvidenceStore,_MAX
from .root_commands import DockerSystemdCommands
from .root_guard import RootKernelGuard,_identity
from .root_layout import RootLayoutPolicy,MappedCgroupFiles,_path
from .store import RecordError,safe_payload,timestamp
from .timer_readback import _json


class RootGuardBindings(GuardEvidenceStore):
    """Original execution seals, in a SEPARATE directory from guard receipts."""
    def _body(self,binding,layout,evidence_root,host_identity):
        self._binding(binding);_identity(binding,host_identity)
        RootLayoutPolicy.encode(layout)
        digest=hashlib.sha256(RootLayoutPolicy.encode(layout)).hexdigest()
        if digest!=binding['policy_sha256']:raise RecordError('sealed layout policy differs')
        policy=RootLayoutPolicy(digest,**{k:v for k,v in layout.items() if k!='version'})
        policy.resolve(binding,host_identity=host_identity);_path(evidence_root,root=True)
        return {'version':1,'binding':binding,'layout':layout,'evidence_root':evidence_root}

    def _read(self,directory,binding,host_identity):
        name=binding['guard_id']+'.json'
        with self._file(directory,name) as fd:
            raw=os.read(fd,_MAX+1)
            if len(raw)>_MAX:raise RecordError('guard seal exceeds bound')
            value=_json(raw)
            if (not isinstance(value,dict) or set(value)!={'version','binding','layout','evidence_root','sha256'}
                    or type(value['version']) is not int or value['version']!=1
                    or safe_payload(value['binding'])!=safe_payload(binding)):
                raise RecordError('original guard seal binding differs')
            body=self._body(value['binding'],value['layout'],value['evidence_root'],host_identity)
            if (value['sha256']!=hashlib.sha256(safe_payload(body).encode()).hexdigest()
                    or (safe_payload(value)+'\n').encode()!=raw):
                raise RecordError('guard seal checksum or encoding differs')
            os.fsync(fd)
        os.fsync(directory)
        return value

    def read(self,binding,*,host_identity):
        self._binding(binding);_identity(binding,host_identity)
        with self._directory() as directory:return self._read(directory,binding,host_identity)

    def seal(self,binding,policy,evidence_root,*,host_identity):
        # Copy before trusted callbacks can mutate caller-owned dictionaries.
        binding=_json(safe_payload(binding));layout={k:v for k,v in vars(policy).items() if k!='sha256'}
        layout['version']=1
        body=self._body(binding,layout,evidence_root,host_identity)
        now=self.clock()
        if not timestamp(binding['at'])<=now<timestamp(binding['deadline_at']):
            raise RecordError('new guard seal requires original unexpired creation')
        # Validate the original private evidence location BEFORE arming. It is
        # retained in the seal; expiry execution does not choose a new location.
        with GuardEvidenceStore(evidence_root)._directory():pass
        digest=hashlib.sha256(safe_payload(body).encode()).hexdigest()
        record={**body,'sha256':digest};raw=(safe_payload(record)+'\n').encode()
        if len(raw)>_MAX:raise RecordError('guard execution seal exceeds bound')
        name=binding['guard_id']+'.json'
        with self._directory(write=True) as directory:
            try:os.stat(name,dir_fd=directory,follow_symlinks=False)
            except FileNotFoundError:pass
            else:
                previous=self._read(directory,binding,host_identity)
                if safe_payload(previous)!=safe_payload(record):raise RecordError('original guard execution seal immutable')
                return {'reference':name,'sha256':digest}
            count=0
            with os.scandir(directory) as entries:
                for _ in entries:
                    count+=1
                    if count>4094:raise RecordError('guard seal directory capacity exceeded')
            temporary='.stage-'+secrets.token_hex(16);created=False;fd=None
            try:
                fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=directory)
                created=True;os.fchmod(fd,0o400)
                if os.write(fd,raw)!=len(raw):raise RecordError('guard seal write incomplete')
                os.fsync(fd);os.close(fd);fd=None
                os.link(temporary,name,src_dir_fd=directory,dst_dir_fd=directory,follow_symlinks=False)
                os.unlink(temporary,dir_fd=directory);created=False
                os.fsync(directory)
            finally:
                if fd is not None:os.close(fd)
                if created:
                    try:os.unlink(temporary,dir_fd=directory)
                    except FileNotFoundError:pass
        return {'reference':name,'sha256':digest}


class RootGuardRuntime:
    def __init__(self,seals,*,host_identity,clock,euid=os.geteuid,commands=None,files_factory=MappedCgroupFiles):
        self.seals,self.host_identity,self.clock,self.euid=seals,host_identity,clock,euid
        self.commands=commands if commands is not None else DockerSystemdCommands()
        self.files_factory=files_factory

    def execute(self,binding):
        uid=self.euid()
        if type(uid) is not int or uid!=0:raise RecordError('root runtime identity required')
        original=safe_payload(binding)
        record=self.seals.read(binding,host_identity=self.host_identity)
        # Use the ROOT seal, never arguments/restore-host discovery for placement.
        bound=record['binding'];layout=record['layout']
        policy=RootLayoutPolicy(bound['policy_sha256'],**{k:v for k,v in layout.items() if k!='version'})
        if safe_payload(binding)!=original:raise RecordError('guard invocation binding changed')
        if self.clock()<timestamp(bound['deadline_at']):raise RecordError('original guard deadline not reached')
        uid=self.euid()
        if type(uid) is not int or uid!=0:raise RecordError('root runtime identity changed')
        files=self.files_factory(policy,bound,host_identity=self.host_identity)
        evidence=GuardEvidenceStore(record['evidence_root'],clock=self.clock)
        return RootKernelGuard(files,self.commands,host_identity=self.host_identity,clock=self.clock,
                               evidence=evidence).enforce(bound)


def parse_binding(argv):
    if (not isinstance(argv,list) or len(argv)!=2 or argv[0]!='--binding-json'
            or not isinstance(argv[1],str) or len(argv[1].encode())>8192):
        raise RecordError('exact bounded guard ABI required')
    binding=_json(argv[1])
    GuardEvidenceStore('/')._binding(binding)  # Pure schema check; no path is opened.
    if safe_payload(binding)!=argv[1]:raise RecordError('canonical original binding argument required')
    return binding


def main(argv=None,*,runtime=None,stdout=None,stderr=None):
    stdout=sys.stdout if stdout is None else stdout;stderr=sys.stderr if stderr is None else stderr
    try:
        binding=parse_binding(sys.argv[1:] if argv is None else argv)
        if runtime is None:raise RecordError('trusted root runtime not configured')
        receipt=runtime.execute(binding)
        stdout.write(safe_payload({'termination_state':'observed','guard_id':receipt['guard_id'],
            'container_id':receipt['container_id'],'references':receipt['evidence']})+'\n')
        return 0
    except Exception:
        stderr.write('root guard unavailable or incomplete\n')
        return 1


if __name__=='__main__':raise SystemExit(main())
