"""Read all 300 MiB from the live camera, with per-chunk camera-side CRCs."""
import hashlib
import os
import struct
import zlib

from local import BACKUP
from qemu_test import payload as tested_payload

CHUNK = 4 * 1024 * 1024
COUNT = 75
TAG = 0x41375342
MISSING = (0, 0x10000006)


class Sink(bytearray):
    def write(self, data):
        if len(self) + len(data) > CHUNK + 16:
            raise OSError('Factory reply exceeded the expected chunk size.')
        self.extend(data)


def backup_partition(camera):
    payload = tested_payload("backup")

    def call(code, extra=b''):
        sink = Sink()
        response, _ = camera.dev.sendSenserPacket(0x40, struct.pack('<HH', 0x1001, code) + extra, sink)
        status = struct.unpack_from('<I', sink)[0] if len(sink) >= 4 else None
        return (response, status), sink[4:]

    def check(code, extra=b''):
        result, data = call(code, extra)
        if result != (0, 0):
            raise OSError(f'Factory request {code:#x} returned {result!r}.')
        return data

    def read(name):
        return call(0x4008, b'\x01\0\0/../tmp/jiritsu/' + name.encode('ascii') + b'\0')

    def select(name):
        check(0x000f, b'\0' + name.encode('ascii') + b'\0')

    def put(name, contents):
        select(name)
        check(0x0010, b'\0\xff\0' + contents)

    def run():
        if read('libJit.so')[0] != MISSING:
            raise OSError('Factory staging name already exists.')
        put('libJit.so', payload)
        if read('libJit.so')[0] != MISSING:
            raise OSError('Probe did not clean up its temporary binary.')

    def cleanup():
        state, data = read('a7ram/tag.bin')
        if state == (0, 0) and data == struct.pack('<I', TAG):
            if read('a7ram/req.bin')[0] == (0, 0):
                select('a7ram/req.bin')
                check(0x0012, b'\0\xff')
            put('a7ram/req.bin', b'\xff' * 4)
            run()
        if any(read(name)[0] != MISSING for name in ('libJit.so', 'a7ram/tag.bin', 'a7ram/data.bin', 'a7ram/req.bin')):
            raise OSError('Could not verify cleanup of factory temporary files.')
        print('BACKUP_SCRATCH_CLEANUP_CONFIRMED', flush=True)

    destination = BACKUP
    partial = destination.with_suffix('.partial')
    if destination.exists() or partial.exists():
        raise OSError('A previous local partition capture already exists.')
    check(0x4002, b'\0\0')
    if any(read(name)[0] != MISSING for name in ('libJit.so', 'a7ram/tag.bin', 'a7ram/data.bin', 'a7ram/req.bin')):
        raise OSError('Factory staging names are in use.')

    digest = hashlib.sha256()
    try:
        run()
        state, token = read('a7ram/tag.bin')
        if state != (0, 0) or token != struct.pack('<I', TAG):
            raise OSError('Probe could not set up the temporary RAM filesystem.')
        print('BACKUP_SCRATCH_TMPFS_READY', flush=True)
        fd = os.open(partial, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            for index in range(COUNT):
                if read('a7ram/req.bin')[0] != MISSING:
                    raise OSError('The previous request was not consumed.')
                put('a7ram/req.bin', struct.pack('<I', index))
                run()
                state, blob = read('a7ram/data.bin')
                if state != (0, 0) or len(blob) != CHUNK + 12:
                    raise OSError(f'Chunk {index}: received {state!r}, {len(blob)} bytes.')
                tag, reply_index, crc = struct.unpack_from('<III', blob)
                data = memoryview(blob)[12:]
                if tag != TAG or reply_index != index or zlib.crc32(data) != crc:
                    raise OSError(f'Chunk {index}: camera checksum or index mismatch.')
                if index == 0 and data[1080:1082] != b'\x53\xef':
                    raise OSError('The readback does not begin with the expected ext2 image.')
                stream.write(data)
                digest.update(data)
                if index == 0 or (index + 1) % 8 == 0 or index == COUNT - 1:
                    print(f'CAMERA_USR_BACKUP {(index + 1) * 4}/300 MiB verified', flush=True)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        cleanup()

    if partial.stat().st_size != CHUNK * COUNT:
        raise OSError('The backup size does not match the complete partition.')
    partial.rename(destination)
    print(f'CAMERA_USR_BACKUP_COMPLETE {CHUNK * COUNT} bytes SHA-256 {digest.hexdigest()}', flush=True)
