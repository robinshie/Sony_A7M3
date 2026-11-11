"""Pinned Sony UXC v7 image resources: LZ77 blocks and Morton 8x8 RGBA4444.

The LZ77 stream semantics are documented by ma1co/fwtool.py (MIT) and Sony's
published kernel lib/lz77/lz77_inflate.c. This bounded implementation and
encoder are independent. Firmware bytes and generated Sony previews stay local.
"""
import struct
from collections import defaultdict, deque

LENGTHS = tuple(range(3, 17)) + (32, 64)


def decode(data):
    out = bytearray()
    pos = 0
    while pos < len(data):
        kind = data[pos]; pos += 1
        block = bytearray()
        if kind == 15:
            if pos + 3 > len(data): raise ValueError('Truncated raw block')
            size = struct.unpack_from('<H', data, pos + 1)[0]; pos += 3
            if not 0 < size <= 4096 or pos + size > len(data): raise ValueError('Invalid raw block')
            block.extend(data[pos:pos + size]); pos += size
        elif kind == 240:
            ended = False
            while not ended:
                if pos >= len(data): raise ValueError('Truncated flags')
                flags = data[pos]; pos += 1
                for bit in range(8):
                    if flags & (1 << bit):
                        if pos + 2 > len(data): raise ValueError('Truncated match')
                        a, b = data[pos:pos + 2]; pos += 2
                        distance = ((a & 15) << 8) | b
                        if not distance: ended = True; break
                        if distance > len(block): raise ValueError('Invalid match distance')
                        for _ in range(LENGTHS[a >> 4]): block.append(block[-distance])
                    else:
                        if pos >= len(data): raise ValueError('Truncated literal')
                        block.append(data[pos]); pos += 1
                    if len(block) > 4096: raise ValueError('Block too large')
        else: raise ValueError('Unknown LZ77 block')
        if not block: raise ValueError('Empty block')
        out.extend(block)
        if len(out) > 16 * 1024 * 1024: raise ValueError('Image too large')
    return bytes(out)


def encode(data):
    encoded = bytearray()
    for begin in range(0, len(data), 4096):
        block = data[begin:begin + 4096]; table = defaultdict(deque)
        tokens = []; at = 0
        while at < len(block):
            best = 0; distance = 0
            key = block[at:at + 3]
            candidates = table[key]
            while candidates and at - candidates[0] > 4095: candidates.popleft()
            for previous in reversed(candidates):
                size = 0
                while size < min(64, len(block) - at) and block[previous + size] == block[at + size]: size += 1
                size = max((x for x in LENGTHS if x <= size), default=0)
                if size > best: best, distance = size, at - previous
                if best == 64: break
            if best:
                tokens.append((1, bytes([(LENGTHS.index(best) << 4) | (distance >> 8), distance & 255])))
            else:
                best = 1; tokens.append((0, block[at:at + 1]))
            for offset in range(at, at + best): table[block[offset:offset + 3]].append(offset)
            at += best
        tokens.append((1, b'\0\0'))
        packed = bytearray([240])
        for start in range(0, len(tokens), 8):
            group = tokens[start:start + 8]
            packed.append(sum(flag << i for i, (flag, _) in enumerate(group)))
            packed.extend(b''.join(value for _, value in group))
        raw = b'\x0f\0' + struct.pack('<H', len(block)) + block
        encoded.extend(packed if len(packed) < len(raw) else raw)
    result = bytes(encoded)
    if decode(result) != data: raise ValueError('Encoder round trip failed')
    return result


