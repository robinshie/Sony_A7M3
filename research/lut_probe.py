#!/usr/bin/env python3
"""Prepare one bounded, reversible diagnostic LUT change; this is not FL."""
import argparse
import io
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from local import BUILD_ID, require, sha

IDS = (0x30004, 0x30005, 0x30006, 0x30007)
TARGET = IDS[0]
OFFSETS = tuple(405 + a*81 + b*9 + c
                for a in range(1, 4) for b in range(3, 6) for c in range(3, 6))


def candidate(original):
    require(len(original) == 1280, 'Expected a 1280-byte native LUT property')
    data = bytearray(original)
    for offset in OFFSETS:
        value = original[offset] if original[offset] < 128 else original[offset] - 256
        require(-64 <= value <= 51, 'Probe would exceed signed seven-bit bounds')
        data[offset] = (value + 12) & 255
    require(sum(a != b for a, b in zip(data, original)) == 27, 'Probe change count')
    return bytes(data)


def prepare(snapshot, avcam, pmca, output):
    from pmca.backup import BackupFile
    require(not output.exists(), 'Use a new private experiment directory')
    raw = snapshot.read_bytes()
    backup = BackupFile(io.BytesIO(raw))
    require(backup.revision == 4 and backup.size == len(raw), 'Complete BK4 snapshot required')
    original = {key: bytes(backup.getProperty(key).data) for key in IDS}
    require(all(len(v) == 1280 for v in original.values()), 'Unexpected source LUT size')
    require(all(backup.getProperty(key).attr == 8 for key in IDS), 'Unexpected source attributes')
    changed = candidate(original[TARGET])
    stream = io.BytesIO(raw)
    copy = BackupFile(stream)
    copy.setProperty(TARGET, changed)
    copy.updateChecksum()
    modified = stream.getvalue()
    check = BackupFile(io.BytesIO(modified))
    for key, prop in backup.listProperties():
        require(check.getProperty(key) == (prop._replace(data=changed) if key == TARGET else prop),
                'Unrelated backup property changed')
    output.mkdir(mode=0o700, parents=True)
    artifacts = {'original-settings.bin': raw, 'candidate-settings.bin': modified,
                 'candidate.bin': changed}
    artifacts.update({f'{key:08x}.bin': value for key, value in original.items()})
    for name, data in artifacts.items():
        with (output/name).open('xb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
    subprocess.run([sys.executable, str(ROOT/'research/lut3d_native.py'),
                    '--avcam', str(avcam), '--settings', str(output/'candidate-settings.bin'),
                    '--pmca', str(pmca), '--out', str(output/'qemu')], check=True)
    proof = output/'qemu/proof.json'
    sources = ('research/lut_probe.py', 'camera/lut_probe.py')
    manifest = {'schema': 1, 'purpose': 'diagnostic-only; not FL',
                'build': BUILD_ID.decode(), 'property': TARGET,
                'changed_offsets': OFFSETS, 'code_delta': 12,
                'files': {name: sha(value) for name, value in artifacts.items()},
                'qemu_proof_sha256': sha(proof.read_bytes()),
                'source_sha256': {p: sha((ROOT/p).read_bytes()) for p in sources},
                'camera_write_performed': False, 'jpeg_effect_proven': False}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('LUT_PROBE_PREPARED', output)


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('snapshot', 'avcam', 'pmca', 'out'):
        p.add_argument('--'+name, type=lambda s: Path(s).expanduser().resolve(), required=True)
    args = p.parse_args()
    sys.path.insert(0, str(args.pmca))
    prepare(args.snapshot, args.avcam, args.pmca, args.out)


if __name__ == '__main__':
    main()
