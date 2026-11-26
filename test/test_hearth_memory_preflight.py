import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest

from scripts.hearth_memory_preflight import PreflightError, Target, verify_live, verify_release


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_tar(path, members):
    with tarfile.open(path, 'w') as archive:
        for name, contents in members:
            entry = tarfile.TarInfo(name)
            entry.size = len(contents)
            archive.addfile(entry, io.BytesIO(contents))


class TargetTests(unittest.TestCase):
    def setUp(self):
        self.target = Target('fixture-host', 'memory', 'memory-data', '/srv/memory/_data')
        self.mount = {
            'Type': 'volume', 'Name': 'memory-data', 'Source': '/srv/memory/_data',
            'Destination': '/data', 'RW': True,
        }
        self.volume = {'Driver': 'local', 'Mountpoint': '/srv/memory/_data'}
        self.writer = {'name': '/memory', 'running': True, 'mounts': [self.mount]}
        self.containers = [self.writer]

    def check(self, host='fixture-host', runner=('HEARTH2_ENABLED=false',)):
        return verify_live(self.target, host, self.volume, self.containers, runner)

    def test_matching_host_writer_and_runner_pass(self):
        self.assertIs(self.check(), self.writer)

    def test_wrong_host_fails(self):
        with self.assertRaisesRegex(PreflightError, 'hostname'):
            self.check(host='another-host')

    def test_wrong_volume_fails(self):
        self.mount['Name'] = 'different-volume'
        with self.assertRaisesRegex(PreflightError, '/data mount'):
            self.check()

    def test_missing_writer_fails(self):
        self.containers = []
        with self.assertRaisesRegex(PreflightError, 'running writer'):
            self.check()

    def test_second_consumer_using_an_overlapping_bind_fails(self):
        self.containers.append({'name': '/other', 'running': True, 'mounts': [
            {'Type': 'bind', 'Source': '/srv/memory', 'Destination': '/other', 'RW': True},
        ]})
        with self.assertRaisesRegex(PreflightError, 'another running container'):
            self.check()

    def test_runner_must_be_explicitly_off_once(self):
        for runner in (('HEARTH2_ENABLED=true',), (), ('HEARTH2_ENABLED=false',) * 2):
            with self.subTest(runner=runner), self.assertRaisesRegex(PreflightError, 'runner'):
                self.check(runner=runner)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name)
        with sqlite3.connect(':memory:') as db:
            db.execute('CREATE TABLE example (id INTEGER PRIMARY KEY)')
            self.sqlite_bytes = db.serialize()
        self.write_data()
        self.image = self.write_image()
        (self.path / 'image-id').write_text(self.image + '\n', encoding='ascii')
        (self.path / 'compose.before.json').write_text('{"services":{"hub":{}}}', encoding='ascii')
        self.manifest('runtime.before.sha256', 'compose.before.json', 'image.before.oci.tar')
        health = {'memory': 'ok', 'homeserver': 'ok', 'version': 'fixture', 'build_commit': 'a' * 40,
                  'drawers': 3, 'checkpoints': 2, 'relays': 1}
        (self.path / 'health.before.public.json').write_text(json.dumps(health), encoding='ascii')

    def manifest(self, manifest, *names):
        lines = [f'{sha((self.path / name).read_bytes())}  {name}\n' for name in names]
        (self.path / manifest).write_text(''.join(lines), encoding='ascii')

    def write_data(self, include_memory=True, extra=()):
        members = [('./work.sqlite3', self.sqlite_bytes)]
        if include_memory:
            members.append(('./chroma/chroma.sqlite3', self.sqlite_bytes))
        write_tar(self.path / 'cold-data.tar', members + list(extra))
        self.manifest('cold-data.sha256', 'cold-data.tar')

    def write_image(self, include_layer=True):
        index_type = 'application/vnd.oci.image.index.v1+json'
        manifest_type = 'application/vnd.oci.image.manifest.v1+json'
        members = []

        def blob(media_type, body, include=True):
            digest = sha(body)
            if include:
                members.append(('blobs/sha256/' + digest, body))
            return {'mediaType': media_type, 'digest': 'sha256:' + digest, 'size': len(body)}

        def encoded(value):
            return json.dumps(value).encode()

        config = blob('application/vnd.oci.image.config.v1+json', b'{}')
        layer = blob('application/vnd.oci.image.layer.v1.tar', b'fixture layer', include_layer)
        manifest = blob(manifest_type, encoded({'schemaVersion': 2, 'config': config, 'layers': [layer]}))
        image = blob(index_type, encoded({'schemaVersion': 2, 'manifests': [manifest]}))
        members.append(('index.json', encoded({'schemaVersion': 2, 'manifests': [image]})))
        write_tar(self.path / 'image.before.oci.tar', members)
        return image['digest']

    def test_complete_release_passes(self):
        self.assertEqual(verify_release(self.path, self.image), self.image)

    def test_missing_rollback_image_fails(self):
        (self.path / 'image.before.oci.tar').unlink()
        with self.assertRaisesRegex(PreflightError, 'image.before.oci.tar'):
            verify_release(self.path, self.image)

    def test_missing_data_archive_fails(self):
        (self.path / 'cold-data.tar').unlink()
        with self.assertRaisesRegex(PreflightError, 'cold-data.tar'):
            verify_release(self.path, self.image)

    def test_incomplete_archive_fails_even_with_matching_checksum(self):
        self.write_data(include_memory=False)
        with self.assertRaisesRegex(PreflightError, 'chroma/chroma.sqlite3'):
            verify_release(self.path, self.image)

    def test_checksum_mismatch_fails(self):
        with (self.path / 'cold-data.tar').open('ab') as archive:
            archive.write(b'unexpected data')
        with self.assertRaisesRegex(PreflightError, 'checksum mismatch'):
            verify_release(self.path, self.image)

    def test_wrong_image_digest_fails(self):
        with self.assertRaisesRegex(PreflightError, 'running writer image'):
            verify_release(self.path, 'sha256:' + 'b' * 64)

    def test_oci_missing_blob_fails_even_with_matching_archive_checksum(self):
        self.assertEqual(self.write_image(include_layer=False), self.image)
        self.manifest('runtime.before.sha256', 'compose.before.json', 'image.before.oci.tar')
        with self.assertRaisesRegex(PreflightError, 'missing OCI blob'):
            verify_release(self.path, self.image)

    def test_unsafe_archive_member_fails(self):
        self.write_data(extra=(('../outside', b'bad path'),))
        with self.assertRaisesRegex(PreflightError, 'unsafe cold archive member'):
            verify_release(self.path, self.image)


if __name__ == '__main__':
    unittest.main()
