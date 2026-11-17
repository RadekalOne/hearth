import hashlib,json,pathlib,tarfile,sys
root=pathlib.Path.cwd();manifest=json.loads((root/'.superpowers/session-lifecycle-release-manifest.json').read_text())
archive=root/'.superpowers/session-lifecycle-release-source.tar.gz'
with tarfile.open(archive) as stored:
    bad=[name for name,value in manifest['files'].items() if hashlib.sha256((root/name).read_bytes()).hexdigest()!=value or hashlib.sha256(stored.extractfile(name).read()).hexdigest()!=value]
print('Post-commit byte equality:',len(manifest['files']),'Python files; differences:',bad)
print('Source archive SHA256',hashlib.sha256(archive.read_bytes()).hexdigest())
sys.exit(bool(bad))
