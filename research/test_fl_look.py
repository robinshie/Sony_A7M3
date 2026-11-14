"""Determinism, gamut, cube ordering, interpolation, native table and image I/O."""
import copy
import json
from pathlib import Path
import random
import struct
import tempfile
import unittest

from fl_look import (DEFAULT_RECIPE, build, cube_table, decode, encode, interpolate,
                     native_tone, preview, transform, validate)


class LookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.recipe = validate(json.loads(DEFAULT_RECIPE.read_text()))
        cls.table = cube_table(cls.recipe, 33)

    def test_srgb_roundtrip_and_neutral_ramp(self):
        last = -1
        for i in range(4097):
            x = i / 4096
            self.assertAlmostEqual(encode(decode(x)), x, places=12)
            rgb = transform((x, x, x), self.recipe)
            self.assertLess(max(rgb)-min(rgb), 1e-12)
            self.assertGreaterEqual(rgb[0], last)
            last = rgb[0]

    def test_disabled_is_exact(self):
        recipe = dict(self.recipe, strength=0)
        rng = random.Random(20261111)
        for _ in range(1000):
            rgb = tuple(rng.random() for _ in range(3))
            self.assertEqual(transform(rgb, recipe), rgb)
        self.assertEqual(struct.unpack('<1025H', native_tone(recipe)),
                         tuple(min(i*64, 65535) for i in range(1025)))

    def test_invalid_recipes_and_input_rejected(self):
        for key, bad in [('strength', float('nan')), ('strength', 2),
                         ('input_space', 'S-Log3'), ('saturation', -1),
                         ('tone_curve', [[0, 1], [1, 0]]),
                         ('linear_matrix', [[1, 0, 0]]*2),
                         ('split_tone', [[0, 0]]*4), ('split_tone', [[0, .3]]*5)]:
            recipe = copy.deepcopy(self.recipe); recipe[key] = bad
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate(recipe)
        for rgb in [(0, 1), (-1, 0, 0), (1, float('nan'), 0)]:
            with self.assertRaises(ValueError):
                transform(rgb, self.recipe)

    def test_cube_order_and_boundaries(self):
        table = cube_table(dict(self.recipe, strength=0), 2)
        self.assertEqual(table, [(0,0,0), (1,0,0), (0,1,0), (1,1,0),
                                (0,0,1), (1,0,1), (0,1,1), (1,1,1)])
        for corner in table:
            self.assertEqual(interpolate(corner, table, 2), corner)
        rgb = (.13, .57, .91)
        for a,b in zip(interpolate(rgb, table, 2), rgb):
            self.assertAlmostEqual(a, b)

    def test_gamut_and_cube_approximation(self):
        rng = random.Random(20261111)
        errors = []
        for _ in range(6000):
            rgb = tuple(rng.random() for _ in range(3))
            direct = transform(rgb, self.recipe)
            self.assertTrue(all(0 <= v <= 1 for v in direct))
            approx = interpolate(rgb, self.table, 33)
            errors.extend(abs(a-b) for a,b in zip(direct, approx))
        peak = max(errors); rms = (sum(e*e for e in errors)/len(errors))**.5
        print(f'33-cube / direct: peak={peak:.8f}, RMS={rms:.8f} (normalized sRGB)')
        self.assertLess(peak, .025)
        self.assertLess(rms, .002)

    def test_native_tone_is_monotone_u16(self):
        raw = native_tone(self.recipe)
        self.assertEqual(len(raw), 2050)
        values = struct.unpack('<1025H', raw)
        self.assertEqual(values[0], round(.012*65535))
        self.assertEqual(values[-1], round(.985*65535))
        self.assertTrue(all(a <= b for a,b in zip(values, values[1:])))

    def test_cinema_print_has_cool_shadows_and_warm_highlights(self):
        path = DEFAULT_RECIPE.with_name('cinema-print-srgb.json')
        recipe = validate(json.loads(path.read_text()))
        shadow = transform((.12,) * 3, recipe)
        highlight = transform((.85,) * 3, recipe)
        self.assertGreater(shadow[2] - shadow[0], .05)
        self.assertGreater(highlight[0] - highlight[2], .05)
        self.assertGreater(sum(transform((0,) * 3, recipe)) / 3, .04)
        self.assertLess(sum(transform((1,) * 3, recipe)) / 3, .95)
        ramp = [transform((i / 256,) * 3, recipe) for i in range(257)]
        self.assertTrue(all(all(x <= y for x, y in zip(a, b)) for a, b in zip(ramp, ramp[1:])))

    def test_fl2_reference_lifts_mids_and_subdues_blue_without_tinting_gray(self):
        recipe = validate(json.loads(DEFAULT_RECIPE.with_name('fl2-reference-srgb.json').read_text()))
        gray = transform((.5,) * 3, recipe)
        self.assertGreater(min(gray), .58)
        self.assertLess(max(gray) - min(gray), .025)
        blue = transform((.22, .53, .84), recipe)
        self.assertLess(max(blue) - min(blue), .40)
        ramp = [transform((i / 256,) * 3, recipe) for i in range(257)]
        self.assertTrue(all(all(x <= y for x, y in zip(a, b)) for a, b in zip(ramp, ramp[1:])))

    def test_build_is_reproducible(self):
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder)
            _, first = build(self.recipe, 17, out)
            _, second = build(self.recipe, 17, out)
            self.assertEqual(first, second)
            rows = [line for line in (out/'fl-inspired.cube').read_text().splitlines()
                    if line and line[0].isdigit()]
            self.assertEqual(len(rows), 17**3)
            self.assertFalse(first['flash_ready'])
            self.assertFalse(first['camera_integration'])

    def test_pillow_interpolation_and_color_profile(self):
        from PIL import Image, ImageCms, ImageFilter
        rng = random.Random(20261111)
        pixels = [tuple(rng.randrange(256) for _ in range(3)) for _ in range(1000)]
        source = Image.new('RGB', (100, 10)); source.putdata(pixels)
        lut = ImageFilter.Color3DLUT(33, [c for row in self.table for c in row], channels=3)
        output = source.filter(lut)
        for original, actual in zip(pixels, output.getdata()):
            expected = interpolate(tuple(v/255 for v in original), self.table, 33)
            self.assertTrue(all(abs(a-round(b*255)) <= 1 for a,b in zip(actual, expected)))
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder); path = out/'input.png'; source.save(path)
            with self.assertRaisesRegex(ValueError, 'Untagged'):
                preview(path, self.table, 33, out, False)
            profile = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
            source.save(path, icc_profile=profile.tobytes())
            proof = preview(path, self.table, 33, out, False)
            self.assertEqual(proof['pixels'], [100, 10])
            with Image.open(out/'fl-preview.png') as final:
                self.assertEqual(final.size, source.size)
                self.assertTrue(final.info['icc_profile'])


if __name__ == '__main__':
    unittest.main()
