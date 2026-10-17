"""Append-only Commons files, published through a serialized local git history.

No auth decision is made here: callers must supply a trusted principal. Only
committed blobs are readable; a failed publication can be retried safely.
"""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


KINDS = {
    'glossary': {'distinction', 'review', 'correction', 'sample'},
    'journal': {'prediction', 'outcome', 'review', 'correction', 'sample'},
    'ledger': {'budget', 'spend', 'budget_change', 'result', 'review', 'correction', 'sample'},
    'corpus': {'case', 'observation', 'review', 'correction', 'sample'},
}
ENTRY = re.compile(r'entry_[a-f0-9]{32}\Z')
COMMIT = re.compile(r'[a-f0-9]{40}\Z')
REQUEST = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}\Z')
AUTHOR = re.compile(r'(?:[a-z][a-z0-9_.-]{0,63}|@[a-z0-9_.=-]+:[a-z0-9.-]+)\Z')
MAX_BYTES = 65536
PAGE_CHARS = 4000
PAGE_ENTRIES = 25


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def no_links(path):
    """Reject links/junctions in the configured path and existing ancestors."""
    for part in (path, *path.parents):
        if part.is_symlink() or (hasattr(part, 'is_junction') and part.is_junction()):
            raise ValueError('Filesystem links are not allowed')


