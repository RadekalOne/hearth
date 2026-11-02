"""Trial-only native transcript projection and pinned file-reader checks.

No real login, user task, inference, persistent core or service change. The
native bootstrap is local transcript metadata, inside network-none containment.
"""
import argparse
import array
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import tempfile
import uuid

from hearth2_native_policy_probe import NativeProcess, immutable_file
from hearth2.native_policy import claude_arguments, claude_managed_settings

PIN = Path('/root/hearth-runner-trial/cloudroom-core-3949daaea3c7613458e9ad14afddbd267a0a56bc')
BASE = Path('/run/hearth2-fixtures')


def as_worker():
    os.setgroups([])
    os.setgid(1000)
    os.setuid(1000)


def pinned_open(helper_source, root, relative):
    """Use the actual pinned helper's SCM_RIGHTS entry point under worker UID."""
    parent, child = socket.socketpair()
    parent.settimeout(3)
    process = subprocess.Popen(['python3', '-I', '-c', helper_source],
        stdin=subprocess.PIPE, stdout=child, stderr=subprocess.DEVNULL,
        cwd='/', preexec_fn=as_worker,
        env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'})
    child.close()
    descriptors = []
    try:
        process.stdin.write(json.dumps({'op':'open','tree':{'root':str(root)},
            'path':relative,'directory':False}).encode()+b'\n')
        process.stdin.close()
        data, messages, flags, address = parent.recvmsg(4096,
            socket.CMSG_SPACE(array.array('i').itemsize), socket.MSG_CMSG_CLOEXEC)
        for level, kind, payload in messages:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                values=array.array('i');values.frombytes(payload);descriptors.extend(values)
        process.wait(timeout=3)
        if not descriptors:
            return None
        if data != b'F' or len(descriptors) != 1:
            raise RuntimeError('invalid pinned reader descriptor response')
        info=os.fstat(descriptors[0])
        if not stat.S_ISREG(info.st_mode) or info.st_size > 1024*1024:
            raise RuntimeError('fixture transcript exceeds regular-file/size bound')
        return os.read(descriptors[0],1024*1024)
    finally:
        for descriptor in descriptors:os.close(descriptor)
        parent.close()
        if process.poll() is None:process.kill();process.wait(timeout=3)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-trial-fixture',action='store_true')
    parser.add_argument('--baseline-pinned-args',action='store_true',
        help='Unchanged core arguments, fake auth and network none; diagnostic control only')
    args=parser.parse_args()
    if not args.execute_trial_fixture or os.geteuid()!=0 or socket.gethostname()!='srv2065995':
        parser.error('explicit opt-in, root and exact isolated trial host required')
    if BASE.exists() and (BASE.is_symlink() or BASE.stat().st_uid!=0 or BASE.stat().st_mode&0o022):
        raise RuntimeError('unsafe fixture base')
    BASE.mkdir(exist_ok=True,mode=0o755)
    run=BASE/uuid.uuid4().hex;run.mkdir(mode=0o755)
    account,work=run/'account',run/'work'
    account.mkdir(mode=0o1777);account.chmod(0o1777)
    work.mkdir(mode=0o755)
    config=account/'.claude';projects=config/'projects'
    config.mkdir(mode=0o1777);config.chmod(0o1777)
    projects.mkdir(mode=0o1777);projects.chmod(0o1777)
    artifacts=Path(tempfile.mkdtemp(prefix='projection-fixture-',dir='/root/hearth-runner-trial'))
    artifacts.chmod(0o755)
    policy=artifacts/'managed-settings.json'
    immutable_file(policy,json.dumps({} if args.baseline_pinned_args else claude_managed_settings()))
    session=str(uuid.uuid4())
    source=['-p','--input-format','stream-json','--output-format','stream-json',
        '--verbose','--include-partial-messages','--replay-user-messages',
        '--dangerously-skip-permissions','--permission-prompts','none','--no-chrome',
        '--model','sonnet','--append-system-prompt','Projection fixture; no inference.',
        '--disallowedTools','AskUserQuestion,EnterPlanMode,ExitPlanMode,Agent,Task,Workflow,SendMessage',
        '--mcp-config','{"mcpServers":{"cloudroom":{"type":"sdk","name":"cloudroom"}}}',
        '--session-id',session,'--settings','{"fastMode":false,"enableWorkflows":false}']
    process=None
    try:
        arguments=source if args.baseline_pinned_args else claude_arguments(source,expected_model='sonnet')
        process=NativeProcess(artifacts,'claude',policy,arguments,
                              projection=(account,work))
        process.send({'type':'control_request','request_id':'1','request':{
            'subtype':'initialize','hooks':{'SubagentStart':[{'hookCallbackIds':['cloudroom-native-child']}]},
            'sdkMcpServers':['cloudroom']}})
        response=process.receive(lambda value:value.get('type')=='control_response'
            and value.get('response',{}).get('request_id')=='1')['response']
        assert response.get('response',{}).get('hooks_applied') is True
        process.send({'type':'control_request','request_id':'2','request':{
            'subtype':'bootstrap','text':'Synthetic projection note; no user task.'}})
        boot=process.receive(lambda value:value.get('type')=='control_response'
            and value.get('response',{}).get('request_id')=='2')['response']
        if boot.get('subtype')!='success':
            (artifacts/'bootstrap-failure.json').write_text(json.dumps(
                {'baseline_pinned_args':args.baseline_pinned_args,'response':boot},indent=2)+'\n')
            raise RuntimeError('native bootstrap failed; diagnostic in '+str(artifacts/'bootstrap-failure.json'))
        transcripts=list(projects.glob('*/'+session+'.jsonl'))
        assert len(transcripts)==1,'native transcript mapping missing or ambiguous'
        transcript=transcripts[0]
        assert any(row.get('sessionId')==session and row.get('type')=='user'
                   for row in map(json.loads,transcript.read_text().splitlines()))
        helper=(PIN/'src/sync/files.py').read_text()
        relative=str(transcript.relative_to(projects))
        content=pinned_open(helper,projects,relative)
        assert content and b'Synthetic projection note' in content

        # Root-owned sticky anchors permit ordinary native metadata but prevent
        # a worker from replacing the reader's root or config ancestors.
        attack='''import os,sys
for path in sys.argv[1:]:
    try:os.rename(path,path+'-moved')
    except PermissionError:continue
    raise SystemExit(1)
'''
        refused=subprocess.run(['python3','-I','-c',attack,str(config),str(projects)],
            preexec_fn=as_worker,env={'PATH':'/usr/bin:/bin'},timeout=5)
        assert refused.returncode==0,'worker replaced protected projection anchor'

        outside=run/'outside';outside.mkdir(mode=0o755)
        canary=outside/'canary.jsonl';canary.write_text('OFF_SCOPE_CANARY');canary.chmod(0o644)
        leaf=transcript.parent
        linked=leaf/'linked.jsonl';linked.symlink_to(canary)
        assert pinned_open(helper,projects,str(linked.relative_to(projects))) is None
        directory_link=projects/'linked-dir';directory_link.symlink_to(outside,target_is_directory=True)
        assert pinned_open(helper,projects,'linked-dir/canary.jsonl') is None
        fifo=leaf/'not-regular';os.mkfifo(fifo)
        assert pinned_open(helper,projects,str(fifo.relative_to(projects))) is None
        result={'same_home_and_cwd_mapping':True,'native_bootstrap_transcript_found':True,
            'pinned_reader_opened_native_record':True,'worker_anchor_replacement_refused':True,
            'final_symlink_refused':True,'intermediate_symlink_refused':True,'fifo_refused':True,
            'model_called':False,'real_credentials_used':False,
            'pinned_helper_sha256':hashlib.sha256(helper.encode()).hexdigest(),
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    finally:
        if process is not None:process.close()
        if run.parent!=BASE or run.resolve().parent!=BASE.resolve():
            raise RuntimeError('refusing cleanup outside this fixture root')
        shutil.rmtree(run)
    result['container_cleanup_verified']=process.cleanup_verified
    result['projection_removed']=not run.exists()
    (artifacts/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'receipt_directory':str(artifacts),**result},sort_keys=True))


if __name__=='__main__':main()
