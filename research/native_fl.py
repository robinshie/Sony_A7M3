#!/usr/bin/env python3
"""Bounded FL-inspired color-table experiment for ILCE-7M3 4.04.

The native SD conversion supplies a nonlinear chroma grid. Rec.709-like Y/Cb/Cr
and display RGB are an experimental interpretation, not a measured ISP model.
This composes the existing original RGB recipe with each original table node.
It does not port A7 IV code, create native menu controls, or process RAW data.
"""
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from local import BUILD_ID, require, sha
from research.fl_look import DEFAULT_RECIPE, transform, validate
from research.lut_probe import IDS, TARGET

AVCAM_SHA = 'e1b0f84e8323005a34b43de6dd0083fca712d2c654f0d9716512e0a54631bbe7'
CODEC_BYTES = 129*2 + 513
KIND = 'native-fl-inspired-v0'
MAX_DELTA = (8, 12, 12)


class Codec:
    def __init__(self, data):
        require(len(data) == CODEC_BYTES, 'Wrong native coordinate codec length')
        self.raw = data
        self.expansion = struct.unpack('<129H', data[:258])
        self.compression = data[258:]
        require(self.expansion[0] == self.compression[0] == 0 and
                self.expansion[-1] == 512 and self.compression[-1] == 128,
                'Wrong native coordinate codec endpoints')
        require(all(a <= b for a,b in zip(self.expansion, self.expansion[1:])) and
                all(a <= b for a,b in zip(self.compression, self.compression[1:])),
                'Native coordinate codec must be monotonic')

    def expand(self, value):
        require(isinstance(value, int) and not isinstance(value, bool), 'Integer native code required')
        return (-1 if value < 0 else 1) * self.expansion[min(abs(value), 128)]

    def compress(self, value):
        require(isinstance(value, int) and not isinstance(value, bool), 'Integer expanded code required')
        return (-1 if value < 0 else 1) * self.compression[min(abs(value), 512)]

    @classmethod
    def from_firmware(cls, raw):
        require(sha(raw) == AVCAM_SHA, 'Wrong firmware for native color coordinates')
        return cls(raw[0x8a999e:0x8a9aa0] + raw[0x9b5921:0x9b5b22])


def bounded(value, low, high):
    return min(high, max(low, value))

