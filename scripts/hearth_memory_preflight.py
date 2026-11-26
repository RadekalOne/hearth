"""Read-only rehearsal and maintenance checks for a local Hearth Memory writer."""

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import subprocess
import sys
import tarfile
from urllib import request


class PreflightError(Exception):
    pass


class NoHealthRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


@dataclass(frozen=True)
class Target:
    hostname: str
    writer: str
    volume: str
    data_path: str


CONTAINER_FORMAT = (
    '{"id":{{json .Id}},"name":{{json .Name}},"running":{{json .State.Running}},'
    '"started":{{json .State.StartedAt}},"image":{{json .Image}},"mounts":{{json .Mounts}}}'
)
RUNNER_FORMAT = (
    '{{range .Config.Env}}{{if eq (index (split . "=") 0) "HEARTH2_ENABLED"}}'
    '{{println .}}{{end}}{{end}}'
)
OCI_INDEX = 'application/vnd.oci.image.index.v1+json'
OCI_MANIFEST = 'application/vnd.oci.image.manifest.v1+json'


def verify_live(target, hostname, volume, containers, runner):
    if hostname != target.hostname:
        raise PreflightError('hostname differs from the expected target')
    if volume.get('Driver') != 'local' or volume.get('Mountpoint') != target.data_path:
        raise PreflightError('local volume mountpoint differs from the expected data path')
    writers = [entry for entry in containers if entry['name'] == '/' + target.writer
               and entry['running']]
    if len(writers) != 1:
        raise PreflightError('expected exactly one matching running writer')
    writer = writers[0]
    data = {
        'Type': 'volume', 'Name': target.volume, 'Source': target.data_path,
        'Destination': '/data', 'RW': True,
    }
    app_mounts = [mount for mount in writer['mounts'] if mount.get('Destination') == '/data']
    if len(app_mounts) != 1 or any(app_mounts[0].get(k) != v for k, v in data.items()):
        raise PreflightError('writer /data mount differs from the expected writable volume')
    primary = PurePosixPath(target.data_path)
    for entry in containers:
        if entry is writer or not entry['running']:
            continue
        for mount in entry['mounts']:
            source = PurePosixPath(mount.get('Source') or '.')
            overlaps = source == primary or source in primary.parents or primary in source.parents
            named = mount.get('Type') == 'volume' and mount.get('Name') == target.volume
            if mount.get('RW') and (named or (source.is_absolute() and overlaps)):
                raise PreflightError('another running container can write to the data volume')
    if tuple(runner) != ('HEARTH2_ENABLED=false',):
        raise PreflightError('shared runner must be explicitly off (HEARTH2_ENABLED=false)')
    return writer


