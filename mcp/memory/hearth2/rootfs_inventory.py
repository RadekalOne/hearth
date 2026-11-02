"""Inactive exhaustive rootfs inventory ONLY, never credential absence proof.

Whole-view authorization is separate from selected-file enrollment. Native
consumer parsing/environment/config/mount-source coverage remains absent. No
default whole-view enrollment or driver/credential-backend wiring is installed.
"""
from dataclasses import dataclass
import hashlib
import time

from .creation import _digest
from .credential_policy import CredentialAuditRequirements
from .root_commands import BoundedCommand
from .rootfs_source import PROGRAM as FILE_PROGRAM, RootfsViewEnrollment
from .store import RecordError, safe_payload
from .timer_readback import _json


# Reuse only the reviewed stdlib identity/descriptor primitives, not its CLI.
PROGRAM=FILE_PROGRAM.split('\ndef measure(',1)[0]+r'''
def inventory(payload):
    view=payload['view'];limits=payload['limits'];first=identity()
    if first!={'boot_id':view['boot_id'],'namespaces':view['namespaces'],'uid':0,'euid':0}:raise ValueError('runtime differs')
    root=open_root(view['root_path'])
    work={'sources':0,'bytes':0};source_limit=min(limits['sources'],8192);byte_limit=min(limits['bytes'],67108864)
    def names(fd):
        result=[]
        with os.scandir(fd) as entries:
            for entry in entries:
                name=entry.name
                if not name or name in ['.','..'] or not name.isascii() or any(ord(c)<32 or ord(c)==127 for c in name) or '/' in name or '\\' in name:raise ValueError('name unsupported')
                result.append(name)
                if len(result)>=source_limit:raise ValueError('directory enumeration limit')
        if len(set(result))!=len(result):raise ValueError('duplicate directory entry')
        return sorted(result)
    try:
        mount=view['root_mount_id'];original=directory(root,mount)
        if (original.st_dev,original.st_ino,original.st_ctime_ns)!=(view['root_device'],view['root_inode'],view['root_ctime_ns']) or not os.fstatvfs(root).f_flag&os.ST_RDONLY:raise ValueError('readonly enrolled view differs')
        def scan():
            snapshots={};digest=hashlib.sha256();counts={'entries':0,'files':0,'directories':0,'bytes':0}
            def walk(fd,path,depth):
                if depth>64 or len(path)>4096:raise ValueError('tree depth/path limit')
                work['sources']+=1
                if work['sources']>=source_limit:raise ValueError('source work limit')
                value=os.fstat(fd);before=signature(value)
                if mount_id(fd)!=mount:raise ValueError('nested mount unsupported')
                snapshots[path]=before;counts['entries']+=1
                record={'path':path,'mode':stat.S_IMODE(value.st_mode),'uid':value.st_uid,'gid':value.st_gid,'links':value.st_nlink}
                if stat.S_ISDIR(value.st_mode):
                    counts['directories']+=1;record['kind']='directory'
                    listed=names(fd)
                    digest.update((json.dumps(record,sort_keys=True,separators=(',',':'))+'\n').encode())
                    for name in listed:
                        target=os.open(name,os.O_PATH|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
                        child=None
                        try:
                            target_stat=os.fstat(target)
                            if not (stat.S_ISDIR(target_stat.st_mode) or stat.S_ISREG(target_stat.st_mode)) or mount_id(target)!=mount:raise ValueError('unsupported source type or mount')
                            flags=os.O_RDONLY|os.O_CLOEXEC|os.O_NONBLOCK
                            if stat.S_ISDIR(target_stat.st_mode):flags|=os.O_DIRECTORY
                            child=os.open('/proc/self/fd/'+str(target),flags)
                            if signature(os.fstat(child))!=signature(target_stat) or mount_id(child)!=mount:raise ValueError('reopened source differs')
                            walk(child,('/' if path=='/' else path+'/')+name,depth+1)
                            if signature(os.stat(name,dir_fd=fd,follow_symlinks=False))!=signature(os.fstat(child)):raise ValueError('named source changed')
                        finally:
                            if child is not None:os.close(child)
                            os.close(target)
                    if names(fd)!=listed:raise ValueError('directory changed')
                elif stat.S_ISREG(value.st_mode):
                    if value.st_nlink!=1 or not 0<=value.st_size<=8388608:raise ValueError('file unsupported')
                    counts['files']+=1;counts['bytes']+=value.st_size;work['bytes']+=value.st_size
                    if work['bytes']>=byte_limit:raise ValueError('byte work limit')
                    content=hashlib.sha256();remaining=value.st_size
                    while remaining:
                        block=os.read(fd,min(65536,remaining))
                        if not block:raise ValueError('short read')
                        content.update(block);remaining-=len(block)
                    if os.read(fd,1):raise ValueError('file grew')
                    record.update(kind='file',size=value.st_size,sha256=content.hexdigest())
                    digest.update((json.dumps(record,sort_keys=True,separators=(',',':'))+'\n').encode())
                else:raise ValueError('unsupported source')
                if signature(os.fstat(fd))!=before:raise ValueError('source metadata changed')
            walk(root,'/',0)
            return snapshots,digest.hexdigest(),counts
        a,tree,counts=scan();b,other,again=scan()
        if a!=b or tree!=other or counts!=again:raise ValueError('whole inventory changed')
        check=open_root(view['root_path'])
        try:
            if signature(os.fstat(check))!=signature(original) or mount_id(check)!=mount or not os.fstatvfs(root).f_flag&os.ST_RDONLY or identity()!=first:raise ValueError('view/runtime changed')
        finally:os.close(check)
        snapshot=hashlib.sha256(json.dumps(a,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        return {**first,'root_device':original.st_dev,'root_inode':original.st_ino,'root_ctime_ns':original.st_ctime_ns,'root_mount_id':mount,**counts,'work_sources':work['sources'],'work_bytes':work['bytes'],'tree_sha256':tree,'snapshot_sha256':snapshot}
    finally:os.close(root)
if __name__=='__main__':
    try:
        if len(sys.argv)!=2:raise ValueError('arguments')
        print(json.dumps(inventory(json.loads(sys.argv[1])),sort_keys=True,separators=(',',':')))
    except BaseException:
        print('{"error":"rootfs inventory unavailable"}');sys.exit(70)
'''


