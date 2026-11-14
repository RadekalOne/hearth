"""Reproducible non-secret relay configuration/manifest producer. Stdlib only.

build_artifacts can be run against a source checkout on any host. Only the
explicit disabled installer calls write_artifacts; neither function enables work.
"""
import argparse,hashlib,json,os,re
from pathlib import Path,PureWindowsPath

PROGRAM_FILES=('offline_relay.py','offline_relay_state.py','offline_relay_ports.py',
 'offline_relay_windows.py','pause-offline-relay.ps1','relay_matrix.py',
 'relay_native.py','relay_launch.py','relay_live.py','relay_install.py',
 'activate-offline-relay.ps1','install-offline-relay.ps1')
RECOVERY_FILES=('offline_relay_pause.py',)
SEED='$LOWDdF8e9IbDvwo36BkoFITMNzmEpB08jfdJMb1JxKg'
PATHS={'repo':'C:/Users/rslabinski/Projects/hearth2-transfer',
 'matrix_env':'C:/Users/rslabinski/AI Projects/.hearth-matrix-codex.env',
 'auth':'C:/Users/rslabinski/.codex/auth.json',
 'binary':'C:/Users/rslabinski/AppData/Roaming/npm/node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor/x86_64-pc-windows-msvc/bin/codex.exe'}
BINARY_HASH='6f267830b029ee25d9339864aa867cd45de9f8fd4c5ea007d2e63c13a0c66d36'
class InstallRefused(RuntimeError):pass


def configuration():
    return {'version':1,'mode':'intake_capacity_only','host':'RSLABINSKI-PC',
        **PATHS,'binary_sha256':BINARY_HASH,'seed_event':SEED}


def canonical(value):return (json.dumps(value,sort_keys=True,indent=2)+'\n').encode('utf-8')


def no_link(path):
    path=Path(path)
    if path.is_symlink() or (path.exists() and getattr(path.lstat(),'st_file_attributes',0)&0x400):raise InstallRefused('installation_link_refused')


def source_hash(path):
    no_link(path)
    if not path.is_file() or path.stat().st_size>1048576:raise InstallRefused('bounded_source_required')
    return hashlib.sha256(path.read_bytes().decode('utf-8-sig').replace('\r\n','\n').encode()).hexdigest()


def build_artifacts(program,recovery,installation_root,model):
    if type(model) is not str or not re.fullmatch('[A-Za-z0-9 _.()-]{1,128}',model):raise InstallRefused('hardware_model_required')
    root=PureWindowsPath(installation_root);program,recovery=Path(program),Path(recovery)
    config=canonical(configuration())
    manifest={'host':'RSLABINSKI-PC','model':model,'task':'Hearth-Codex-Offline-Relay',
        'program':str(root/'program'),'state':str(root/'relay.sqlite3'),'python':'C:\\Python314\\python.exe',
        'source_hashes':{n:source_hash(program/n) for n in PROGRAM_FILES},
        'recovery_hashes':{n:source_hash(recovery/n) for n in RECOVERY_FILES},'installed_disabled':True,
        'live_config_sha256':hashlib.sha256(config).hexdigest(),'live_coordination':'authenticated_fixed_thread',
        'included_allowance':'capacity_only_not_financial_authority','unattended_launcher':'blocked_financial_boundary_unverified'}
    return config,canonical(manifest)


def write_artifacts(root,model):
    root=Path(root).absolute()
    for p in (root,*root.parents,root/'program',root/'recovery',root/'live-config.json',root/'manifest.json'):no_link(p)
    old=root/'live-config.json'
    if old.exists():
        try:
            if old.stat().st_size>8192:raise ValueError()
            def pairs(items):
                d={}
                for k,v in items:
                    if k in d:raise ValueError()
                    d[k]=v
                return d
            c=json.loads(old.read_text(encoding='utf-8-sig'),object_pairs_hook=pairs);expected=configuration()
            if type(c) is not dict or set(c)!=set(expected) or type(c['version']) is not int:raise ValueError()
            if any((PureWindowsPath(c[k])!=PureWindowsPath(v) if k in PATHS else c[k]!=v) for k,v in expected.items()):raise ValueError()
        except Exception:raise InstallRefused('preserve_unknown_configuration') from None
    config,manifest=build_artifacts(root/'program',root/'recovery',root,model)
    for name,raw in [('live-config.json',config),('manifest.json',manifest)]:
        temp=root/(name+'.new');no_link(temp)
        with temp.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,root/name)
    return {'live_config_sha256':hashlib.sha256(config).hexdigest(),'manifest_sha256':hashlib.sha256(manifest).hexdigest(),'mode':'intake_capacity_only','enabled':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--model',required=True);args=p.parse_args()
    if os.name!='nt' or os.environ.get('COMPUTERNAME')!='RSLABINSKI-PC':raise InstallRefused('approved_host_required')
    expected=Path(os.environ.get('LOCALAPPDATA',''))/'Hearth/OfflineRelay'
    if args.root.absolute()!=expected.absolute():raise InstallRefused('fixed_installation_required')
    print(json.dumps(write_artifacts(args.root,args.model),sort_keys=True))


if __name__=='__main__':main()
