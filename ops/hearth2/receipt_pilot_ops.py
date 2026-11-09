"""Operator-only receipt pilot cutoff and cold snapshot utilities.

Importing executes nothing. A sealed private plan identifies one Compose service;
production use still requires the human approval recorded in that plan.
"""
import argparse,copy,fcntl,hashlib,json,math,os,re,stat,subprocess,tarfile,time,uuid
from pathlib import Path,PurePosixPath
from datetime import datetime,timezone

SECURITY=('notice-session-credentials.sqlite3','notice-session-credentials.required','memory-tokens.json','reviewers.sqlite3')
MAX_BYTES=512*1024*1024
MAX_FILES=10000

def digest(data):return hashlib.sha256(data).hexdigest()
def file_digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):value.update(chunk)
    return value.hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def atomic_json(path,value):
    path=Path(path);mode=stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    temporary=path.with_name('.'+path.name+'.'+uuid.uuid4().hex)
    fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,mode)
    try:
        with os.fdopen(fd,'w') as out:json.dump(value,out,sort_keys=True,indent=2);out.flush();os.fsync(out.fileno())
        os.replace(temporary,path)
        parent=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(parent)
        finally:os.close(parent)
    finally:temporary.unlink(missing_ok=True)
def immutable_config(config,service):
    value=copy.deepcopy(config);s=value['services'][service]
    for key in ('image','restart'):s.pop(key,None)
    for key in ('HEARTH2_ENABLED','HEARTH2_NOTICE_SESSIONS'):s.get('environment',{}).pop(key,None)
    return digest(json.dumps(value,sort_keys=True,separators=(',',':')).encode())
def fallback_config(config,service,image):
    value=copy.deepcopy(config);s=value['services'][service];s['image']=image;s['restart']='unless-stopped'
    s.setdefault('environment',{}).update(HEARTH2_ENABLED='false',HEARTH2_NOTICE_SESSIONS='{}')
    return value
def retired_tokens(tokens,expected):
    if type(tokens) is not dict:raise ValueError('token map invalid')
    result=dict(tokens)
    pilot_hashes={value for values in expected.values() for value in values}
    if any(type(value) is str and digest(value.encode()) in pilot_hashes and name not in expected for name,value in tokens.items()):raise ValueError('unexpected pilot credential alias')
    for name,fingerprints in expected.items():
        if name in result:
            if type(result[name]) is not str or digest(result[name].encode()) not in fingerprints:raise ValueError('pilot credential mapping changed')
            del result[name]
    return result

def command(args,timeout=60):
    result=subprocess.run(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if result.returncode:raise RuntimeError('operator command failed; inspect private diagnostics')
    return result.stdout.decode()
def docker_inspect(name):return json.loads(command(['docker','inspect',name]))[0]
def writers(data):
    ids=command(['docker','ps','-q']).split()
    if not ids:return []
    return [c['Id'] for c in json.loads(command(['docker','inspect',*ids])) if any(m.get('RW') and (Path(m['Source']).resolve().is_relative_to(Path(data).resolve()) or Path(data).resolve().is_relative_to(Path(m['Source']).resolve())) for m in c.get('Mounts',[]) if m.get('Source'))]
def quiescent(data):
    if writers(data):raise ValueError('data still has a container writer')
def load_plan(path,expected):
    path=Path(path)
    if path.is_symlink() or path.stat().st_uid!=os.geteuid() or stat.S_IMODE(path.stat().st_mode)&0o077:raise ValueError('plan must be private and operator-owned')
    if file_digest(path)!=expected:raise ValueError('sealed plan changed')
    p=json.loads(path.read_text())
    if p.get('format')!='receipt-pilot-v1' or p.get('mode') not in ('rehearsal','approved') or not p.get('approval_ref'):raise ValueError('approval scope missing')
    for key in ('project','service','container'):
        if not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}',p[key]):raise ValueError('invalid service selector')
    root=Path(p['root']).resolve()
    if root!=path.parent.resolve() or root.stat().st_uid!=os.geteuid() or stat.S_IMODE(root.stat().st_mode)&0o077:raise ValueError('private plan root required')
    for key in ('config','data'):
        candidate=Path(p[key]);resolved=candidate.resolve(strict=True)
        if not candidate.is_absolute() or resolved!=candidate:raise ValueError('plan paths must be exact absolute paths')
        if p['mode']=='rehearsal' and not resolved.is_relative_to(root):raise ValueError('rehearsal path escapes fixture')
    if p['mode']=='rehearsal' and (not p['project'].startswith('hearth-receipt-rehearsal-') or p['container']=='hearth-project-hub-hub-1'):raise ValueError('rehearsal cannot target production')
    for key in ('candidate_image','fallback_image'):
        if not re.fullmatch(r'sha256:[0-9a-f]{64}',p[key]):raise ValueError('immutable image ID required')
    if p['boot_id']!=Path('/proc/sys/kernel/random/boot_id').read_text().strip():raise ValueError('host boot changed; require operator recovery')
    if type(p['deadline_monotonic']) not in (int,float) or not math.isfinite(p['deadline_monotonic']) or p['deadline_monotonic']>time.monotonic()+1201:raise ValueError('cutoff exceeds authorized20-minute window')
    if p.get('script_sha256') and p['script_sha256']!=file_digest(__file__):raise ValueError('operator artifact changed')
    if set(p.get('retire',{})) & set(p.get('preserve_principals',[])):raise ValueError('cannot retire preserved principals')
    for name,values in p.get('retire',{}).items():
        if not values or any(not re.fullmatch(r'[0-9a-f]{64}',v) for v in values):raise ValueError('invalid retirement fingerprints')
    return p

