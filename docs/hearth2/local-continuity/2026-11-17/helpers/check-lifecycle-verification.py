import hashlib,json,pathlib,subprocess,tarfile,sys
root=pathlib.Path.cwd();manifest=json.loads((root/'.superpowers/session-lifecycle-release-manifest.json').read_text());snapshot=pathlib.Path(manifest['snapshot'])
bad=[name for name,value in manifest['files'].items() if hashlib.sha256((root/name).read_bytes()).hexdigest()!=value or hashlib.sha256((snapshot/name).read_bytes()).hexdigest()!=value]
print('Python source/test byte equality:',len(manifest['files']),'files; differences:',bad)
if bad:sys.exit(1)
archive=root/'.superpowers/session-lifecycle-release-source.tar.gz'
files=subprocess.check_output(['git','ls-files','-z']).decode().split('\0')
with tarfile.open(archive,'w:gz') as output:
    for name in filter(None,files):
        if (snapshot/name).is_file():output.add(snapshot/name,arcname=name,recursive=False)
print('Source archive SHA256',hashlib.sha256(archive.read_bytes()).hexdigest())
