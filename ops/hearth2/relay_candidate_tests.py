"""Fixed credential-free candidate tests and outside workload supervision. No auto launch."""
import os,re,signal,subprocess
from pathlib import Path

def command(image,source,name):
    if not re.fullmatch('sha256:[0-9a-f]{64}',image) or not re.fullmatch('hearth-entitlement-[a-z0-9-]+',name):raise ValueError('fixed_image_and_name_required')
    source=Path(source)
    if not source.is_absolute() or not source.is_dir() or source.is_symlink() or ',' in str(source):raise ValueError('isolated_source_required')
    return ['docker','run','--name',name,'--pull=never','--network=none','--read-only','--cap-drop=ALL',
        '--security-opt=no-new-privileges','--user=1000:1000','--pids-limit=128','--memory=1g',
        '--tmpfs=/tmp:rw,nosuid,nodev,size=64m','--mount',f'type=bind,src={source},dst=/source,readonly',
        '--workdir=/source',image,'python','-I','-m','unittest','discover','-s','test','-p','test_entitlement_fixture.py']

def supervised_process(argv,*,timeout):
    """Parent is outside child's group. Windows uses existing Job implementation."""
    if not 0<timeout<=120:raise ValueError('outside_cutoff_bound')
    if os.name=='nt':
        from relay_native import ProcessOwner
        owner=ProcessOwner(argv,dict(os.environ),os.getcwd())
        try:
            try:code=owner.process.wait(timeout=timeout);state='exited'
            except subprocess.TimeoutExpired:code=None;state='timeout'
        finally:empty=owner.close()
        for pipe in (owner.process.stdin,owner.process.stdout,owner.process.stderr):pipe.close()
        return {'state':state,'exit_code':code,'empty':empty}
    p=subprocess.Popen(argv,start_new_session=True,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        try:code=p.wait(timeout=timeout);state='exited'
        except subprocess.TimeoutExpired:code=None;state='timeout'
    finally:
        try:os.killpg(p.pid,signal.SIGKILL)
        except ProcessLookupError:pass
        p.wait(timeout=5)
    # Process-group death is not container removal proof.
    return {'state':state,'exit_code':code,'empty':True}

def run(image,source,name):
    """Container cutoff/removal is outside the candidate process, even on CLI hang."""
    result=supervised_process(command(image,source,name),timeout=30)
    subprocess.run(['docker','kill',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
    removed=subprocess.run(['docker','rm','-f',name],capture_output=True,timeout=5)
    if removed.returncode:raise ValueError('candidate_removal_unconfirmed')
    result['container_removed']=True
    if result['state']!='exited' or result['exit_code']!=0:raise ValueError('candidate_test_failed')
    return result