def docker(*args):
    env = {key: value for key, value in os.environ.items()
           if key not in {'DOCKER_CONTEXT', 'DOCKER_HOST', 'DOCKER_TLS', 'DOCKER_TLS_VERIFY'}}
    try:
        result = subprocess.run(
            ('docker', '--host', 'unix:///var/run/docker.sock', *args), env=env,
            check=True, capture_output=True, text=True, encoding='utf-8', timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        raise PreflightError(f'local Docker read failed ({args[0]} {args[1]})') from None
    return result.stdout.strip()


def read_live(target, health_port):
    hostname = socket.gethostname().split('.')[0]
    if hostname != target.hostname:
        raise PreflightError('hostname differs from the expected target')
    path = PurePosixPath(target.data_path)
    if not path.is_absolute() or path == path.root or os.path.realpath(path) != target.data_path:
        raise PreflightError('expected data path must be an absolute, canonical volume path')
    volume_format = '{"Driver":{{json .Driver}},"Mountpoint":{{json .Mountpoint}}}'
    volume = json.loads(docker('volume', 'inspect', '--format', volume_format, target.volume))
    ids = docker('container', 'ls', '--quiet', '--no-trunc').splitlines()
    containers = []
    if ids:
        output = docker('container', 'inspect', '--format', CONTAINER_FORMAT, *ids)
        containers = [json.loads(line) for line in output.splitlines()]
    runner = docker('container', 'inspect', '--format', RUNNER_FORMAT, target.writer).splitlines()
    writer = verify_live(target, hostname, volume, containers, runner)
    if not 1 <= health_port <= 65535:
        raise PreflightError('health port is outside 1–65535')
    opener = request.build_opener(request.ProxyHandler({}), NoHealthRedirect())
    endpoint = f'http://127.0.0.1:{health_port}/health'
    try:
        with opener.open(endpoint, timeout=8) as response:
            if response.geturl() != endpoint:
                raise PreflightError('local health redirected from the expected endpoint')
            health = json.loads(response.read(65537))
    except (OSError, ValueError):
        raise PreflightError('local health read failed') from None
    if not isinstance(health, dict) or health.get('memory') != 'ok' or health.get('homeserver') != 'ok':
        raise PreflightError('local health did not report memory and homeserver ok')
    return writer


def artifact(directory, name):
    path = directory / name
    if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
        raise PreflightError(f'missing, empty, or linked artifact: {name}')
    return path


def verify_hashes(directory, manifest, names):
    entries = {}
    for line in artifact(directory, manifest).read_text(encoding='ascii').splitlines():
        match = re.fullmatch(r'([a-f0-9]{64}) [ *]([A-Za-z0-9._-]+)', line)
        if not match or match[2] in entries:
            raise PreflightError(f'invalid checksum manifest: {manifest}')
        entries[match[2]] = match[1]
    if set(entries) != set(names):
        raise PreflightError(f'unexpected artifact list in checksum manifest: {manifest}')
    for name, digest in entries.items():
        with artifact(directory, name).open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise PreflightError(f'checksum mismatch: {name}')


def verify_cold_archive(path):
    required = {'work.sqlite3', 'chroma/chroma.sqlite3'}
    seen = set()
    with tarfile.open(path, 'r:') as archive:
        for member in archive:
            relative = PurePosixPath(member.name)
            if (relative.is_absolute() or '..' in relative.parts or '\\' in member.name
                    or not (member.isfile() or member.isdir()) or relative in seen):
                raise PreflightError('unsafe cold archive member or duplicate path')
            seen.add(relative)
            name = str(relative)
            if name in required:
                if (not member.isfile() or member.size < 100
                        or archive.extractfile(member).read(16) != b'SQLite format 3\x00'):
                    raise PreflightError(f'invalid SQLite file in cold archive: {name}')
                required.remove(name)
    if required:
        raise PreflightError('cold archive missing required file(s): ' + ', '.join(sorted(required)))


def read_oci_member(archive, name):
    try:
        member = archive.getmember(name)
    except KeyError:
        raise PreflightError(f'missing OCI blob or index: {name}') from None
    if not member.isfile():
        raise PreflightError('OCI archive contains a non-file blob or index')
    return member


def verify_oci(path, expected_id):
    with tarfile.open(path, 'r:') as archive:
        tree = json.load(archive.extractfile(read_oci_member(archive, 'index.json')))
        roots = [item for item in tree['manifests'] if item['digest'] == expected_id]
        if len(roots) != 1 or roots[0]['mediaType'] not in {OCI_INDEX, OCI_MANIFEST}:
            raise PreflightError('exact rollback image is absent or ambiguous in the OCI index')
        seen = set()

        def verify(descriptor):
            image_id = descriptor['digest']
            if not re.fullmatch(r'sha256:[a-f0-9]{64}', image_id):
                raise PreflightError('invalid OCI blob digest')
            if image_id in seen:
                return
            seen.add(image_id)
            digest = image_id.removeprefix('sha256:')
            member = read_oci_member(archive, 'blobs/sha256/' + digest)
            if member.size != descriptor['size']:
                raise PreflightError('OCI blob size mismatch')
            stream = archive.extractfile(member)
            if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
                raise PreflightError('OCI blob checksum mismatch')
            kind = descriptor['mediaType']
            if kind == OCI_INDEX:
                stream.seek(0)
                children = json.load(stream)['manifests']
            elif kind == OCI_MANIFEST:
                stream.seek(0)
                content = json.load(stream)
                children = [content['config'], *content['layers']]
            else:
                return
            if not children:
                raise PreflightError('OCI image index has no child descriptors')
            for child in children:
                verify(child)

        verify(roots[0])


def verify_release(directory, running_image):
    image_id = artifact(directory, 'image-id').read_text(encoding='ascii').strip()
    if not re.fullmatch(r'sha256:[a-f0-9]{64}', image_id) or image_id != running_image:
        raise PreflightError('rollback image ID differs from the running writer image')
    verify_hashes(directory, 'cold-data.sha256', ('cold-data.tar',))
    verify_hashes(directory, 'runtime.before.sha256', ('compose.before.json', 'image.before.oci.tar'))
    config = json.loads(artifact(directory, 'compose.before.json').read_text(encoding='utf-8'))
    if not isinstance(config, dict) or not config.get('services'):
        raise PreflightError('saved Compose file has no services')
    baseline = json.loads(artifact(directory, 'health.before.public.json').read_text(encoding='utf-8'))
    if (not isinstance(baseline, dict) or baseline.get('memory') != 'ok' or baseline.get('homeserver') != 'ok'
            or not baseline.get('version') or not baseline.get('build_commit')
            or any(type(baseline.get(key)) is not int or baseline[key] < 0
                   for key in ('drawers', 'checkpoints', 'relays'))):
        raise PreflightError('archived health baseline is incomplete or unhealthy')
    verify_cold_archive(directory / 'cold-data.tar')
    verify_oci(directory / 'image.before.oci.tar', image_id)
    return image_id


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True, help='Expected short hostname')
    parser.add_argument('--writer', required=True, help='Expected running container name')
    parser.add_argument('--volume', required=True, help='Expected local Docker volume name')
    parser.add_argument('--data-path', required=True, help='Expected canonical host path to the volume')
    parser.add_argument('--health-port', type=int, default=8010)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--live-only', action='store_true', help='Check runtime identity and readiness only')
    mode.add_argument('--release-dir', type=Path, help='Also check a retained release for this writer image')
    args = parser.parse_args()
    target = Target(args.host, args.writer, args.volume, args.data_path)
    try:
        writer = read_live(target, args.health_port)
        if args.release_dir is not None:
            image_id = verify_release(args.release_dir, writer['image'])
            if docker('image', 'inspect', '--format', '{{.Id}}', image_id) != image_id:
                raise PreflightError('exact rollback image is not available to the local Docker engine')
            if read_live(target, args.health_port) != writer:
                raise PreflightError('running writer changed during artifact verification')
            print(f'PASS: backup and exact rollback image verified ({image_id})')
        print('PASS: expected local writer and volume, shared runner off, Memory and homeserver healthy')
    except PreflightError as error:
        print(f'STOP: {error}', file=sys.stderr)
        return 1
    except (OSError, ValueError, TypeError, KeyError, tarfile.TarError):
        print('STOP: could not read valid Docker metadata or recovery artifacts', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
