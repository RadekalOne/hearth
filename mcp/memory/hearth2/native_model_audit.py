"""Bounded root-only decision journal, outside the native worker namespace."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import stat
from .native_model_guard import ModelAuditUnavailable
from .native_rpc import canonical_object


class RootModelDecisionJournal:
    def __init__(self,directory,*,max_file=4_000_000,max_row=65536):
        self.directory=Path(directory)
        if (type(max_file) is not int or type(max_row) is not int
                or not 128<=max_row<=65536 or not max_row<=max_file<=4_000_000):
            raise ModelAuditUnavailable('invalid journal bounds')
        self.max_file,self.max_row=max_file,max_row

    @contextmanager
    def _file(self,write):
        import fcntl
        directory=fd=None
        try:
            if (os.geteuid()!=0 or not self.directory.is_absolute()
                    or self.directory.resolve()!=self.directory):raise ValueError()
            directory=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
            meta=os.fstat(directory)
            if meta.st_uid!=0 or stat.S_IMODE(meta.st_mode)!=0o700:raise ValueError()
            flags=(os.O_RDWR|os.O_CREAT|os.O_APPEND) if write else os.O_RDONLY
            try:fd=os.open('model-decisions.jsonl',flags|os.O_NOFOLLOW|os.O_NONBLOCK,0o600,dir_fd=directory)
            except FileNotFoundError:
                if not write:yield None,directory;return
                raise
            meta=os.fstat(fd)
            if (not stat.S_ISREG(meta.st_mode) or meta.st_uid!=0 or meta.st_nlink!=1
                    or stat.S_IMODE(meta.st_mode)!=0o600 or meta.st_size>self.max_file):raise ValueError()
            fcntl.flock(fd,(fcntl.LOCK_EX if write else fcntl.LOCK_SH)|fcntl.LOCK_NB)
            yield fd,directory
        except ModelAuditUnavailable:raise
        except Exception:raise ModelAuditUnavailable('root model audit unavailable') from None
        finally:
            if fd is not None:os.close(fd)
            if directory is not None:os.close(directory)

    def _read(self,fd):
        if fd is None:return []
        os.lseek(fd,0,os.SEEK_SET);raw=b''
        while True:
            chunk=os.read(fd,min(65536,self.max_file+1-len(raw)))
            if not chunk:break
            raw+=chunk
            if len(raw)>self.max_file:raise ModelAuditUnavailable('model audit capacity exceeded')
        if raw and not raw.endswith(b'\n'):raise ModelAuditUnavailable('incomplete model audit')
        rows=[]
        for i,line in enumerate(raw.splitlines(),1):
            if len(line)+1>self.max_row:raise ModelAuditUnavailable('model audit row bound')
            row=json.loads(line)
            if (type(row.get('audit_seq')) is not int or row['audit_seq']!=i
                    or canonical_object(row)!=line):raise ModelAuditUnavailable('invalid model audit sequence')
            rows.append(row)
        return rows

    def read_records(self):
        with self._file(False) as (fd,_):return self._read(fd)

    def record(self,decision):
        with self._file(True) as (fd,directory):
            if type(decision) is not dict or 'audit_seq' in decision:raise ModelAuditUnavailable('invalid model decision')
            rows=self._read(fd)
            raw=canonical_object({**decision,'audit_seq':len(rows)+1})+b'\n'
            if len(raw)>self.max_row or os.fstat(fd).st_size+len(raw)>self.max_file:
                raise ModelAuditUnavailable('model audit capacity exceeded')
            remaining=raw
            while remaining:
                n=os.write(fd,remaining)
                if not n:raise ModelAuditUnavailable('model audit write failed')
                remaining=remaining[n:]
            os.fsync(fd);os.fsync(directory)
            return True
