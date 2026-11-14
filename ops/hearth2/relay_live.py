"""Verified live intake + capacity, explicitly gated inference. No hidden fallback."""
import hashlib,json,os,uuid
from contextlib import contextmanager
from datetime import datetime,timezone
from pathlib import Path
from relay_matrix import MatrixClient,MatrixIntake,decode
from relay_native import NativeSession,read_selected_auth,assess_capacity
from relay_launch import Launcher,snapshot

REPO=Path('C:/Users/rslabinski/Projects/hearth2-transfer')
MATRIX_ENV=Path('C:/Users/rslabinski/AI Projects/.hearth-matrix-codex.env')
AUTH=Path('C:/Users/rslabinski/.codex/auth.json')
BINARY=Path('C:/Users/rslabinski/AppData/Roaming/npm/node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe')
BINARY_HASH='6f267830b029ee25d9339864aa867cd45de9f8fd4c5ea007d2e63c13a0c66d36'
MODE='intake_capacity_only'
class LiveUnavailable(RuntimeError):pass


def load_configuration(root):
    root=Path(root);p=root/'live-config.json';manifest=root/'manifest.json'
    try:
        if p.is_symlink() or manifest.is_symlink() or p.stat().st_size>8192 or manifest.stat().st_size>32768:raise ValueError()
        raw=p.read_bytes();m=decode(manifest.read_bytes());c=decode(raw)
        if m.get('live_config_sha256')!=hashlib.sha256(raw).hexdigest():raise ValueError()
        if set(c)!={'version','mode','host','repo','matrix_env','auth','binary','binary_sha256','seed_event'}:raise ValueError()
        if (c['version']!=1 or c['mode']!=MODE or c['host']!='RSLABINSKI-PC' or c['binary_sha256']!=BINARY_HASH
            or any(Path(c[k])!=v for k,v in [('repo',REPO),('matrix_env',MATRIX_ENV),('auth',AUTH),('binary',BINARY)])
            or type(c['seed_event']) is not str or not c['seed_event'].startswith('$') or len(c['seed_event'])>200):raise ValueError()
        return c
    except Exception:raise LiveUnavailable('live_configuration_unverified') from None


def verify_activation_review(client,event_id,manifest_sha256):
    """Review is evidence, never paid authority. Bind exact installed bytes."""
    from relay_matrix import content,CLAUDE
    try:
        event=client.event(event_id);body=content(event)
        if event.get('sender')!=CLAUDE or not body.startswith('[REVIEW]'):raise ValueError()
        from relay_matrix import review_packet
        packet=review_packet(body)
        expected={'hearth_relay_activation_review':{'verdict':'pass','mode':MODE,'manifest_sha256':manifest_sha256}}
        if packet!=expected:raise ValueError()
        return True
    except Exception:raise LiveUnavailable('exact_claude_activation_review_required') from None


class MetadataOwner:
    """Original invocation fence + durable named process-tree ownership.
    The same writer lock serializes spawn against the independent pause latch.
    """
    def __init__(self,state,original,*,diagnostic=False):
        self.state,self.original,self.diagnostic=state,dict(original),diagnostic
    def active(self):
        c=self.state.control()
        return all(c[k]==self.original[k] for k in ('paused','enabled','epoch'))
    @contextmanager
    def start(self,factory):
        ident=uuid.uuid4().hex;native=None;failure=None
        with self.state.tx() as db:
            c=dict(db.execute('SELECT * FROM control WHERE id=1').fetchone())
            if (any(c[k]!=self.original[k] for k in ('paused','enabled','epoch'))
                or (not self.diagnostic and (c['paused'] or not c['enabled']))
                or db.execute("SELECT 1 FROM jobs WHERE state IN ('claimed','dispatching','active','held')").fetchone()):raise LiveUnavailable('metadata_original_invocation_or_slot_unavailable')
            body=json.dumps({'work_id':'metadata-'+ident,'generation':1,'aliases':[],'kind':'windows','scope':'read-only-metadata'})
            db.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,NULL)',(ident,'metadata-'+ident,1,'active',c['epoch'],body))
            try:native=factory(ident,self.active)
            except BaseException as error:
                failure=error;db.execute("UPDATE jobs SET state='held',receipt=? WHERE id=?",(json.dumps({'reason':'metadata_start_outcome_unknown','confirmed_empty':False}),ident))
        if failure:raise LiveUnavailable('metadata_start_outcome_unknown') from None
        try:yield native
        finally:
            try:empty=native.close() is True
            except BaseException:empty=False
            with self.state.tx() as db:
                row=db.execute('SELECT state FROM jobs WHERE id=?',(ident,)).fetchone()
                if row and row['state']!='paused':
                    db.execute('UPDATE jobs SET state=?,receipt=? WHERE id=?',('complete' if empty else 'held',json.dumps({'confirmed_empty':empty,'reason':'metadata_stopped' if empty else 'metadata_stop_unknown'}),ident))


