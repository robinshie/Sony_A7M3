"""Read local ARM ELF32 symbols, load segments and dynamic relocations."""
import struct
from pathlib import Path


class ELF:
    def __init__(self, path):
        self.data = Path(path).read_bytes()
        h = struct.unpack_from('<16sHHIIIIIHHHHHH', self.data)
        if h[0][:6] != b'\x7fELF\x01\x01' or h[2] != 40:
            raise ValueError('Expected little-endian ARM ELF32')
        self.segments = [struct.unpack_from('<8I', self.data, h[5] + i*h[9])
                         for i in range(h[10])]
        self.sections = [struct.unpack_from('<10I', self.data, h[6] + i*h[11])
                         for i in range(h[12])]
        self.symbols = {}
        self.relocations = {}
        tables = {}
        for index, s in enumerate(self.sections):
            if s[1] != 11:
                continue
            strings = self.section(s[6])
            entries = []
            for off in range(s[4], s[4]+s[5], s[9]):
                name, value, size, info, other, section = struct.unpack_from('<IIIBBH', self.data, off)
                name = strings[name:strings.index(b'\0', name)].decode('ascii')
                symbol = dict(name=name, value=value, size=size, section=section)
                entries.append(symbol)
                if name and section:
                    self.symbols[name] = symbol
            tables[index] = entries
        for s in self.sections:
            if s[1] != 9 or s[6] not in tables:
                continue
            for off in range(s[4], s[4]+s[5], s[9]):
                address, info = struct.unpack_from('<II', self.data, off)
                self.relocations[address] = (info & 255, tables[s[6]][info >> 8])

    def section(self, index):
        s = self.sections[index]
        return self.data[s[4]:s[4]+s[5]]

    def read(self, address, length):
        for kind, offset, va, _, size, _, _, _ in self.segments:
            if kind == 1 and va <= address and address+length <= va+size:
                at = offset + address - va
                return self.data[at:at+length]
        raise ValueError(f'Address {address:#x}+{length} is not file-backed')

    def word(self, address):
        return struct.unpack('<I', self.read(address, 4))[0]

    def target_name(self, address):
        return self.relocations[address][1]['name']
