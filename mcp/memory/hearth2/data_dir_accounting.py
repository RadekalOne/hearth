"""Inactive fixture acquisition -> pinned source accounting, not scan authority.

No discovery, native execution or physical enrollment. The conditional map only
supports Pi auth, root config and explicitly scoped OAuth store/state files.
Other roles remain unscanned. Private bodies never appear in public results.
"""
from dataclasses import dataclass,field
import hashlib
import os

from .credential_sources import (CredentialSourceAccounting,SourceObservation,
    SourceAccountingSummary,_manifest)
from .credential_coverage import CoverageSummary
from .data_dir_files import DirectoryFileCapture,_FileWork
from .data_dir_metadata import _Failed
from .store import RecordError


def _refuse():raise RecordError('unsupported directory source accounting request') from None


@dataclass(frozen=True,slots=True,repr=False)
class _Body:
    digest:bytes
    raw:bytes=field(compare=False)


@dataclass(frozen=True,slots=True)
class DirectorySourceResult:
    state:str
    reason:str|None
    coverage:CoverageSummary|None
    accounting:SourceAccountingSummary|None
    metadata_work:int
    bytes_read:int
    read_attempts:int
    file_outcomes:tuple


class DirectorySourceCapture(DirectoryFileCapture):
    def _read_body(self,fd,work):
        chunks=[];length=0;digest=hashlib.sha256()
        while length<65537:
            raw=work.read(fd,min(8192,65537-length))
            if not raw:break
            chunks.append(raw);digest.update(raw);length+=len(raw)
        return length,_Body(digest.digest(),b''.join(chunks))

    def _bindings(self,requirements,manifest,begin):
        self._validate(requirements,begin)
        _,limits,entries,_,oauth,_=_manifest(manifest)
        if (manifest.context!=requirements.scope.context
                or type(self.max_bytes) is not int or not 1<=self.max_bytes<=1048576
                or len(entries)!=len(requirements.sources)):_refuse()
        expected_groups={g.group_id:tuple(e.source_id for e in manifest.entries if e.group_id==g.group_id)
                         for g in manifest.oauth_groups+manifest.selection_groups}
        if dict(requirements.groups)!=expected_groups:_refuse()
        for group in oauth.values():
            if group.data_directory_id!=requirements.scope.root_id:_refuse()
        for source in requirements.sources:
            entry=entries.get(source.source_id)
            if entry is None or entry.kind!=source.kind:_refuse()
            if source.path is None:continue
            if source.kind=='pi-auth':expected=('codex-auth.json',)
            elif source.kind=='mcode-config':expected=('config.yaml',)
            elif source.kind in ('oauth-store','oauth-state'):
                group=oauth[entry.group_id]
                expected=('auth',group.build_env,group.region,'mcode-public',
                          'auth.json' if source.kind=='oauth-store' else 'auth-state.json')
            else:_refuse()
            if source.path!=expected:_refuse()
        return limits

    def capture(self,requirements,manifest,*,begin):
        try:
            limits=self._bindings(requirements,manifest,begin)
            work=_FileWork(self.max_entries,min(self.timeout_seconds,limits['seconds']),
                           self.monotonic,min(self.max_bytes,limits['bytes']))
        except (RecordError,TypeError,ValueError,AttributeError,OverflowError):_refuse()
        try:
            a=self._pass(requirements,work);b=self._pass(requirements,work)
            coverage=self._summarize(requirements,a,b,begin,work)
            observed=self.clock();observations=[];outcomes=[]
            for i,source in enumerate(requirements.sources):
                state=coverage.source_statuses[i][2]
                reason,body=b[3].get(source.source_id,(None,None))
                outcomes.append((i,state,reason))
                # Unsupported filesystem objects are known unreadable material,
                # never absence. Non-file/unmapped roles stay unscanned.
                packet_state='unreadable' if state=='unsupported' else state
                raw=None
                if state=='present':
                    if type(body) is not _Body:raise _Failed('changed')
                    raw=body.raw
                observations.append(SourceObservation(manifest.context,source.source_id,
                    source.kind,packet_state,observed,'conditional-private-file-acquisition',raw))
            accounting=CredentialSourceAccounting(clock=self.clock,monotonic=self.monotonic).account(
                manifest,tuple(observations),begin=begin)
            work.tick()
            return DirectorySourceResult('sources-accounted',None,coverage,accounting,
                work.count,work.bytes_read,work.read_attempts,tuple(outcomes))
        except _Failed as exc:reason=exc.reason
        except OSError:reason='unavailable'
        except (RecordError,TypeError,ValueError,AttributeError,OverflowError):_refuse()
        return DirectorySourceResult('unscanned',reason,None,None,work.count,
                                     work.bytes_read,work.read_attempts,())
