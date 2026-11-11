"""Run in the Linux lab guest via .lab/card_read.py; never accesses camera USB."""
import os
import mmap
import ctypes
import tempfile
import hashlib
import struct

libc = ctypes.CDLL(None, use_errno=True)
libc.mprotect.argtypes = (ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int)
libc.mprotect.restype = ctypes.c_int
page = os.sysconf('SC_PAGE_SIZE')
with tempfile.TemporaryDirectory(prefix='a7fl-cow-') as temp:
    path = temp + '/view-test.bin'
    original = bytes((i * 17 + i // page) % 251 for i in range(page * 6))
    with open(path, 'wb') as f:
        f.write(original)
        f.flush()
        os.fsync(f.fileno())
    fd = os.open(path, os.O_RDWR)
    mem = mmap.mmap(fd, len(original), access=mmap.ACCESS_COPY)
    addr = ctypes.addressof(ctypes.c_char.from_buffer(mem))
    assert addr % page == 0
    assert libc.mprotect(addr, len(original), 5) == 0
    before = mem[:]

    def flags(index):
        with open('/proc/self/pagemap', 'rb', buffering=0) as p:
            p.seek((addr // page + index) * 8)
            entry = struct.unpack('<Q', p.read(8))[0]
        return {'present': (entry >> 63) & 1, 'file_or_shared': (entry >> 61) & 1}

    selected = (1, 3, 5)
    first = [flags(i) for i in selected]
    for i in selected:
        at = addr + i * page
        assert libc.mprotect(at, page, 7) == 0
        byte = ctypes.c_ubyte.from_address(at)
        byte.value = byte.value
        assert libc.mprotect(at, page, 5) == 0
        assert mem[i * page:(i + 1) * page] == original[i * page:(i + 1) * page]
    second = [flags(i) for i in selected]
    assert all(x['present'] == 1 and x['file_or_shared'] == 0 for x in second)
    changed = bytearray(original)
    for i in selected:
        changed[i * page:i * page + 4] = b'NEW!'
        assert os.pwrite(fd, b'NEW!', i * page) == 4
    os.fsync(fd)
    assert mem[:] == original
    assert os.pread(fd, len(original), 0) == changed
    result = {'kernel': os.uname().release, 'page_size': page,
              'pages': list(selected), 'flags_before': first, 'flags_after': second,
              'mapping_unchanged': mem[:] == original,
              'disk_changed': os.pread(fd, len(original), 0) == changed,
              'original_sha256': hashlib.sha256(original).hexdigest(),
              'new_file_sha256': hashlib.sha256(changed).hexdigest()}
    assert libc.mprotect(addr, len(original), 3) == 0
    mem.close()
    os.close(fd)