class LivePorts:
    def __init__(self,state,intake,observe,*,config=None,client=None):
        self.state,self.intake,self.observe,self.config,self.client=state,intake,observe,config,client
        self.last=None
    @classmethod
    def installed(cls,state,*,diagnostic=False):
        original=state.control();c=load_configuration(state.path.parent);client=MatrixClient.from_env_file(c['matrix_env']);intake=MatrixIntake(state,client)
        def observe():
            before=hashlib.sha256(AUTH.read_bytes()).hexdigest();auth=read_selected_auth(AUTH,datetime.now(timezone.utc))
            fence=MetadataOwner(state,original,diagnostic=diagnostic)
            def factory(ident,active):return NativeSession.pinned(BINARY,BINARY_HASH,state.path.parent/'native-homes',auth=auth,timeout=10,check_active=active,job_id=ident)
            with fence.start(factory) as native:observation=native.metadata()
            if not native.confirmed_empty or hashlib.sha256(AUTH.read_bytes()).hexdigest()!=before:raise LiveUnavailable('native_cleanup_or_profile_changed')
            return assess_capacity(observation,datetime.now(timezone.utc)),observation
        return cls(state,intake,observe,config=c,client=client)
    def poll(self):
        original=self.state.control()
        started=datetime.now(timezone.utc).isoformat();receipt={'started_at':started,'intake_complete':False,'native_complete':False,
            'mode':MODE,'model_turns':0,'inference_authorized':False,'understanding':'unknown','task_state':'unchanged'}
        try:
            events=self.intake.poll();receipt['intake_complete']=True;receipt['pending']=len(events)
            with self.state.connect() as db:
                row=db.execute('SELECT event_id FROM relay_cursor WHERE id=1').fetchone() if db.execute("SELECT 1 FROM sqlite_master WHERE name='relay_cursor'").fetchone() else None
            receipt['processed_through']=row[0] if row else None
            try:
                if any(self.state.control()[k]!=original[k] for k in ('paused','enabled','epoch')):
                    receipt['error']='invocation_revoked';return events
                receipt['capacity'],receipt['native']=self.observe();receipt['native_complete']=True
            except Exception:receipt['error']='native_metadata_unavailable'
        except Exception:
            receipt['error']='intake_unavailable_or_gap';raise
        finally:
            receipt['completed_at']=datetime.now(timezone.utc).isoformat();self.last=receipt
            root=self.state.path.parent;p=root/'live-receipt.json';temp=root/'live-receipt.json.new'
            if p.is_symlink() or temp.is_symlink():raise LiveUnavailable('receipt_path_link')
            temp.write_text(json.dumps(receipt,sort_keys=True,indent=2),encoding='utf-8');os.replace(temp,p)
        return events
    def bootstrap(self):
        with self.state.connect() as db:row=db.execute('SELECT event_id FROM relay_cursor WHERE id=1').fetchone()
        if not row:self.intake.bootstrap(self.config['seed_event'])
    def ready_for_claim(self):return False # Financial route absent: preserve pending work/generation.
    def poll_status(self):return 'enabled_inference_gated' if self.last and self.last['native_complete'] else 'enabled_metadata_unavailable'
    def verify(self,work):return self.intake.verify(work)
    def base_commit(self):
        import subprocess
        value=subprocess.run(['git','--no-replace-objects','rev-parse','HEAD'],cwd=REPO,capture_output=True,text=True,timeout=5,check=True)
        return value.stdout.strip()
    def allowance(self):return {'source':'verified_capacity_only','included_only':False,'fresh':bool(self.last and self.last['native_complete']),'fallback':False}
    def launch(self,job):
        # Concrete durable refusal until separately reviewed financial capability.
        files=snapshot(REPO,job['base_commit'],job['paths'])
        return Launcher(self.state,self.state.path.parent/'candidates').run(job,observation=(self.last or {}).get('native',{}),snapshot=files,approval=None,financial_boundary=None)
    def post(self,room,thread,text):
        if self.client is None:raise LiveUnavailable('fixed_live_post_unavailable')
        return self.client.post(room,thread,text)
