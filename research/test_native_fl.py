#!/usr/bin/env python3
"""Check the native approximation's bounds, identity and neutral behavior offline."""
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.native_fl import Codec, MAX_DELTA, build_table
from research.fl_look import DEFAULT_RECIPE


class NativeFLTests(unittest.TestCase):
    def setUp(self):
        # Synthetic monotonic codec; native machine-code tests separately use
        # the exact original lookup tables and pinned firmware.
        self.codec = Codec(struct.pack('<129H', *(i*4 for i in range(129))) +
                           bytes(min(128, (i+2)//4) for i in range(513)))
        self.recipe = json.loads(DEFAULT_RECIPE.read_text())
        self.original = bytes(1215)+bytes(range(65))

    def test_zero_strength_exact_identity(self):
        self.assertEqual(build_table(self.original, self.codec, self.recipe, 0), self.original)

    def test_bounds_and_tail(self):
        result = build_table(self.original, self.codec, self.recipe)
        self.assertEqual(len(result), 1280)
        self.assertEqual(result[1215:], self.original[1215:])
        self.assertNotEqual(result[:1215], self.original[:1215])
        for plane in range(3):
            values=[x if x<128 else x-256 for x in result[plane*405:(plane+1)*405]]
            self.assertLessEqual(max(abs(x) for x in values), MAX_DELTA[plane])

    def test_neutral_axis_and_luminance_order(self):
        result = build_table(self.original, self.codec, self.recipe)
        y=[]
        for a in range(5):
            i=a*81+40
            self.assertEqual(result[i+405], 0)
            self.assertEqual(result[i+810], 0)
            d=result[i] if result[i]<128 else result[i]-256
            y.append(a*64+d)
        self.assertEqual(y, sorted(y))
        self.assertGreaterEqual(y[0],0); self.assertLessEqual(y[-1],256)

    def test_repeatable(self):
        self.assertEqual(build_table(self.original,self.codec,self.recipe),
                         build_table(self.original,self.codec,self.recipe))

    def test_invalid_inputs(self):
        for strength in (-.1,1.1,float('nan'),float('inf'),True):
            with self.assertRaises(ValueError): build_table(self.original,self.codec,self.recipe,strength)
        for source in (bytes(1279),bytes(1281),bytes([127])*1280):
            with self.assertRaises(ValueError): build_table(source,self.codec,self.recipe)
        with self.assertRaises(ValueError): Codec(bytes(771))
        with self.assertRaises(ValueError): self.codec.expand(.5)


if __name__ == '__main__':
    unittest.main()
