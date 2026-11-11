"""AV-CAM 4.04 LUT storage, not an RGB .cube converter or camera payload.

The three coordinates and components deliberately have no color-space names:
their device encoding and position in the image pipeline are still unproven.
"""
import struct

SHAPE = (5, 9, 9)
NODES = 405
BANK_COUNTS = (75, 60, 60, 48, 50, 40, 40, 32)
BANK_REGISTERS = (0x17000, 0x17200, 0x17300, 0x17400,
                  0x17500, 0x17600, 0x17700, 0x17800)


def packed_index(a, b, c):
    """Parity-bank layout, independently compared to the firmware permutation."""
    if not all(type(v) is int and 0 <= v < n for v, n in zip((a, b, c), SHAPE)):
        raise ValueError('Coordinates must be integers inside 5 x 9 x 9')
    bank = ((a & 1) << 2) | ((b & 1) << 1) | (c & 1)
    nb, nc = 5 - (b & 1), 5 - (c & 1)
    return sum(BANK_COUNTS[:bank]) + (a // 2 * nb + b // 2) * nc + c // 2


def pack(components):
    """Pack three signed correction planes into 405 little-endian u32 words.

    Each plane has logical index a*81+b*9+c. Reject values that would silently
    wrap in the native seven-bit mask. This does not establish units or gamut.
    """
    if len(components) != 3 or any(len(p) != NODES for p in components):
        raise ValueError('Expected three planes of 405 signed integers')
    if any(type(x) is not int or not -64 <= x <= 63 for p in components for x in p):
        raise ValueError('Correction codes must be integers in [-64, 63]')
    words = [0] * NODES
    for a in range(5):
        for b in range(9):
            for c in range(9):
                i = a * 81 + b * 9 + c
                words[packed_index(a, b, c)] = sum(
                    (components[p][i] & 127) << (16 - p * 8) for p in range(3))
    return struct.pack('<405I', *words)


def unpack(data):
    """Inverse of pack; reject reserved bits rather than silently discard them."""
    if len(data) != NODES * 4:
        raise ValueError('Packed LUT must contain exactly 1620 bytes')
    words = struct.unpack('<405I', data)
    if any(w & 0xff808080 for w in words):
        raise ValueError('Reserved bits are set')
    planes = [[0] * NODES for _ in range(3)]
    for a in range(5):
        for b in range(9):
            for c in range(9):
                w = words[packed_index(a, b, c)]
                for p in range(3):
                    x = (w >> (16 - p * 8)) & 127
                    planes[p][a * 81 + b * 9 + c] = x - 128 if x & 64 else x
    return planes
