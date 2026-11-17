import os,pathlib,signal
for snapshot in ['/tmp/hearth2-lifecycle-t9m3x4b7']:
    for proc in pathlib.Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:
            if str((proc/'cwd').resolve())==snapshot and b'unittest' in (proc/'cmdline').read_bytes():
                os.kill(int(proc.name),signal.SIGTERM);print('Stopped superseded test snapshot',snapshot,'pid',proc.name)
        except (OSError,ProcessLookupError):pass


