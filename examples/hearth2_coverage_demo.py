"""Run four synthetic coverage cases; no credential files are opened."""
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import stat
import sys

sys.path.insert(0,str(Path(__file__).parents[1]/'mcp/memory'))
from hearth2.credential_coverage import (
    CoverageScope,CoverageSource,CoverageRequirements,CoverageObservation,
    CoverageNode,DirectorySnapshot,DirectoryEntry,AbsenceEvidence,CoverageAccounting)
from hearth2.credential_sources import SourceContext
from hearth2.store import RecordError


def examples():
    now=datetime(2026,11,4,tzinfo=timezone.utc)
    scope=CoverageScope(SourceContext('sha256:'+'a'*64,None,'b'*64,'c'*64),
        'SYNTHETIC-ROOT','SYNTHETIC-BATCH','SYNTHETIC-ROUND',7)
    branch=('auth','prod','en','mcode-public')
    store=CoverageSource('store','oauth-store',branch+('auth.json',))
    state=CoverageSource('state','oauth-state',branch+('auth-state.json',))
    projection=CoverageSource('projection','projection-namespaced',
        ('cli-auth','prod','en','local-runtime.auth.json'))
    accounting=CoverageAccounting(clock=lambda:now)

    def proof(path,entries=(),inode=20):
        snapshot=DirectorySnapshot(scope,path,7,1,inode,stat.S_IFDIR|0o700,1000,1000,
            2,100,101,now,entries)
        return AbsenceEvidence(snapshot,snapshot)

    requirements=CoverageRequirements.create(scope,(store,state),(('pair',('store','state')),))
    missing=CoverageNode(scope,branch,now,proof(branch[:-1]))
    absent=accounting.account(requirements,(),(missing,),begin=now)
    store_proof=proof(branch,(DirectoryEntry('auth-state.json','regular'),))
    partial=accounting.account(requirements,(
        CoverageObservation(scope,'store','absent',now,store_proof),
        CoverageObservation(scope,'state','present',now)),(),begin=now)
    requirements=CoverageRequirements.create(scope,(store,state,projection),(('pair',('store','state')),))
    present=CoverageObservation(scope,'projection','present',now)
    distinct=accounting.account(requirements,(present,),(missing,),begin=now)
    wrong=CoverageNode(scope,projection.path[:-1],now,proof(projection.path[:-2],inode=21))
    rejected=False
    try:accounting.account(requirements,(present,),(missing,wrong),begin=now)
    except RecordError:rejected=True
    if not rejected:raise AssertionError('contradictory coverage must refuse')
    return [
        dict(case='absent',label='Namespace absent',outcome='Supplied evidence accepted',
             summary=asdict(absent),files=['auth.json','auth-state.json']),
        dict(case='partial',label='Store missing',outcome='State file remains present',
             summary=asdict(partial),files=['auth.json','auth-state.json']),
        dict(case='projection',label='Projection present',outcome='Other branch remains visible',
             summary=asdict(distinct),files=['auth.json','auth-state.json','local-runtime.auth.json']),
        dict(case='conflict',label='Conflicting coverage',outcome='Contradictory packet refused',
             summary=None,files=['auth.json','auth-state.json','local-runtime.auth.json'])]


if __name__=='__main__':
    print(json.dumps(examples(),indent=2))