def cap_level_code(raw, level):
    """Signed interpretation after the original non-SD scale and 7-bit pack."""
    signed = raw if raw < 128 else raw-256
    packed = (signed if level == 8 else signed * level // 8) & 127
    return packed if packed < 64 else packed-128


def build_table(original, codec, recipe, strength=0.65, *, capture_table=None):
    require(len(original) == 1280, 'Expected native property size 1280')
    require(isinstance(strength, (int, float)) and not isinstance(strength, bool) and
            math.isfinite(strength) and 0 <= strength <= 1, 'Invalid strength')
    validate(recipe)
    # The CAP source is stored as seven-bit nodes. The original level-8
    # path masks each component to seven bits; levels 1–7 scale the raw
    # signed-eight-bit input instead and are outside this experiment.
    require(capture_table in (None, 1, 2), 'Unknown CAP source table')
    packed7 = capture_table == 2
    sign, wrap = (64, 128) if packed7 else (128, 256)
    require(not packed7 or all(x < wrap for x in original[:1215]), 'CAP source must use seven-bit nodes')
    old = [x if x < sign else x-wrap for x in original[:1215]]
    require(all(-64 <= x <= 63 for x in old), 'Source must use signed eight-bit/seven-bit-compatible nodes')
    if strength == 0:
        return original
    out = bytearray(original)
    for a in range(5):
        for b in range(9):
            for c in range(9):
                i = a*81+b*9+c
                base = [old[i+p*405] for p in range(3)]
                y = bounded(a*64 + base[0], 0, 256)/256
                # Native SD path adds an arithmetic-shifted 3/4 correction in
                # compressed coordinates, then uses the original expansion.
                cb_code = bounded((b-4)*32 + (base[1]*3//4), -128, 128)
                cr_code = bounded((c-4)*32 + (base[2]*3//4), -128, 128)
                cb, cr = codec.expand(cb_code)/1024, codec.expand(cr_code)/1024
                rgb = (y + 1.5748*cr, y - .187324*cb - .468124*cr, y + 1.8556*cb)
                clipped = tuple(bounded(v, 0, 1) for v in rgb)
                look = transform(clipped, recipe)
                # Apply only the look delta at out-of-gamut nodes. Do not fold
                # RGB clipping itself into the original calibration table.
                dr, dg, db = (strength*(v-u) for u,v in zip(clipped, look))
                dy = .2126*dr + .7152*dg + .0722*db
                next_cb = codec.compress(round((cb + (db-dy)/1.8556)*1024))
                next_cr = codec.compress(round((cr + (dr-dy)/1.5748)*1024))
                delta = (round(dy*256), round((next_cb-cb_code)*4/3), round((next_cr-cr_code)*4/3))
                for plane in range(3):
                    step = bounded(delta[plane], -MAX_DELTA[plane], MAX_DELTA[plane])
                    value = bounded(base[plane]+step, -64, 63)
                    # Keep the luminance endpoints inside the original domain.
                    if plane == 0:
                        lo,hi=max(-64,-a*64),min(63,256-a*64)
                        # Preserve the CAP factory endpoint offset when it
                        # already lies outside the nominal display domain.
                        if capture_table is not None:
                            lo,hi=min(lo,base[plane]),max(hi,base[plane])
                        value = bounded(value,lo,hi)
                    at = i+plane*405
                    encoded = value & (wrap-1)
                    if capture_table is not None and any(abs(cap_level_code(encoded, level) -
                                           cap_level_code(original[at], level)) > MAX_DELTA[plane]
                                       for level in range(1, 8)):
                        # Keep original nodes at scale-dependent wrap boundaries.
                        encoded = original[at]
                    out[at] = encoded
    require(out[1215:] == original[1215:], 'Native property tail changed')
    require(all(abs((new if new < sign else new-wrap)-before) <= MAX_DELTA[p]
                for p in range(3) for before,new in zip(old[p*405:(p+1)*405], out[p*405:(p+1)*405])),
            'Native experiment exceeded its code-delta budget')
    return bytes(out)


def prepare(snapshot, avcam, pmca, output):
    from pmca.backup import BackupFile
    require(not output.exists(), 'Use a new private FL experiment directory')
    raw = snapshot.read_bytes(); backup = BackupFile(io.BytesIO(raw))
    require(backup.revision == 4 and backup.size == len(raw), 'Complete BK4 required')
    original = {key: bytes(backup.getProperty(key).data) for key in IDS}
    require(all(len(v) == 1280 for v in original.values()) and
            all(backup.getProperty(key).attr == 8 for key in IDS), 'Unexpected native properties')
    codec = Codec.from_firmware(avcam.read_bytes())
    recipe_raw = DEFAULT_RECIPE.read_bytes(); recipe = validate(json.loads(recipe_raw))
    changed = build_table(original[TARGET], codec, recipe)
    require(changed != original[TARGET], 'FL table has no effect')
    stream = io.BytesIO(raw); edited = BackupFile(stream)
    edited.setProperty(TARGET, changed); edited.updateChecksum()
    modified = stream.getvalue(); check = BackupFile(io.BytesIO(modified))
    for key, prop in backup.listProperties():
        require(check.getProperty(key) == (prop._replace(data=changed) if key == TARGET else prop),
                'Unrelated setting changed')
    artifacts = {'original-settings.bin': raw, 'candidate-settings.bin': modified,
                 'candidate.bin': changed, 'codec.bin': codec.raw, 'recipe.json': recipe_raw}
    artifacts.update({f'{key:08x}.bin': value for key,value in original.items()})
    output.mkdir(mode=0o700, parents=True)
    for name,data in artifacts.items():
        with (output/name).open('xb') as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
    subprocess.run([sys.executable, str(ROOT/'research/lut3d_native.py'), '--avcam', str(avcam),
                    '--settings', str(output/'candidate-settings.bin'), '--pmca', str(pmca),
                    '--out', str(output/'qemu')], check=True)
    sources = ('research/native_fl.py', 'research/fl_look.py', 'camera/native_fl.py',
               'camera/lut_probe.py', 'research/lut_probe.py', 'recipes/fl-inspired-v0.json')
    manifest = {'schema': 1, 'kind': KIND, 'property': TARGET, 'build': BUILD_ID.decode(),
                'strength': .65, 'purpose': 'bounded native FL-inspired experiment',
                'changed_bytes': sum(a != b for a,b in zip(original[TARGET], changed)),
                'max_delta_per_plane': MAX_DELTA, 'files': {p: sha(v) for p,v in artifacts.items()},
                'qemu_proof_sha256': sha((output/'qemu/proof.json').read_bytes()),
                'source_sha256': {p: sha((ROOT/p).read_bytes()) for p in sources},
                'native_menu': False, 'isp_color_model_measured': False,
                'sony_fl_match': False, 'persistent_save_requested': False}
    (output/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('NATIVE_FL_EXPERIMENT_PREPARED', output, 'changed_bytes='+str(manifest['changed_bytes']))


def main():
    os.umask(0o077)
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('snapshot', 'avcam', 'pmca', 'out'):
        p.add_argument('--'+name, required=True, type=lambda s: Path(s).expanduser().resolve())
    args = p.parse_args(); sys.path.insert(0, str(args.pmca))
    prepare(args.snapshot, args.avcam, args.pmca, args.out)


if __name__ == '__main__':
    main()