@dataclass(frozen=True)
class RootfsInventoryEnrollment:
    view: RootfsViewEnrollment
    inventory_policy_sha256: str
    authority_reference: str

    def __post_init__(self):
        if (type(self.view) is not RootfsViewEnrollment or not _digest(self.inventory_policy_sha256)
                or type(self.authority_reference) is not str or not self.authority_reference.strip()
                or len(self.authority_reference)>4096):
            raise RecordError('separate immutable whole-view inventory enrollment required')


class RootfsInventorySource:
    def __init__(self,enrollments=(),command=None,*,host_identity,clock,monotonic=time.monotonic):
        if (type(enrollments) is not tuple or len(enrollments)>32 or any(type(v) is not RootfsInventoryEnrollment for v in enrollments)
                or len({(v.view.image_id,v.view.container_id) for v in enrollments})!=len(enrollments)):
            raise RecordError('unique independently authorized inventory views required')
        self.enrollments,self.command=enrollments,command
        self.host_identity,self.clock,self.monotonic=host_identity,clock,monotonic

    def scan(self,image_id,container_id,requirements):
        if type(requirements) is not CredentialAuditRequirements:raise RecordError('immutable inventory requirements required')
        matches=[v for v in self.enrollments if (v.view.image_id,v.view.container_id)==(image_id,container_id)]
        if len(matches)!=1:raise RecordError('whole-view inventory authority absent')
        enrollment=matches[0];view=enrollment.view;limits=dict(requirements.limits)
        requirements.require_scope(image_id,container_id,requirements.native_profile_sha256,enrollment.inventory_policy_sha256)
        if self.host_identity()!=view.host_id:raise RecordError('original inventory host differs')
        begin=self.clock();started=self.monotonic();payload={'view':view.manifest(),'limits':limits}
        args=['-I','-S','-c',PROGRAM,safe_payload(payload)];BoundedCommand.validate_arguments(args)
        command=self.command if self.command is not None else BoundedCommand('/usr/bin/python3',timeout_seconds=limits['seconds'],max_output=65536)
        result=_json(command.run(args))
        fields={'boot_id','namespaces','uid','euid','root_device','root_inode','root_ctime_ns','root_mount_id',
                'entries','files','directories','bytes','work_sources','work_bytes','tree_sha256','snapshot_sha256'}
        if (type(result) is not dict or set(result)!=fields or result['boot_id']!=view.boot_id
                or safe_payload(result['namespaces'])!=safe_payload(dict(view.namespaces))
                or any(type(result[k]) is not int or result[k]!=0 for k in ['uid','euid'])
                or any(type(result[k]) is not int or result[k]!=getattr(view,k) for k in ['root_device','root_inode','root_ctime_ns','root_mount_id'])
                or any(type(result[k]) is not int or result[k]<0 for k in ['entries','files','directories','bytes','work_sources','work_bytes'])
                or result['directories']<1 or result['entries']!=result['files']+result['directories']
                or result['bytes']>result['files']*8388608
                or result['work_sources']!=2*result['entries'] or not result['work_sources']<min(limits['sources'],8192)
                or result['work_bytes']!=2*result['bytes'] or not result['work_bytes']<min(limits['bytes'],67108864)
                or not _digest(result['tree_sha256']) or not _digest(result['snapshot_sha256'])):
            raise RecordError('bounded whole-view helper projection invalid')
        elapsed=self.monotonic()-started;finish=self.clock()
        if self.host_identity()!=view.host_id or not 0<=elapsed<limits['seconds'] or not 0<=(finish-begin).total_seconds()<limits['seconds']:
            raise RecordError('whole-view inventory identity/time changed')
        ref=hashlib.sha256(safe_payload({'view':view.manifest(),'policy':requirements.sha256,
            'program_sha256':hashlib.sha256(PROGRAM.encode()).hexdigest(),'facts':result}).encode()).hexdigest()
        return {'kind':'rootfs-inventory-only-v1','image_id':image_id,'container_id':container_id,
                'inventory_policy_sha256':requirements.sha256,**{k:result[k] for k in
                 ['entries','files','directories','bytes','work_sources','work_bytes','tree_sha256','snapshot_sha256']},
                'observed_at':begin.isoformat(),'references':[enrollment.authority_reference,view.authority_reference,'rootfs-inventory:'+ref]}
