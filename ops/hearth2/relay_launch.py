"""One-attempt proposal boundary. Real inference remains financially unconfigured.
No repository code or model-provided command ever executes on this host.
"""
import hashlib,json,os,subprocess
from pathlib import Path
from datetime import datetime,timezone
from relay_matrix import decode
from relay_native import NativeRefused,authorize_turn

class LaunchRefused(RuntimeError):pass


def write_proposal(source,proposal,target):
    if (type(source) is not dict or not 1<=len(source)<=32 or type(proposal) is not dict
        or set(proposal)!={'changes'} or type(proposal['changes']) is not list or not 1<=len(proposal['changes'])<=32):raise LaunchRefused('proposal_shape')
    changes={};total=0
    for c in proposal['changes']:
        if type(c) is not dict or set(c)!={'path','base_sha256','text'}:raise LaunchRefused('proposal_keys')
        p=c['path'];text=c['text']
        if (type(p) is not str or p not in source or p in changes or '\\' in p or p.startswith('/') or ':' in p
            or '..' in p.split('/') or type(text) is not str or '\x00' in text or len(text.encode())>65536
            or type(source[p]) is not str or hashlib.sha256(source[p].encode()).hexdigest()!=c['base_sha256']):raise LaunchRefused('proposal_scope_or_base')
        total+=len(text.encode());changes[p]=text
    if total>524288:raise LaunchRefused('proposal_output_bound')
    target=Path(target)
    if target.exists() or target.is_symlink():raise LaunchRefused('new_isolated_candidate_required')
    target.mkdir()
    # All data validated before creating the destination. Only fresh directories.
    for p,text in {**source,**changes}.items():
        file=target/p
        if not file.resolve().is_relative_to(target.resolve()):raise LaunchRefused('proposal_scope')
        file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(text.encode())
    return {'files':len(changes),'sha256':hashlib.sha256(json.dumps(changes,sort_keys=True).encode()).hexdigest(),
            'tests':'not_run','understanding':'unknown','task_state':'unchanged'}


def snapshot(repo,base,paths):
    """Read only named Git blobs; never checkout, hooks, smudge or repo executables."""
    import re
    if not re.fullmatch('[0-9a-f]{40}',base) or type(paths) is not list or not 1<=len(paths)<=32:raise LaunchRefused('snapshot_scope')
    from offline_relay import admit,Approval,ROOM,THREAD
    work={'work_id':'snapshot','aliases':[],'generation':1,'review_event':'$review','base_commit':base,'paths':paths,'scope':'hearth2-offline'}
    admit(work,Approval(ROOM,THREAD,'@rad:hearth.radekal.me','snapshot',1,base,tuple(paths),'$approval','server_authenticated',(),'$review'))
    def git(*args):
        p=subprocess.run(['git','--no-replace-objects','--no-pager',*args],cwd=repo,stdin=subprocess.DEVNULL,capture_output=True,timeout=5)
        if p.returncode:raise LaunchRefused('snapshot_git_refused')
        return p.stdout
    data={};total=0
    for path in paths:
        entry=git('ls-tree',base,'--',path).decode().strip()
        if not entry.startswith('100644 blob ') or entry.split('\t',1)[-1]!=path:raise LaunchRefused('snapshot_regular_blob_required')
        oid=entry.split()[2];size=int(git('cat-file','-s',oid))
        if not 0<=size<=65536:raise LaunchRefused('snapshot_file_bound')
        total+=size
        if total>524288:raise LaunchRefused('snapshot_total_bound')
        data[path]=git('cat-file','blob',oid).decode('utf-8')
    return data


class Launcher:
    def __init__(self,state,root):
        self.state,self.root=state,Path(root)
        with state.tx() as db:db.execute('CREATE TABLE IF NOT EXISTS relay_attempts(job TEXT PRIMARY KEY,send_state TEXT NOT NULL,reason TEXT NOT NULL,receipt TEXT)')
    def attempt(self,ident):
        with self.state.connect() as db:
            row=db.execute('SELECT * FROM relay_attempts WHERE job=?',(ident,)).fetchone()
            return dict(row) if row else None
    def active(self,job):
        c=self.state.control()
        return not c['paused'] and c['enabled']==1 and c['epoch']==job['epoch']
    def run(self,job,*,observation,snapshot,approval,financial_boundary):
        with self.state.tx() as db:
            if db.execute('SELECT 1 FROM relay_attempts WHERE job=?',(job['id'],)).fetchone():raise LaunchRefused('one_attempt_already_consumed')
            db.execute('INSERT INTO relay_attempts VALUES(?,?,?,NULL)',(job['id'],'not_sent','authority_pending'))
        try:
            # Deliberately no guessed financial route. No thread can be opened
            # before this returns a verified, scoped authority capability.
            authorize_turn(observation,approval=approval,financial_boundary=financial_boundary,work=job,now=datetime.now(timezone.utc))
        except NativeRefused as e:
            receipt={'confirmed_empty':True,'exit_code':77,'send_state':'not_sent','reason':str(e),
                'understanding':'unknown','task_state':'unchanged','tests':'not_run'}
            with self.state.tx() as db:db.execute('UPDATE relay_attempts SET reason=?,receipt=? WHERE job=?',(str(e),json.dumps(receipt),job['id']))
            return receipt
        # An adapter for a server-enforced financial boundary must be reviewed
        # before this becomes reachable. Quota and a human budget are not one.
        raise LaunchRefused('financial_capability_implementation_required')
