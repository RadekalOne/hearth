"""Inactive root launch composition with an injected privileged driver.

No concrete OS driver, provider prompt, credential or service activation lives
here. Driver methods must enforce root policy and observe the ORIGINAL host.
Ambiguous failures propagate while retaining the slot/guard; no automatic
cleanup, disarm, adoption or start retry is permitted by this coordinator.
"""
from .creation import CreationRegistry, _digest, read_binding
from .recovery import RecoveryCoordinator
from .store import RecordError, safe_payload, timestamp


class LaunchCoordinator:
    def __init__(self, registry, driver):
        self.registry = registry
        self.store = registry.store
        self.controller = registry.controller
        self.creations = CreationRegistry(registry)
        self.driver = driver

    def _created(self, intent, container_id, proof):
        identity = {'host_id','container_id','workload_id','guard_id','parent_cgroup',
                    'deadline_at','policy_sha256'}
        if (not isinstance(proof,dict)
                or set(proof)!=identity|{'observed_at','container_state','references'}
                or proof['container_state']!='created'
                or proof['container_id']!=container_id
                or any(proof[key]!=intent[key] for key in identity-{'container_id'})
                or not isinstance(proof['references'],list) or not 1<=len(proof['references'])<=100
                or any(not isinstance(v,str) or not v.strip() or len(v)>4096 for v in proof['references'])):
            raise RecordError('independent stopped original-host container/policy proof required')
        observed = timestamp(proof['observed_at']); now = self.store.now()
        if (observed>now or (now-observed).total_seconds()>60 or observed<timestamp(intent['at'])
                or now>=timestamp(intent['deadline_at'])):
            raise RecordError('created-container inspection stale or deadline expired')

    def _before_start(self, claim, registration, binding):
        with self.store.transaction() as db:
            _, _, run = self.store._live_claim(db,self.controller,claim)
            current = self.registry._owned(self.registry._latest(db),run['id'])
            if (safe_payload(current)!=safe_payload(registration) or current['phase']!='launching'
                    or read_binding(db,run['id'])!=binding):
                raise RecordError('start fenced after guarded consume')

    def launch(self, registration, claim, *, host_id):
        """Attempt external creation and start ONCE; status never reauthorizes it.

        The driver's start must itself honor the independently armed original
        deadline/immutable ID: the final DB check cannot close an OS scheduling
        gap. A delayed start must be blocked by the root guard/ID removal.
        """
        preflight=getattr(self.driver,'preflight',None)
        if preflight is not None:preflight(registration,claim,host_id=host_id)
        intent = self.creations.begin(registration,claim,host_id=host_id)
        container_id = self.driver.create_stopped(dict(intent))
        if not _digest(container_id):
            raise RecordError('driver returned no immutable container ID')
        proof = self.driver.inspect_created(dict(intent),container_id)
        self._created(intent,container_id,proof)
        binding = self.creations.bind(registration,claim,host_id=host_id,container_id=container_id)
        self.driver.arm_guard(dict(binding))
        proof = self.driver.inspect_armed(dict(binding))
        consumed = self.creations.consume_armed(claim,binding,proof=proof)
        self._before_start(claim,consumed,binding)
        self.driver.start(dict(binding))
        return {'registration':consumed,'binding':binding}

    def recover(self, run_id, *, outcome):
        """Capture current fencing BEFORE independent original-host inspection.

        No generic release path, no worker result, and no inferred exit from a
        failed start. An exact RecoveryCoordinator packet may separately be
        replayed by trusted root for acknowledgment; this facade inspects anew.
        """
        with self.store.transaction() as db:
            registration = self.registry._owned(self.registry._latest(db),run_id)
            binding = read_binding(db,run_id)
            if binding is None or registration['phase']=='released':
                raise RecordError('unresolved original creation binding required for recovery')
            epoch = db.execute('SELECT restore_epoch FROM record_meta WHERE id=1').fetchone()[0]
            claim = self.store.row(db,'claims',registration['claim_id'])
            generation = claim['generation']
        proof = self.driver.inspect_termination(dict(binding))
        return RecoveryCoordinator(self.registry).recover(registration,expected_epoch=epoch,
            expected_generation=generation,outcome=outcome,proof=proof)
