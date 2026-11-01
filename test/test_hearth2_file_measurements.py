"""Private USTAR fixtures only; no daemon, image extraction or native worker."""
from dataclasses import replace
from datetime import datetime, timezone, timedelta
import hashlib
import importlib.util
import io
import stat
import tarfile
import unittest

from hearth2.store import RecordError


class FileMeasurementTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('hearth2.file_measurements'), 'archive reader missing')
        from hearth2 import file_measurements
        self.module = file_measurements
        self.now = datetime(2026, 11, 1, 22, 0, tzinfo=timezone.utc)
        self.image = 'sha256:' + 'a'*64
        self.cid = 'b'*64
        self.path = '/opt/hearth2/bootstrap'
        self.payload = b'PRIVATE BOOTSTRAP NEVER EXECUTED\n'
        self.requests = []
        self.reply = self.packet()
        test = self
        class Source:
            def read_file_archive(_, image, container, path, *, max_bytes, timeout):
                test.requests.append((image, container, path, max_bytes, timeout))
                return test.reply
        self.source = Source()
        self.reader = self.module.ArchiveFileMeasurements(self.source, clock=lambda: self.now)

    def archive(self, *, name='bootstrap', kind=tarfile.REGTYPE, mode=0o555, uid=0, extra=False, fmt=tarfile.USTAR_FORMAT):
        out = io.BytesIO()
        with tarfile.open(fileobj=out, mode='w', format=fmt) as package:
            item = tarfile.TarInfo(name)
            item.type, item.mode, item.uid, item.gid = kind, mode, uid, 0
            item.size = len(self.payload) if kind == tarfile.REGTYPE else 0
            if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE): item.linkname = '/outside'
            package.addfile(item, io.BytesIO(self.payload) if item.size else None)
            if extra: package.addfile(tarfile.TarInfo('another'))
        return out.getvalue()

    def packet(self, **changes):
        return self.module.FileArchive(self.image, None, self.path,
            (('/', stat.S_IFDIR | 0o555, 0), ('/opt', stat.S_IFDIR | 0o555, 0),
             ('/opt/hearth2', stat.S_IFDIR | 0o555, 0)),
            self.archive(), self.now.isoformat(), ('private:archive-acquisition',), **changes)

    def read(self, cid=None):
        return self.reader.observe(self.image, cid, self.path)

    def test_hashes_payload_without_extraction_and_preserves_source_linkage(self):
        fact = self.read()
        self.assertEqual({k: fact[k] for k in ['image_id','container_id','path','kind','uid','mode','size','sha256']},
            dict(image_id=self.image, container_id=None, path=self.path, kind='regular', uid=0,
                 mode=0o555, size=len(self.payload), sha256=hashlib.sha256(self.payload).hexdigest()))
        self.assertIn('private:archive-acquisition', fact['references'])
        self.assertEqual(self.requests[0][:3], (self.image, None, self.path))
        self.assertLessEqual(self.requests[0][3], 8*1024*1024 + 16384)
        self.assertEqual(self.requests[0][4], 5)

    def test_container_request_requires_source_to_bind_exact_cid(self):
        with self.assertRaises(RecordError): self.read(self.cid)
        self.reply = replace(self.reply, container_id=self.cid)
        self.assertEqual(self.read(self.cid)['container_id'], self.cid)

    def test_missing_source_never_measures_or_returns_empty_success(self):
        reader = self.module.ArchiveFileMeasurements(clock=lambda: self.now)
        with self.assertRaises(RecordError): reader.observe(self.image, None, self.path)

    def test_wrong_image_path_or_member_is_refused(self):
        original = self.reply
        for changes in [dict(image_id='sha256:'+'c'*64), dict(path='/another/bootstrap'),
                        dict(archive=self.archive(name='different'))]:
            with self.subTest(changes=list(changes)):
                self.reply = replace(original, **changes)
                with self.assertRaises(RecordError): self.read()

    def test_rejects_all_nonregular_types_and_pax_gnu_extensions(self):
        for kind in [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.DIRTYPE, tarfile.FIFOTYPE,
                     tarfile.CHRTYPE, tarfile.BLKTYPE, tarfile.XHDTYPE, tarfile.GNUTYPE_SPARSE]:
            with self.subTest(kind=kind):
                self.reply = replace(self.reply, archive=self.archive(kind=kind))
                with self.assertRaises(RecordError): self.read()
        for fmt in [tarfile.GNU_FORMAT, tarfile.PAX_FORMAT]:
            self.reply = replace(self.reply, archive=self.archive(name='x'*101, fmt=fmt))
            with self.assertRaises(RecordError): self.read()

    def test_rejects_path_traversal_absolute_member_and_second_entry(self):
        for name in ['../bootstrap', '/bootstrap', 'dir/bootstrap', './bootstrap']:
            self.reply = replace(self.reply, archive=self.archive(name=name))
            with self.assertRaises(RecordError): self.read()
        self.reply = replace(self.reply, archive=self.archive(extra=True))
        with self.assertRaises(RecordError): self.read()

    def test_requires_full_ordered_nonwritable_root_owned_nofollow_ancestor_chain(self):
        original = self.reply
        for chain in [(), original.ancestors[1:], tuple(reversed(original.ancestors)),
                      (('/', stat.S_IFDIR|0o555, 0), ('/opt', stat.S_IFLNK|0o555, 0), original.ancestors[2]),
                      (original.ancestors[0], ('/opt', stat.S_IFDIR|0o777, 0), original.ancestors[2]),
                      (original.ancestors[0], ('/opt', stat.S_IFDIR|0o555, 1000), original.ancestors[2])]:
            self.reply = replace(original, ancestors=chain)
            with self.assertRaises(RecordError): self.read()

    def test_rejects_corrupt_header_payload_padding_and_trailing_data(self):
        raw = self.archive()
        for broken in [raw[:100], raw[:512], raw[:1024], raw+b'x',
                       raw[:100]+bytes([raw[100]^1])+raw[101:],
                       raw[:512+len(self.payload)]+b'x'+raw[513+len(self.payload):],
                       raw[:1024]+b'x'+raw[1025:]]:
            with self.subTest(size=len(broken)):
                self.reply = replace(self.reply, archive=broken)
                with self.assertRaises(RecordError): self.read()

    def test_rejects_oversize_empty_compressed_and_malformed_requests(self):
        self.reply = replace(self.reply, archive=b'x'*(8*1024*1024+16385))
        with self.assertRaises(RecordError): self.read()
        for path in ['/', '/opt/../bootstrap', '/opt//bootstrap', '/opt/bootstrap/', '/opt/./bootstrap']:
            with self.assertRaises(RecordError): self.reader.observe(self.image, None, path)
        with self.assertRaises(RecordError): self.reader.observe('latest', None, self.path)
        with self.assertRaises(RecordError): self.reader.observe(self.image, 'name', self.path)

    def test_observation_time_must_be_fresh_and_acquired_in_this_call(self):
        for delta in [-1, 1]:
            self.reply = replace(self.reply, observed_at=(self.now+timedelta(seconds=delta)).isoformat())
            with self.assertRaises(RecordError): self.read()

    def test_no_content_or_archive_is_returned_in_measurement(self):
        fact = self.read()
        self.assertNotIn('archive', fact)
        self.assertNotIn(self.payload.decode(), str(fact))
        self.assertEqual(set(fact), {'image_id','container_id','path','sha256','kind','uid','mode','size','observed_at','references'})

    def test_file_size_and_mode_boundaries(self):
        self.payload = b'\0'*(8*1024*1024)
        self.reply = replace(self.reply, archive=self.archive())
        self.assertEqual(self.read()['size'], 8*1024*1024)
        self.payload += b'x'
        self.reply = replace(self.reply, archive=self.archive())
        with self.assertRaises(RecordError): self.read()
        self.payload = b''
        self.reply = replace(self.reply, archive=self.archive())
        with self.assertRaises(RecordError): self.read()
        self.payload = b'profile'
        self.reply = replace(self.reply, archive=self.archive(mode=0o444))
        self.assertEqual(self.read()['mode'], 0o444)
        for changes in [dict(mode=0o777), dict(mode=0o4555), dict(uid=1000)]:
            self.reply = replace(self.reply, archive=self.archive(**changes))
            with self.assertRaises(RecordError): self.read()

    def test_timeout_and_monotonic_rollback_never_return_measurement(self):
        for values in [(10,16), (10,9)]:
            times = iter(values)
            reader = self.module.ArchiveFileMeasurements(self.source, clock=lambda:self.now, monotonic=lambda:next(times))
            with self.assertRaises(RecordError): reader.observe(self.image, None, self.path)

    def test_unknown_source_format_or_mutable_evidence_is_refused(self):
        original = self.reply
        for changes in [dict(ancestors=list(original.ancestors)), dict(references=[]),
                        dict(archive=bytearray(original.archive)), dict(references=('',)),
                        dict(ancestors=(('/', -45056, 0), *original.ancestors[1:]))]:
            self.reply = replace(original, **changes)
            with self.assertRaises(RecordError): self.read()
        self.reply = dict(image_id=self.image)
        with self.assertRaises(RecordError): self.read()

    def test_base256_size_and_prefix_or_linkname_hidden_fields_are_rejected(self):
        raw = self.archive()
        for offset, value in [(124,b'\x80'), (345,b'x'), (157,b'x')]:
            header = bytearray(raw[:512]); header[offset:offset+len(value)] = value
            header[148:156] = b' '*8
            header[148:156] = ('%06o\0 ' % sum(header)).encode()
            self.reply = replace(self.reply, archive=bytes(header)+raw[512:])
            with self.assertRaises(RecordError): self.read()

    def test_non_octal_checksum_and_device_fields_are_refused_even_with_valid_checksum(self):
        raw = self.archive()
        for offset, field in [(148, b'checksum'), (329, b'\x80'+b'\0'*7),
                              (337, b'\xff'*8), (329, b'0000001\0')]:
            header = bytearray(raw[:512])
            if offset != 148: header[offset:offset+8] = field
            header[148:156] = b' '*8
            checksum = sum(header)
            header[148:156] = (b'\x80'+checksum.to_bytes(7, 'big') if offset == 148
                               else ('%06o\0 ' % checksum).encode())
            self.reply = replace(self.reply, archive=bytes(header)+raw[512:])
            with self.subTest(offset=offset, field=field):
                with self.assertRaises(RecordError): self.read()


if __name__ == '__main__': unittest.main()
