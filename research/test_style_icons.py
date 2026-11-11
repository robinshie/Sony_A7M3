"""Synthetic codec/tiling boundary tests; no firmware required."""
import random
import struct
import unittest

from style_icons import decode, encode, morton, swizzle


class ImageCodecTests(unittest.TestCase):
    def test_block_boundaries_and_incompressible_data(self):
        rng = random.Random(404)
        for size in (0, 1, 2, 3, 7, 8, 63, 64, 4095, 4096, 4097, 8200):
            for data in (bytes(size), (b'RW123' * ((size + 4) // 5))[:size],
                         bytes(rng.randrange(256) for _ in range(size))):
                with self.subTest(size=size, head=data[:8]):
                    self.assertEqual(decode(encode(data)), data)

    def test_overlapping_backreference_and_multiple_blocks(self):
        # Literal A, distance=1/length=3, terminator. Four As, not two.
        compressed = b'\xf0\x06A\x00\x01\x00\x00'
        self.assertEqual(decode(compressed), b'AAAA')
        self.assertEqual(decode(compressed + b'\x0f\0\x01\0Z'), b'AAAAZ')

    def test_bad_input(self):
        for data in (b'\xff', b'\x0f', b'\x0f\0\0\0', b'\x0f\0\x01\0',
                     b'\x0f\0\x01\x10', b'\xf0', b'\xf0\0', b'\xf0\x01\0',
                     b'\xf0\x01\0\x01', b'\xf0\x01\0\0'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                decode(data)
        # Oversized compressed block: 4097 literals.
        data = b'\xf0' + (b'\0' + b'A' * 8) * 512 + b'\0A'
        with self.assertRaises(ValueError):
            decode(data)

    def test_morton_tile_bijection_and_padded_edges(self):
        self.assertEqual({morton(x, y) for y in range(8) for x in range(8)}, set(range(64)))
        self.assertEqual([morton(x, y) for x, y in [(0,0),(1,0),(0,1),(1,1),(2,0),(0,2)]],
                         [0,1,2,3,4,8])
        raw = swizzle(9, 9, list(range(1, 82)))
        values = struct.unpack('<256H', raw)
        self.assertEqual((values[0], values[64], values[128], values[192]), (1,9,73,81))
        self.assertEqual(sum(v != 0 for v in values), 81)


if __name__ == '__main__':
    unittest.main()
