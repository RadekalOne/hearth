"""Inactive bounded no-follow file measurements from explicitly enrolled views.

Enrollment is independent authority, never synthesized from caller image names,
directories, DB records or this helper's observations. No mounts are created and
no source is installed/wired by default. Actual enrollment/interpreter/root
runtime provenance and complete credential inventory remain separate gates.
"""
from dataclasses import dataclass
import hashlib
import time
import uuid

from .creation import _digest
from .file_measurements import _parts
from .root_commands import BoundedCommand, _container
from .store import RecordError, safe_payload
from .timer_readback import _json


# Passed literally to isolated stdlib Python, not read from a mutable script path.
# Fixed command transport strips inherited credentials and bounds time/output.
PROGRAM = r'''
import os,stat,json,hashlib,sys
def mount_id(fd):
    with open('/proc/self/fdinfo/'+str(fd),'rb') as stream:
        raw=stream.read(8193)
    if len(raw)>8192:raise ValueError('fdinfo bound')
    values=[line.split(b':',1)[1].strip() for line in raw.splitlines() if line.startswith(b'mnt_id:')]
    if len(values)!=1 or not values[0].isdigit() or int(values[0])<=0:raise ValueError('mount unknown')
    return int(values[0])
def identity():
    with open('/proc/sys/kernel/random/boot_id','rb') as stream:boot=stream.read(128).decode().strip()
    return {'boot_id':boot,'namespaces':{name:os.stat('/proc/self/ns/'+name).st_ino for name in ['user','pid','mnt','cgroup']},'uid':os.getuid(),'euid':os.geteuid()}
def signature(value):
    return tuple(getattr(value,k) for k in ['st_dev','st_ino','st_mode','st_uid','st_gid','st_nlink','st_size','st_mtime_ns','st_ctime_ns'])
def directory(fd,mount):
    value=os.fstat(fd)
    if not stat.S_ISDIR(value.st_mode) or value.st_uid!=0 or value.st_mode&0o022 or mount_id(fd)!=mount:raise ValueError('directory differs')
    return value
def open_root(path):
    flags=os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK
    fd=os.open('/',flags)
    try:
        for name in path.split('/')[1:]:
            new=os.open(name,flags,dir_fd=fd);os.close(fd);fd=new
        return fd
    except BaseException:
        os.close(fd);raise
def measure(enrollment,path):
    first=identity()
    expected={'boot_id':enrollment['boot_id'],'namespaces':enrollment['namespaces'],'uid':0,'euid':0}
    if first!=expected:raise ValueError('original root namespace differs')
    fds=[];links=[]
    try:
        root=open_root(enrollment['root_path']);fds.append(root)
        mount=enrollment['root_mount_id'];root_stat=directory(root,mount)
        if (root_stat.st_dev,root_stat.st_ino,root_stat.st_ctime_ns)!=(enrollment['root_device'],enrollment['root_inode'],enrollment['root_ctime_ns']):raise ValueError('root view differs')
        if not os.fstatvfs(root).f_flag&os.ST_RDONLY:raise ValueError('view is writable')
        directories=[(root,signature(root_stat))];parent=root
        parts=path.split('/')[1:]
        for name in parts[:-1]:
            fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=parent)
            fds.append(fd);links.append((parent,name,fd));directories.append((fd,signature(directory(fd,mount))));parent=fd
        target=os.open(parts[-1],os.O_PATH|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
        fds.append(target);links.append((parent,parts[-1],target));value=os.fstat(target)
        mode=stat.S_IMODE(value.st_mode)
        if not stat.S_ISREG(value.st_mode) or value.st_uid!=0 or value.st_gid!=0 or mode not in [0o444,0o555] or value.st_nlink!=1 or not 0<value.st_size<=8388608 or mount_id(target)!=mount:raise ValueError('file unsupported')
        fd=os.open('/proc/self/fd/'+str(target),os.O_RDONLY|os.O_CLOEXEC|os.O_NONBLOCK)
        fds.append(fd)
        if signature(os.fstat(fd))!=signature(value) or mount_id(fd)!=mount:raise ValueError('reopened inode differs')
        digest=hashlib.sha256();remaining=value.st_size
        while remaining:
            block=os.read(fd,min(65536,remaining))
            if not block:raise ValueError('short file')
            digest.update(block);remaining-=len(block)
        if os.read(fd,1) or signature(os.fstat(fd))!=signature(value):raise ValueError('file changed')
        for parent,name,child in links:
            if signature(os.stat(name,dir_fd=parent,follow_symlinks=False))!=signature(os.fstat(child)) or mount_id(child)!=mount:raise ValueError('path changed')
        for directory_fd,before in directories:
            if signature(directory(directory_fd,mount))!=before:raise ValueError('ancestor changed')
        check=open_root(enrollment['root_path']);fds.append(check)
        if signature(os.fstat(check))!=signature(root_stat) or mount_id(check)!=mount or not os.fstatvfs(root).f_flag&os.ST_RDONLY or identity()!=first:raise ValueError('view or runtime changed')
        return {**first,'root_device':root_stat.st_dev,'root_inode':root_stat.st_ino,'root_ctime_ns':root_stat.st_ctime_ns,'root_mount_id':mount,'path':path,'sha256':digest.hexdigest(),'mode':mode,'size':value.st_size,'file_uid':value.st_uid,'file_gid':value.st_gid}
    finally:
        for fd in reversed(fds):os.close(fd)
if __name__=='__main__':
    try:
        if len(sys.argv)!=3:raise ValueError('arguments')
        print(json.dumps(measure(json.loads(sys.argv[1]),sys.argv[2]),sort_keys=True,separators=(',',':')))
    except BaseException:
        print('{"error":"rootfs measurement unavailable"}');sys.exit(70)
'''