class Images:
    def __init__(self, data):
        self.data = bytes(data)
        if data[:12] != bytes.fromhex('757864070000000008002e00'): raise ValueError('Wrong image UXC header')
        packed = struct.unpack_from('<I', data, 12)[0]
        self.count = packed & 8191; self.start = 16 + 4 * (packed >> 13)
        if self.start != (16 + self.count * 2 + 3) & ~3: raise ValueError('Expected fixed short index')
        self.records = {}
        for index in range(self.count):
            value = struct.unpack_from('<H', data, 16 + index * 2)[0]
            if value == 65535: continue
            at = self.start + value * 4
            tag, flags, w, h, size, offset = struct.unpack_from('<IIHHII', data, at)
            key = 0x5c000 + index
            if tag != 0x1a000000 | key: raise ValueError('Bad image record')
            # Nine-patch records have a separate layout, preserved byte-for-byte.
            if flags & 0x08000000: continue
            begin = at + 4 + offset
            if not 0 < w <= 4096 or not 0 < h <= 4096 or begin + size > len(data): raise ValueError('Bad image span')
            self.records[key] = (at, flags, w, h, begin, size)

    def pixels(self, key):
        at, flags, w, h, begin, size = self.records[key]
        raw = decode(self.data[begin:begin + size])
        stride = (w + 7) // 8
        if len(raw) != stride * 8 * ((h + 7) // 8 * 8) * 2: raise ValueError('Unexpected pixel format')
        values = struct.unpack('<' + 'H' * (len(raw) // 2), raw)
        return w, h, [values[((y // 8) * stride + x // 8) * 64 + morton(x, y)] for y in range(h) for x in range(w)]


def morton(x, y):
    return sum((((x >> bit) & 1) << (2 * bit)) | (((y >> bit) & 1) << (2 * bit + 1)) for bit in range(3))


def swizzle(w, h, pixels):
    stride = (w + 7) // 8
    values = [0] * (stride * 8 * ((h + 7) // 8 * 8))
    for y in range(h):
        for x in range(w): values[((y // 8) * stride + x // 8) * 64 + morton(x, y)] = pixels[y * w + x]
    return struct.pack('<' + 'H' * len(values), *values)


# Original geometric 5x7 letters; no proprietary fonts or artwork.
LETTERS = {
    'R': (30,17,17,30,20,18,17), 'W': (17,17,17,21,21,21,10),
    'F': (31,16,16,30,16,16,16), 'L': (16,16,16,16,16,16,31),
}

def badge(text, w, h, orange=False):
    pixels = [0] * (w * h)
    color = 0xf60f if orange else 0xdddf
    scale = 4 if w > 100 else 2
    left = (w - 11 * scale) // 2; top = (h - 7 * scale) // 2
    def rect(x, y, width, height):
        for yy in range(y, y + height):
            for xx in range(x, x + width):
                if 0 <= xx < w and 0 <= yy < h: pixels[yy * w + xx] = color
    for i, ch in enumerate(text):
        for y, row in enumerate(LETTERS[ch]):
            for x in range(5):
                if row & (1 << (4-x)): rect(left+(i*6+x)*scale, top+y*scale, scale, scale)
    border = 2 if w > 100 else 1
    x, y = left - scale * 2, top - scale
    width, height = 15 * scale, 9 * scale
    rect(x,y,width,border);rect(x,y+height-border,width,border)
    rect(x,y,border,height);rect(x+width-border,y,border,height)
    return pixels


def patch(data):
    """Reuse slack created by lossless recompression; keep file size unchanged.

    Resource 5c000 keeps exactly the same pixels. Its shorter stream frees
    40 bytes for two short-index records. The much smaller RW Fn badge frees
    enough space in its own old stream span for the large and small badges.
    No unrelated image bytes, resource IDs or filesystem blocks are reused.
    """
    old = Images(data); result = bytearray(data)
    donor = old.records[0x5c000]; at, flags, w, h, begin, size = donor
    if (at, begin, size) != (0x3408, 0x21e44, 783): raise ValueError('Unexpected donor record')
    compressed = encode(decode(data[begin:begin+size]))
    if len(compressed) + 40 > size: raise ValueError('No metadata space after lossless recompression')
    relocated = begin + 40
    result[relocated:relocated+len(compressed)] = compressed
    struct.pack_into('<II', result, at + 12, len(compressed), relocated - at - 4)
    fn_at, flags, fw, fh, space, available = old.records[0x5c76d]
    if (fw,fh,available)!=(70,35,1801): raise ValueError('Wrong Fn badge baseline')
    cursor = space
    def allocate(blob):
        nonlocal cursor
        cursor = (cursor + 3) & ~3
        pos = cursor; cursor += len(blob)
        if cursor > space + available: raise ValueError('Icons exceed reserved stream span')
        result[pos:cursor] = blob
        return pos
    blob=encode(swizzle(70,35,badge('RW',70,35)))
    if allocate(blob)!=space:raise ValueError('Unexpected Fn alignment')
    struct.pack_into('<I',result,fn_at+12,len(blob))
    definitions=[(0x5c049,116,100),(0x5c04a,70,60)]
    for i, (key,width,height) in enumerate(definitions):
        index=16+2*(key-0x5c000)
        if data[index:index+2]!=b'\xff\xff': raise ValueError('Image ID already assigned')
        record=begin+i*20
        blob=encode(swizzle(width,height,badge('RW',width,height,width>100)))
        pos=allocate(blob)
        struct.pack_into('<IIHHII',result,record,0x1a000000|key,0xe0000000,width,height,len(blob),pos-record-4)
        struct.pack_into('<H',result,index,(record-old.start)//4)
    new=Images(result)
    for key,entry in old.records.items():
        if key in (0x5c76d,0x5c000):continue
        n=new.records[key]
        if entry!=n or data[entry[4]:entry[4]+entry[5]]!=result[n[4]:n[4]+n[5]]:
            raise ValueError(f'Unrelated image changed: {key:x}')
    if new.pixels(0x5c000)!=old.pixels(0x5c000):raise ValueError('Relocated donor pixels changed')
    for key,width,height in definitions+[(0x5c76d,70,35)]:
        if new.pixels(key)!=(width,height,badge('RW',width,height,width>100)):
            raise ValueError('New badge failed pixel verification')
    if len(result)!=len(data):raise ValueError('Image file size changed')
    return bytes(result)
