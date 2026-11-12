"""Harmless, credential-free isolation probe; no package/model/production call."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

checks={'uid':os.geteuid(),'credentials_absent':not any(os.environ.get(x) for x in
    ['OPENAI_API_KEY','CODEX_API_KEY','HEARTH_MEMORY_TOKEN','SSH_AUTH_SOCK']),
    'docker_socket_absent':not Path('/var/run/docker.sock').exists(),
    'network_interfaces':sorted(x.name for x in Path('/sys/class/net').iterdir())}
try:Path('/etc/hearth-offline-test').write_text('must refuse');checks['readonly_root']=False
except OSError:checks['readonly_root']=True
try:
    with socket.create_connection(('192.0.2.1',443),timeout=.2):checks['egress_denied']=False
except OSError:checks['egress_denied']=True
Path('/work/ok').write_text('private fixture scratch')
checks['scratch_writable']=True
child=subprocess.Popen([sys.executable,'-I','-c','import time;time.sleep(15)'])
checks['child_pid']=child.pid
print(json.dumps(checks),flush=True)
time.sleep(15)