def scoped_container(p):
    c=docker_inspect(p['container']);labels=c['Config'].get('Labels') or {}
    if labels.get('com.docker.compose.project')!=p['project'] or labels.get('com.docker.compose.service')!=p['service']:raise ValueError('container authority mismatch')
    mounted=[m for m in c['Mounts'] if m['Destination']=='/data']
    if len(mounted)!=1 or Path(mounted[0]['Source']).resolve()!=Path(p['data']) or not mounted[0]['RW']:raise ValueError('data mount mismatch')
    return c

def verify_target(p):
    c=scoped_container(p)
    if c['Image'] not in (p['candidate_image'],p['fallback_image']):raise ValueError('unexpected service image')
    cfg=json.loads(Path(p['config']).read_text())
    if immutable_config(cfg,p['service'])!=p['immutable_config_sha256']:raise ValueError('unrelated configuration changed')
    if cfg['services'][p['service']]['image'] not in (p['candidate_image'],p['fallback_image']):raise ValueError('config image mismatch')
    if c['Image']==p['candidate_image'] and c['HostConfig']['RestartPolicy']['Name']!='no':raise ValueError('pilot must not auto-resume after host failure')
    return c,cfg

def _cutoff(p,expected):
    root=Path(p['root']);receipt=root/'cutoff-result.json'
    with (root/'operator.lock').open('a') as lock:
        lock_until=time.monotonic()+5
        while True:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>=lock_until:raise RuntimeError('operator lock unavailable')
                time.sleep(.1)
        if receipt.exists():
            prior=json.loads(receipt.read_text())
            if prior['plan_sha256']!=expected:raise ValueError('cutoff receipt belongs to another plan')
            c,cfg=verify_target(p)
            if c['Image']!=p['fallback_image'] or not c['State']['Running'] or cfg['services'][p['service']].get('environment',{}).get('HEARTH2_ENABLED')!='false':raise ValueError('cutoff state changed; maintenance required')
            tokens=json.loads((Path(p['data'])/'memory-tokens.json').read_text())
            retired_tokens(tokens,p['retire'])
            if set(tokens)&set(p['retire']):raise ValueError('pilot credentials reintroduced')
            return prior
        c,cfg=verify_target(p);tokens_path=Path(p['data'])/'memory-tokens.json'
        before=json.loads(tokens_path.read_text());retired_tokens(before,p['retire'])
        base=['docker','compose','-p',p['project'],'-f',p['config']]
        started=now();command([*base,'stop','-t','10',p['service']],25);quiescent(p['data'])
        _,latest=verify_target(p)
        tokens=json.loads(tokens_path.read_text());remaining=retired_tokens(tokens,p['retire'])
        atomic_json(tokens_path,remaining)
        atomic_json(p['config'],fallback_config(latest,p['service'],p['fallback_image']))
        command([*base,'up','-d','--no-deps','--no-build','--pull','never',p['service']],45)
        after=docker_inspect(p['container'])
        if after['Image']!=p['fallback_image'] or not after['State']['Running']:raise RuntimeError('fallback did not start')
        probe="import os,http.client; c=http.client.HTTPConnection('127.0.0.1',8010,timeout=2); h={'Authorization':'Bearer '+os.environ['HEARTH_MEMORY_ADMIN_TOKEN']}; c.request('GET','/api/status',headers=h); r=c.getresponse(); assert r.status==200; r.read(); c.request('GET','/api/hearth2/status',headers=h); r=c.getresponse(); assert r.status==409"
        ready=False
        for _ in range(10):
            result=subprocess.run(['docker','exec',p['container'],'python','-c',probe],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=4)
            if result.returncode==0:ready=True;break
            time.sleep(.3)
        if not ready:raise RuntimeError('fallback authentication/readiness check failed')
        if {k:v for k,v in tokens.items() if k not in p['retire']}!=remaining:raise ValueError('unrelated credential changed')
        result=dict(plan_sha256=expected,triggered_at=started,completed_at=now(),deadline_utc=p['deadline_utc'],deadline_monotonic=p['deadline_monotonic'],overshoot_seconds=max(0,time.monotonic()-p['deadline_monotonic']),before_id=c['Id'],after_id=after['Id'],fallback_image=after['Image'],h2_disabled=True,operator_rest_verified=True,pilot_entries_removed=sorted(set(tokens)-set(remaining)),unrelated_tokens_preserved=True,immutable_config_preserved=immutable_config(json.loads(Path(p['config']).read_text()),p['service'])==p['immutable_config_sha256'])
        atomic_json(receipt,result);return result