@dataclass(frozen=True)
class RootfsViewEnrollment:
    host_id: str
    boot_id: str
    namespaces: tuple
    image_id: str
    container_id: str | None
    root_path: str
    root_device: int
    root_inode: int
    root_ctime_ns: int
    root_mount_id: int
    paths: tuple
    authority_reference: str

    def __post_init__(self):
        try:
            if (not _digest(self.host_id) or str(uuid.UUID(self.boot_id))!=self.boot_id
                    or type(self.namespaces) is not tuple or len(self.namespaces)!=4
                    or any(type(v) is not tuple or len(v)!=2 for v in self.namespaces)
                    or {k for k,v in self.namespaces}!={'user','pid','mnt','cgroup'}
                    or any(type(v) is not int or not 0<v<1<<64 for k,v in self.namespaces)
                    or type(self.image_id) is not str or not self.image_id.startswith('sha256:') or not _digest(self.image_id[7:])
                    or any(type(v) is not int or not 0<v<1<<64 for v in [self.root_inode,self.root_ctime_ns,self.root_mount_id])
                    or type(self.root_device) is not int or not 0<=self.root_device<1<<64
                    or type(self.paths) is not tuple or not 1<=len(self.paths)<=8 or len(set(self.paths))!=len(self.paths)
                    or type(self.authority_reference) is not str or not 1<=len(self.authority_reference)<=4096):
                raise ValueError('enrollment')
            if self.container_id is not None:_container(self.container_id)
            _parts(self.root_path)
            for path in self.paths:_parts(path)
            safe_payload(self.manifest())
        except (TypeError,ValueError,AttributeError):raise RecordError('explicit immutable rootfs enrollment required') from None

    def manifest(self):
        return {**vars(self),'namespaces':dict(self.namespaces),'paths':list(self.paths)}


class RootfsFileMeasurements:
    def __init__(self,enrollments=(),command=None,*,host_identity,clock,monotonic=time.monotonic):
        if (type(enrollments) is not tuple or len(enrollments)>32 or any(type(v) is not RootfsViewEnrollment for v in enrollments)
                or len({(v.image_id,v.container_id) for v in enrollments})!=len(enrollments)):
            raise RecordError('unique immutable enrolled rootfs views required')
        self.enrollments=enrollments
        self.command=command if command is not None else BoundedCommand('/usr/bin/python3',timeout_seconds=5,max_output=65536)
        self.host_identity,self.clock,self.monotonic=host_identity,clock,monotonic

    def observe(self,image_id,container_id,path):
        _parts(path)
        matches=[v for v in self.enrollments if (v.image_id,v.container_id)==(image_id,container_id)]
        if len(matches)!=1 or path not in matches[0].paths:raise RecordError('exact independently enrolled rootfs target required')
        anchor=matches[0]
        if self.host_identity()!=anchor.host_id:raise RecordError('original rootfs host differs')
        begin=self.clock();started=self.monotonic();manifest=anchor.manifest()
        args=['-I','-S','-c',PROGRAM,safe_payload(manifest),path]
        BoundedCommand.validate_arguments(args)
        result=_json(self.command.run(args))
        fields={'boot_id','namespaces','uid','euid','root_device','root_inode','root_ctime_ns','root_mount_id','path','sha256','mode','size','file_uid','file_gid'}
        if (not isinstance(result,dict) or set(result)!=fields or result['boot_id']!=anchor.boot_id
                or safe_payload(result['namespaces'])!=safe_payload(dict(anchor.namespaces)) or result['path']!=path
                or any(type(result[k]) is not int or result[k]!=0 for k in ['uid','euid','file_uid','file_gid'])
                or any(type(result[k]) is not int or result[k]!=getattr(anchor,k) for k in ['root_device','root_inode','root_ctime_ns','root_mount_id'])
                or not _digest(result['sha256']) or type(result['mode']) is not int or result['mode'] not in {0o444,0o555}
                or type(result['size']) is not int or not 0<result['size']<=8*1024*1024):
            raise RecordError('rootfs helper projection differs from enrollment')
        finish=self.clock();elapsed=self.monotonic()-started
        if self.host_identity()!=anchor.host_id or not 0<=(finish-begin).total_seconds()<=5 or not 0<=elapsed<=5:
            raise RecordError('rootfs measurement host or time changed')
        reference=hashlib.sha256(safe_payload({'enrollment':manifest,'program_sha256':hashlib.sha256(PROGRAM.encode()).hexdigest(),'facts':result}).encode()).hexdigest()
        return {'image_id':image_id,'container_id':container_id,'path':path,'sha256':result['sha256'],
                'kind':'regular','uid':0,'mode':result['mode'],'size':result['size'],
                'observed_at':begin.isoformat(),'references':[anchor.authority_reference,'enrolled-rootfs:'+reference]}
