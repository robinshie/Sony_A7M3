#!/usr/bin/env python3
"""Exercise journal ordering and interrupted-write recovery without USB."""
import io
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from camera.lut_probe import Bundle
from research.lut_probe import IDS, TARGET, OFFSETS, candidate


class LutProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.directory = Path(self.tmp.name)
        self.bundle = Bundle.__new__(Bundle)
        self.bundle.path = self.directory
        self.bundle.original = {key: bytes(1280) for key in IDS}
        self.bundle.changed = candidate(self.bundle.original[TARGET])
        self.values = dict(self.bundle.original)
        self.writes = []
        self.failure = None
        test = self

        class Camera:
            def readBackup(self, key):
                return test.values[key]

            def writeBackup(self, key, data):
                test.assertEqual(key, TARGET)
                test.assertTrue(list(test.directory.glob('*/*-write-started.json')))
                test.assertTrue(list(test.directory.glob('*/before-settings.bin')))
                test.writes.append((key, data))
                if len(test.writes) == 1 and test.failure == 'before':
                    raise OSError('USB failed before acceptance')
                if len(test.writes) == 1 and test.failure == 'partial':
                    test.values[key] = data[:600] + test.values[key][600:]
                    raise OSError('USB failed after partial acceptance')
                test.values[key] = data
                if len(test.writes) == 1 and test.failure == 'after':
                    raise OSError('USB acknowledgement lost')

        self.camera = Camera()

        def snapshot(camera, expected):
            for key in IDS:
                want = expected if key == TARGET else test.bundle.original[key]
                if camera.readBackup(key) != want:
                    raise ValueError('Live preimage disagreement')
            return b'complete fake backup:' + b''.join(test.values.values())
        self.bundle.snapshot = snapshot

    def tearDown(self):
        self.tmp.cleanup()

    def test_apply_and_restore(self):
        self.bundle.operate(self.camera, 'apply')
        self.assertEqual(self.values[TARGET], self.bundle.changed)
        self.bundle.operate(self.camera, 'restore')
        self.assertEqual(self.values, self.bundle.original)
        self.assertEqual(len(self.writes), 2)

    def test_interrupted_writes_recover(self):
        for mode in ('before', 'partial', 'after'):
            with self.subTest(mode=mode):
                self.writes.clear(); self.failure = mode
                with self.assertRaises(OSError):
                    self.bundle.operate(self.camera, 'apply')
                self.assertEqual(self.values, self.bundle.original)
                self.assertEqual(len(self.writes), 2)

    def test_partial_recovery_after_reconnect(self):
        self.values[TARGET] = self.bundle.changed[:600] + self.bundle.original[TARGET][600:]
        self.bundle.operate(self.camera, 'restore')
        self.assertEqual(self.values, self.bundle.original)

    def test_unknown_target_refused(self):
        self.values[TARGET] = b'X' + bytes(1279)
        for operation in ('apply', 'restore', 'status'):
            with self.assertRaises(ValueError):
                self.bundle.operate(self.camera, operation)
        self.assertFalse(self.writes)

    def test_unrelated_lut_refused(self):
        self.values[IDS[1]] = b'X' + bytes(1279)
        with self.assertRaises(ValueError):
            self.bundle.operate(self.camera, 'apply')
        self.assertFalse(self.writes)

    def test_already_applied_is_noop(self):
        self.values[TARGET] = self.bundle.changed
        self.bundle.operate(self.camera, 'apply')
        self.assertFalse(self.writes)

    def test_status_has_no_write(self):
        self.bundle.operate(self.camera, 'status')
        self.assertFalse(self.writes)

    def test_exact_delta_and_bounds(self):
        old = self.bundle.original[TARGET]
        new = candidate(old)
        self.assertEqual([i for i,(a,b) in enumerate(zip(old,new)) if a != b], list(OFFSETS))
        self.assertEqual(new[1215:], old[1215:])
        self.assertEqual(len(OFFSETS), 27)
        for bad in (b'', bytes(1279), bytes(1281)):
            with self.assertRaises(ValueError): candidate(bad)
        bad = bytearray(old); bad[OFFSETS[0]] = 52
        with self.assertRaises(ValueError): candidate(bad)


if __name__ == '__main__':
    unittest.main()