def fail_closed_stop(p,error_type):
    root=Path(p['root']);result=dict(at=now(),cause=error_type,maintenance=True,stopped=False)
    try:
        c=scoped_container(p)
        command(['docker','update','--restart=no',c['Id']],15)
        command(['docker','stop','-t','10',c['Id']],25)
        result['stopped']=not docker_inspect(c['Id'])['State']['Running']
        if not result['stopped']:raise RuntimeError('sealed service did not stop')
        quiescent(p['data'])
        result['container_id']=c['Id']
    except Exception as failure:
        result['stop_error_type']=type(failure).__name__
        atomic_json(root/'cutoff-failure.json',result)
        raise RuntimeError('sealed service requires operator maintenance') from None
    atomic_json(root/'cutoff-failure.json',result)
    return result

def cutoff(path,expected):
    p=load_plan(path,expected)
    try:return _cutoff(p,expected)
    except Exception as error:
        fail_closed_stop(p,type(error).__name__);raise

def guard(path,expected):
    # Keep the validated scope in memory. A damaged plan cannot erase the only
    # cutoff authority after arming; drift instead stops this scoped service.
    p=load_plan(path,expected);root=Path(p['root']);armed=root/'cutoff-armed.json'
    fd=os.open(armed,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as out:json.dump(dict(pid=os.getpid(),armed_at=now(),deadline_monotonic=p['deadline_monotonic'],plan_sha256=expected),out)
    try:
        while time.monotonic()<p['deadline_monotonic']:
            if file_digest(path)!=expected:raise ValueError('sealed plan drift')
            time.sleep(min(.2,max(0,p['deadline_monotonic']-time.monotonic())))
        if file_digest(path)!=expected:raise ValueError('sealed plan drift')
        return _cutoff(p,expected)
    except Exception as error:
        fail_closed_stop(p,type(error).__name__);raise

def security_state(data):
    data=Path(data);return {name:file_digest(data/name) if (data/name).is_file() else None for name in SECURITY}
def make_backup(data,config,destination,*,assert_quiescent):
    data,config,destination=map(Path,(data,config,destination))
    if not data.is_dir() or data.is_symlink() or not config.is_file() or config.is_symlink():raise ValueError('regular backup source required')
    if destination.exists() or destination.is_relative_to(data):raise ValueError('new external backup path required')
    assert_quiescent();files={};sources={}
    for path in sorted(data.rglob('*')):
        if path.is_symlink() or not path.is_file() and not path.is_dir():raise ValueError('unsupported backup entry')
        if path.is_file():sources['data/'+str(path.relative_to(data))]=path
    sources['config/compose.json']=config
    if len(sources)>MAX_FILES or sum(p.stat().st_size for p in sources.values())>MAX_BYTES:raise ValueError('backup exceeds review bound')
    for name,path in sources.items():files[name]=dict(sha256=file_digest(path),size=path.stat().st_size,mode=stat.S_IMODE(path.stat().st_mode))
    manifest=dict(format='receipt-pilot-cold-v1',files=files,security=security_state(data))
    fd=os.open(destination,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as raw,tarfile.open(fileobj=raw,mode='w') as archive:
        import io
        encoded=json.dumps(manifest,sort_keys=True).encode();info=tarfile.TarInfo('manifest.json');info.size=len(encoded);info.mode=0o600;archive.addfile(info,io.BytesIO(encoded))
        for name,path in sources.items():
            info=tarfile.TarInfo(name);info.size=files[name]['size'];info.mode=files[name]['mode']
            with path.open('rb') as stream:archive.addfile(info,stream)
    assert_quiescent()
    if any(file_digest(path)!=files[name]['sha256'] for name,path in sources.items()):raise ValueError('backup source changed')
    return dict(archive_sha256=file_digest(destination),files=len(files),bytes=sum(v['size'] for v in files.values()),security=manifest['security'])
def restore_backup(archive_path,expected,destination,*,security_source):
    archive_path,destination=map(Path,(archive_path,destination))
    if destination.exists():raise ValueError('restore destination must be absent')
    if archive_path.stat().st_size>MAX_BYTES+16*1024*1024 or file_digest(archive_path)!=expected:raise ValueError('backup checksum mismatch')
    with tarfile.open(archive_path) as archive:
        members={}
        for member in archive:
            name=member.name;part=PurePosixPath(name)
            if len(members)>MAX_FILES or name in members or not member.isfile() or part.is_absolute() or '..' in part.parts or str(part)!=name:raise ValueError('unsafe backup member')
            if name!='manifest.json' and not name.startswith(('data/','config/')):raise ValueError('unexpected backup path')
            members[name]=member
        if 'manifest.json' not in members or members['manifest.json'].size>1024*1024:raise ValueError('backup manifest missing')
        m=json.loads(archive.extractfile(members['manifest.json']).read())
        if m.get('format')!='receipt-pilot-cold-v1' or set(m['files'])!=set(members)-{'manifest.json'}:raise ValueError('backup manifest differs')
        if m['security']!=security_state(security_source):raise ValueError('stale security snapshot refused')
        total=0
        for name,entry in m['files'].items():
            total+=entry['size']
            if total>MAX_BYTES or entry['size']!=members[name].size:raise ValueError('restore exceeds bound')
            value=hashlib.sha256()
            with archive.extractfile(members[name]) as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):value.update(chunk)
            if value.hexdigest()!=entry['sha256']:raise ValueError('backup member checksum differs')
        staging=destination.with_name('.restore-'+uuid.uuid4().hex);staging.mkdir(mode=0o700)
        for name,entry in m['files'].items():
            output=staging/name;output.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            with archive.extractfile(members[name]) as source,output.open('xb') as target:
                for chunk in iter(lambda:source.read(1024*1024),b''):target.write(chunk)
            output.chmod(entry['mode']&0o777)
        if destination.exists():raise ValueError('restore destination appeared')
        staging.rename(destination)
    return dict(destination=str(destination),files=len(m['files']),archive_sha256=expected)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['guard','cutoff','backup','restore']);parser.add_argument('--plan',required=True);parser.add_argument('--plan-sha256',required=True);parser.add_argument('--archive');parser.add_argument('--archive-sha256');parser.add_argument('--destination');args=parser.parse_args()
    try:
        if args.action in ('guard','cutoff'):result=(guard if args.action=='guard' else cutoff)(args.plan,args.plan_sha256)
        else:
            p=load_plan(args.plan,args.plan_sha256);root=Path(p['root']);archive=Path(args.archive)
            if not archive.is_absolute() or not archive.resolve().is_relative_to(root):raise ValueError('private archive path required')
            quiescent(p['data'])
            if args.action=='backup':result=make_backup(p['data'],p['config'],archive,assert_quiescent=lambda:quiescent(p['data']))
            else:
                destination=Path(args.destination)
                if not destination.is_absolute() or not destination.resolve().is_relative_to(root):raise ValueError('private restore destination required')
                result=restore_backup(archive,args.archive_sha256,destination,security_source=p['data'])
        print(json.dumps(result))
    except Exception as error:
        print(json.dumps(dict(failed=True,error_type=type(error).__name__)),flush=True);raise SystemExit(1)
