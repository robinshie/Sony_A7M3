"""Read the pinned UXC v7 string index and populate an unassigned record ID.

Preserves every assigned resource, all original offsets and the index size.
The caller must verify both its source file and the desired empty slot.
"""
import struct

RESOURCE = 0x4ed84


class Strings:
    def __init__(self, data):
        self.data = bytes(data)
        if data[:12] != bytes.fromhex('75786307000000000f002700'):
            raise ValueError('Unexpected UXC string header')
        packed, self.short_count = struct.unpack_from('<II', data, 12)
        self.count = packed & 8191
        self.start = 20 + (packed >> 13) * 4
        if not 20 < self.start <= len(data) or len(data) % 4:
            raise ValueError('Invalid UXC dimensions')
        self.entries = []
        pos = 20
        for index in range(self.count):
            begin = pos
            value = struct.unpack_from('<H', data, pos)[0]
            pos += 2
            if value & 0x8000:
                value = ((value & 0x7fff) << 16) | struct.unpack_from('<H', data, pos)[0]
                pos += 2
            if (index < self.short_count) != (pos - begin == 2):
                raise ValueError('Unexpected index width')
            resource = 0x4e000 + index
            offset = None if value == 0x7fff0000 else self.start + value * 4
            if offset is not None:
                if offset + 5 > len(data) or data[offset:offset+4] != resource.to_bytes(3, 'little') + b'\x1e':
                    raise ValueError(f'Invalid record {resource:#x}')
                end = data.index(0, offset + 4)
                data[offset+4:end].decode('utf-8')
            self.entries.append((begin, pos-begin, offset))
        if (pos+3)&~3 != self.start:
            raise ValueError('Unexpected index end')

    def text(self, resource):
        offset = self.entries[resource - 0x4e000][2]
        if offset is None:
            return None
        return self.data[offset+4:self.data.index(0, offset+4)].decode('utf-8')

    def add(self, text, resource=RESOURCE):
        begin, width, offset = self.entries[resource - 0x4e000]
        if offset is not None or width != 4 or '\0' in text:
            raise ValueError('Expected an unassigned long-index slot')
        result = bytearray(self.data)
        word_offset = (len(result) - self.start) // 4
        if word_offset >= 0x7fff0000:
            raise ValueError('Record offset out of range')
        struct.pack_into('<HH', result, begin, 0x8000 | (word_offset >> 16), word_offset & 65535)
        result.extend(resource.to_bytes(3, 'little') + b'\x1e' + text.encode() + b'\0')
        result.extend(b'\0' * (-len(result) % 4))
        parsed = Strings(result)
        for index in range(self.count):
            key = 0x4e000 + index
            if parsed.text(key) != (text if key == resource else self.text(key)):
                raise ValueError('Existing resource changed')
        return bytes(result)
