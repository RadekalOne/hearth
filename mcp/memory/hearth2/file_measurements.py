"""Inactive bounded selected-file archive measurements; never extract an archive.

The source must independently authenticate image/CID and resolve every ancestor
without following links in the original filesystem. No source is installed by
default. This decoder cannot prove archive provenance, image layer resolution,
root runtime identity, credential absence, or Docker CLI compatibility.
"""
from dataclasses import dataclass
import hashlib
import re
import stat
import tarfile
import time

from .creation import _digest
from .root_commands import _container
from .store import RecordError, timestamp


_FILE_MAX = 8*1024*1024
_ARCHIVE_MAX = _FILE_MAX + 16384


@dataclass(frozen=True)
class FileArchive:
    """Source evidence, not caller declarations or an automatically trusted seal.

    read_file_archive(image_id, container_id, path, max_bytes=..., timeout=...)
    must enforce its own I/O limits and return this immutable value. ancestors
    contains root through immediate parent as (absolute path, lstat mode, uid),
    acquired without following any symlink in the same authenticated source.
    The uncompressed single-file USTAR member is exactly the requested basename.
    Unsupported OCI layers, provenance, consumers or resolver semantics must fail.
    """
    image_id: str
    container_id: str | None
    path: str
    ancestors: tuple
    archive: bytes
    observed_at: str
    references: tuple


def _parts(path):
    if (type(path) is not str or len(path) > 4096 or not path.startswith('/')
            or '\x00' in path or '\\' in path or not path.isascii()
            or any(ord(c) < 32 or ord(c) == 127 for c in path)):
        raise RecordError('unsupported exact archive source path')
    parts = path.split('/')[1:]
    if not parts or any(p in {'', '.', '..'} for p in parts) or len(parts[-1].encode()) > 100:
        raise RecordError('canonical non-root file path required')
    return parts


def _octal(field):
    # No GNU base-256, negative, empty, embedded-NUL or alternative numeric form.
    if not re.fullmatch(rb'[0-7]+[\x00 ]*', field):
        raise RecordError('unsupported USTAR numeric encoding')
    return int(field.rstrip(b'\0 '), 8)


def _regular(raw, basename):
    if (type(raw) is not bytes or not 2048 <= len(raw) <= _ARCHIVE_MAX or len(raw) % 512
            or raw[257:263] != b'ustar\0' or raw[263:265] != b'00'):
        raise RecordError('bounded uncompressed USTAR file required')
    header = raw[:512]
    try:
        info = tarfile.TarInfo.frombuf(header, 'ascii', 'strict')
    except (tarfile.HeaderError, UnicodeError, ValueError):
        raise RecordError('invalid USTAR header') from None
    size = _octal(header[124:136])
    uid, gid, mode = _octal(header[108:116]), _octal(header[116:124]), _octal(header[100:108])
    _octal(header[136:148])
    _octal(header[148:156])
    for device in (header[329:337], header[337:345]):
        # POSIX regular files may leave device fields entirely NUL. Otherwise
        # permit only octal zero, never GNU base-256 or a hidden device number.
        if any(device) and _octal(device) != 0:
            raise RecordError('device numeric fields unsupported for a regular file')
    name = basename.encode('ascii')
    if (header[:100] != name.ljust(100, b'\0') or header[156:157] not in {b'0', b'\0'}
            or any(header[157:257]) or any(header[345:]) or info.name != basename
            or info.size != size or info.uid != uid or info.gid != gid or info.mode != mode
            or not 0 < size <= _FILE_MAX or uid != 0 or gid != 0 or mode not in {0o444, 0o555}):
        raise RecordError('only one exact regular root-owned immutable file is supported')
    end = 512 + size
    padded = ((end + 511)//512)*512
    # Exactly one payload, zero block padding, at least two end-of-archive blocks.
    # Reject extra members, hidden data after terminator and truncated payloads.
    if len(raw) < padded + 1024 or any(raw[end:]):
        raise RecordError('archive has extra data or missing terminator')
    return hashlib.sha256(memoryview(raw)[512:end]).hexdigest(), mode, size


class ArchiveFileMeasurements:
    def __init__(self, source=None, *, clock, monotonic=time.monotonic):
        self.source, self.clock, self.monotonic = source, clock, monotonic

    def observe(self, image_id, container_id, path):
        if type(image_id) is not str or not image_id.startswith('sha256:') or not _digest(image_id[7:]):
            raise RecordError('exact immutable image ID required')
        if container_id is not None: _container(container_id)
        parts = _parts(path)
        if self.source is None: raise RecordError('independent authenticated archive source absent')
        begin = self.clock(); started = self.monotonic()
        packet = self.source.read_file_archive(image_id, container_id, path, max_bytes=_ARCHIVE_MAX, timeout=5)
        if (type(packet) is not FileArchive or packet.image_id != image_id or packet.container_id != container_id
                or packet.path != path or type(packet.ancestors) is not tuple
                or type(packet.references) is not tuple or not 1 <= len(packet.references) <= 16
                or any(type(v) is not str or not v.strip() or len(v) > 4096 for v in packet.references)):
            raise RecordError('archive source linkage or provenance missing')
        expected = ['/'] + ['/' + '/'.join(parts[:i]) for i in range(1, len(parts))]
        if len(packet.ancestors) != len(expected): raise RecordError('complete resolved ancestor chain required')
        for item, parent in zip(packet.ancestors, expected):
            if (type(item) is not tuple or len(item) != 3 or item[0] != parent
                    or type(item[1]) is not int or type(item[2]) is not int or item[2] != 0
                    or not 0 <= item[1] <= 0xffff or not stat.S_ISDIR(item[1]) or item[1] & 0o022):
                raise RecordError('source ancestor is unresolved, writable or not an owned directory')
        digest, mode, size = _regular(packet.archive, parts[-1])
        finish = self.clock(); elapsed = self.monotonic() - started
        observed = timestamp(packet.observed_at)
        if not begin <= observed <= finish or not 0 <= (finish-begin).total_seconds() <= 5 or not 0 <= elapsed <= 5:
            raise RecordError('archive measurement stale, future or exceeded time bound')
        reference = 'selected-ustar-sha256:' + hashlib.sha256(packet.archive).hexdigest()
        return {'image_id': image_id, 'container_id': container_id, 'path': path, 'sha256': digest,
                'kind': 'regular', 'uid': 0, 'mode': mode, 'size': size,
                'observed_at': packet.observed_at, 'references': list(packet.references) + [reference]}