class CommonsStore:
    def __init__(self, root):
        self.root = Path(os.path.abspath(root))
        self.files = self.root / 'files'
        self.repo = self.root / 'history.git'

    def _safe(self):
        no_links(self.root)
        for child in (self.files, self.repo, self.root / '.lock'):
            no_links(child)

    @contextmanager
    def _lock(self):
        self._safe()
        self.root.mkdir(parents=True, exist_ok=True)
        lock = open(self.root / '.lock', 'a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                lock.seek(0, 2)
                if lock.tell() == 0:
                    lock.write(b'\0')
                    lock.flush()
                deadline = time.monotonic() + 15
                while True:
                    try:
                        lock.seek(0)
                        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            raise RuntimeError('Commons store is busy; retry the same request')
                        time.sleep(.02)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            self._safe()
            yield
        finally:
            if os.name == 'nt':
                try:
                    lock.seek(0)
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    pass
            lock.close()

    def _git(self, *args, check=True):
        env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        env.update(GIT_TERMINAL_PROMPT='0', GIT_CONFIG_NOSYSTEM='1',
                   GIT_CONFIG_GLOBAL=os.devnull)
        location = [] if args[0] == 'init' else ['--git-dir', str(self.repo), '--work-tree', str(self.files)]
        result = subprocess.run(
            ['git', '-c', 'commit.gpgsign=false', '-c', 'core.autocrlf=false',
             '-c', 'core.fsmonitor=false', '-c', f'core.hooksPath={self.root / "disabled-hooks"}',
             '-c', 'user.name=Commons Writer', '-c', 'user.email=commons@hearth.local',
             *location, *args],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        if check and result.returncode:
            # Do not expose arbitrary git/environment output through tools.
            raise RuntimeError('Commons history publication failed; retry the same request')
        return result

    def _initialize(self):
        self.files.mkdir(exist_ok=True)
        if not self.repo.exists():
            self._git('init', '--bare', '--initial-branch=main', str(self.repo))
        self._git('config', 'core.logAllRefUpdates', 'true')

    def _head(self):
        self._safe()
        if not self.repo.exists():
            return ''
        result = self._git('rev-parse', '--verify', 'HEAD', check=False)
        return result.stdout.decode().strip() if result.returncode == 0 else ''

    def _paths(self, head, collection=None):
        if not head:
            return []
        paths = self._git('ls-tree', '-r', '--name-only', head).stdout.decode().splitlines()
        valid = []
        for value in paths:
            bits = value.split('/')
            if len(bits) != 2 or bits[0] not in KINDS or not bits[1].endswith('.json'):
                raise RuntimeError('Unexpected Commons history path')
            if not ENTRY.fullmatch(bits[1][:-5]):
                raise RuntimeError('Unexpected Commons history entry')
            if collection is None or bits[0] == collection:
                valid.append(value)
        return sorted(valid, key=lambda p: p.split('/')[1])

    def _record(self, head, relative):
        blob = self._git('show', f'{head}:{relative}').stdout
        if len(blob) > MAX_BYTES + 20000:
            raise RuntimeError('Commons record is too large')
        return json.loads(blob.decode('utf-8'))

    def _find(self, entry_id, head=None):
        if not isinstance(entry_id, str) or not ENTRY.fullmatch(entry_id):
            raise ValueError('Invalid entry ID')
        head = self._head() if head is None else head
        for relative in self._paths(head):
            if relative.endswith('/' + entry_id + '.json'):
                return self._record(head, relative)
        raise ValueError('Entry not found')

    @staticmethod
    def _validate(author, collection, kind, content, source_refs, links, request_id):
        if not isinstance(author, str) or not AUTHOR.fullmatch(author) or author in {'admin', 'anonymous'}:
            raise ValueError('Invalid authenticated author')
        if not isinstance(collection, str) or collection not in KINDS:
            raise ValueError('Invalid collection')
        if not isinstance(kind, str) or kind not in KINDS[collection]:
            raise ValueError('Invalid record kind for collection')
        if not isinstance(content, str) or not content.strip() or len(content.encode('utf-8')) > MAX_BYTES:
            raise ValueError('Content must be 1-65536 UTF-8 bytes')
        if not isinstance(request_id, str) or not REQUEST.fullmatch(request_id):
            raise ValueError('Invalid request ID')
        if not isinstance(source_refs, list) or not 1 <= len(source_refs) <= 10 or any(
                not isinstance(v, str) or not v.strip() or len(v) > 512 for v in source_refs):
            raise ValueError('Provide 1-10 nonblank source references of at most 512 characters')
        if not isinstance(links, list) or len(links) > 10 or any(
                not isinstance(v, str) or not ENTRY.fullmatch(v) for v in links):
            raise ValueError('Provide at most ten linked entry IDs')
        if kind in {'outcome', 'review', 'correction', 'spend', 'budget_change', 'result', 'observation'} and not links:
            raise ValueError('This kind requires a linked entry')

    def _publish(self, relative):
        self._git('add', '--', relative)
        self._git('commit', '--only', '-m', f'Create {relative.split("/")[0]}/{self._pending_kind}', '--', relative)

    def create(self, *, author, collection, kind, content, source_refs, links, request_id):
        self._validate(author, collection, kind, content, source_refs, links, request_id)
        payload = dict(author=author, collection=collection, kind=kind, content=content,
                       source_refs=source_refs, links=links, request_id=request_id)
        fingerprint = hashlib.sha256(encoded(payload)).hexdigest()
        entry_id = 'entry_' + hashlib.sha256(encoded([author, request_id])).hexdigest()[:32]
        relative = f'{collection}/{entry_id}.json'
        with self._lock():
            self._initialize()
            head = self._head()
            # The same author/request ID is unique across all collections.
            for path in self._paths(head):
                if path.endswith('/' + entry_id + '.json'):
                    existing = self._record(head, path)
                    if existing['payload_sha256'] != fingerprint:
                        raise ValueError('Request ID already used with a different payload')
                    return self._receipt(existing, replayed=True)
            for link in links:
                try:
                    self._find(link, head)
                except ValueError:
                    raise ValueError('A linked entry does not exist') from None
            for candidate_collection in KINDS:
                pending = self.files / candidate_collection / (entry_id + '.json')
                no_links(pending)
                if pending.exists() and candidate_collection != collection:
                    raise ValueError('Request ID already used with a different payload')
            folder = self.files / collection
            no_links(folder)
            folder.mkdir(exist_ok=True)
            target = self.files / relative
            no_links(target)
            record = dict(entry_id=entry_id, created_at=datetime.now(timezone.utc).isoformat(),
                          payload_sha256=fingerprint, **payload)
            # Recover the uncommitted file left by an interrupted publish.
            if target.exists():
                record = json.loads(target.read_text(encoding='utf-8'))
                if record.get('payload_sha256') != fingerprint:
                    raise ValueError('Request ID already used with a different payload')
            else:
                temporary = None
                try:
                    with tempfile.NamedTemporaryFile(dir=folder, prefix='.pending-', delete=False) as stream:
                        temporary = Path(stream.name)
                        stream.write(encoded(record))
                        stream.flush()
                        os.fsync(stream.fileno())
                    # Atomic exclusive publication: a crash cannot leave a
                    # partially written record at the permanent filename.
                    os.link(temporary, target)
                finally:
                    if temporary is not None:
                        temporary.unlink(missing_ok=True)
            self._pending_kind = kind
            self._publish(relative)
            return self._receipt(record, replayed=False)

    @staticmethod
    def _receipt(record, replayed):
        return dict(entry_id=record['entry_id'], author=record['author'],
                    created_at=record['created_at'], sha256=record['payload_sha256'], replayed=replayed)

    def list(self, collection, cursor=''):
        if not isinstance(collection, str) or collection not in KINDS:
            raise ValueError('Invalid collection')
        head, after = self._head(), ''
        if cursor:
            if not isinstance(cursor, str) or cursor.count(':') != 1:
                raise ValueError('Invalid cursor')
            snapshot, after = cursor.split(':')
            if not COMMIT.fullmatch(snapshot) or not ENTRY.fullmatch(after) or not head:
                raise ValueError('Invalid cursor')
            if self._git('merge-base', '--is-ancestor', snapshot, head, check=False).returncode:
                raise ValueError('Invalid cursor snapshot')
            head = snapshot
        paths = self._paths(head, collection)
        if after and not any(p.endswith('/' + after + '.json') for p in paths):
            raise ValueError('Invalid cursor entry')
        paths = [p for p in paths if p.split('/')[1][:-5] > after]
        selected = paths[:PAGE_ENTRIES]
        entries = []
        for path in selected:
            record = self._record(head, path)
            entries.append({k: record[k] for k in ('entry_id', 'author', 'created_at', 'collection', 'kind', 'links')})
        next_cursor = f'{head}:{entries[-1]["entry_id"]}' if len(paths) > PAGE_ENTRIES else None
        return dict(entries=entries, next_cursor=next_cursor)

    def read(self, entry_id, offset=0):
        if type(offset) is not int or offset < 0 or offset > MAX_BYTES:
            raise ValueError('Invalid read offset')
        record = self._find(entry_id)
        text = record['content']
        if offset > len(text):
            raise ValueError('Invalid read offset')
        return {**record, 'content': text[offset:offset + PAGE_CHARS],
                'offset': offset, 'next_offset': offset + PAGE_CHARS if offset + PAGE_CHARS < len(text) else None}
