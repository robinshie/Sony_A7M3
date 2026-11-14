#!/usr/bin/env python3
"""Render a supplied photo on a temporary A7M3 test module and verify its pixels."""
import argparse
import ctypes
from hashlib import sha256
import io
import json
from pathlib import Path
import struct
import subprocess
import sys
import time

from PIL import Image, ImageCms, ImageDraw, ImageFilter, ImageFont, ImageOps

from film_texture_preview import Parameters
from fl_look import cube_table, validate

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CONFIG = (9, 9, 16, 1987)


def base_photo(path, untagged_profile):
    destination = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
    with Image.open(path) as source:
        if source.mode != 'RGB':
            raise ValueError('Expected an 8-bit RGB photo')
        embedded = source.info.get('icc_profile')
        if not embedded and not untagged_profile:
            raise ValueError('Untagged photo needs its source ICC profile')
        profile = ImageCms.ImageCmsProfile(io.BytesIO(embedded) if embedded else str(untagged_profile))
        photo = ImageCms.profileToProfile(ImageOps.exif_transpose(source), profile, destination)
    photo.thumbnail((576, 384), Image.Resampling.LANCZOS)
    recipe = validate(json.loads((ROOT / 'recipes/leica-film-inspired.json').read_text()))
    base = photo.filter(ImageFilter.Color3DLUT(
        33, [channel for row in cube_table(recipe, 33) for channel in row], channels=3))
    return base, destination.tobytes()


def reference(out, raw, width, height):
    language = ROOT / 'payloads/a7-film-texture.c'
    library = out / 'reference.dylib'
    subprocess.run(['clang', '-O2', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                    str(language), '-o', str(library)], check=True)
    f = ctypes.CDLL(str(library)).a7_film_texture
    pointer, size, integer = ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint
    f.argtypes = [pointer, size, integer, pointer, size, integer,
                  integer, integer, ctypes.POINTER(Parameters), pointer, size]
    f.restype = ctypes.c_int
    dst = ctypes.create_string_buffer(len(raw))
    workspace = (ctypes.c_uint32 * (width * 18))()
    grain, halo, radius, seed = CONFIG
    p = Parameters(grain, halo, (ctypes.c_int * 5)(), radius, seed)
    if f(raw, len(raw), width * 3, dst, len(raw), width * 3, width, height,
         ctypes.byref(p), workspace, ctypes.sizeof(workspace)) != 0:
        raise ValueError('Desktop pixel reference failed')
    return dst.raw


def render_card(out, original, edited, icc, live):
    w, h = original.size
    font = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 19)
    small = ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc', 15)
    size = (2 * w + 36, h + 108)
    panel = Image.new('RGB', size, '#17191d')
    draw = ImageDraw.Draw(panel)
    draw.text((12, 9), 'Sony A7 III photo / FL3 texture test', font=font, fill='white')
    note = 'Processed by the camera CPU in maintenance mode' if live else 'Desktop reference'
    draw.text((12, 37), note, font=small, fill='#d2d4d6')
    for x, label, image in ((12, 'Grain off / halation off', original),
                            (24 + w, 'Grain 9 / halation 9', edited)):
        draw.text((x, 66), label, font=font, fill='white')
        panel.paste(image, (x, 92))
    panel.save(out / 'comparison.png', icc_profile=icc)
    edited.save(out / 'processed.png', icc_profile=icc)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('photo', type=Path)
    p.add_argument('--untagged-profile', type=Path)
    p.add_argument('--live', action='store_true')
    a = p.parse_args()
    out = ROOT / '.lab/film-photo-probe' / str(time.time_ns())
    out.mkdir(parents=True, mode=0o700)
    base, icc = base_photo(a.photo, a.untagged_profile)
    w, h = base.size
    raw = base.tobytes()
    (out / 'input.rgb').write_bytes(raw)
    expected = reference(out, raw, w, h)
    changed = sum(raw[i:i+3] != expected[i:i+3] for i in range(0, len(raw), 3))
    if not changed:
        raise ValueError('Effects did not alter the supplied photo')
    actual = expected
    if a.live:
        from camera import handoff, service
        from local import BUILD_ID

        (out / 'photo.S').write_text(
            '.section .rodata\n.balign 4\n.global photo_rgb\n.hidden photo_rgb\n'
            'photo_rgb:\n.incbin "input.rgb"\n.section .note.GNU-stack,"",%progbits\n')
        subprocess.run(['arm-none-eabi-gcc', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-mcpu=cortex-a9', '-marm', '-mfloat-abi=soft',
                        '-mno-unaligned-access', '-fPIC', '-fvisibility=hidden',
                        '-ffreestanding', '-fno-builtin', '-fno-unwind-tables',
                        '-fno-asynchronous-unwind-tables', '-nostdlib', '-shared',
                        '-Wl,--no-undefined', '-Wl,-z,noexecstack', '-I', str(ROOT / 'payloads'),
                        f'-DPHOTO_WIDTH={w}', f'-DPHOTO_HEIGHT={h}',
                        str(ROOT / 'research/film_photo_probe.c'),
                        str(ROOT / 'payloads/a7-film-texture.c'), 'photo.S', '-lgcc', '-o', 'probe.so'],
                       cwd=out, check=True)
        payload = (out / 'probe.so').read_bytes()
        if len(payload) > 768 * 1024:
            raise ValueError('Probe exceeds its USB transfer limit')

        def collect(camera, action):
            nonlocal actual
            factory = service.Factory(camera)
            if (factory.contents('/version.txt') != BUILD_ID or
                    bytes(camera.readBackup(0x3e0005)) != b'ILCE-7M3' + bytes(8)):
                raise ValueError('Wrong camera model or build')
            report = factory.run(payload, 'a7fp.bin')
            if (len(report) != 20 + len(expected) or
                    struct.unpack_from('<5I', report) != (0x41374650, 1, w, h, 0)):
                raise ValueError('Bad image report from the camera')
            actual = report[20:]
            if actual != expected:
                raise ValueError('Camera RGB output differs from the desktop reference')
            (out / 'camera.rgb').write_bytes(actual)

        previous_switch, previous_perform = handoff.SWITCH, service.perform
        handoff.SWITCH += ' --host-identity-check'
        service.perform = collect
        try:
            handoff.run('settings-snapshot')
        finally:
            handoff.SWITCH, service.perform = previous_switch, previous_perform

    finished = Image.frombytes('RGB', (w, h), actual)
    render_card(out, base, finished, icc, a.live)
    proof = dict(source_photo_sha256=sha256(a.photo.read_bytes()).hexdigest(), size=[w, h],
                 input_sha256=sha256(raw).hexdigest(), output_sha256=sha256(actual).hexdigest(),
                 changed_pixels=changed, grain=CONFIG[0], halation=CONFIG[1], radius=CONFIG[2],
                 camera_cpu_rendered=a.live, native_frame_bound=False, firmware_written=False)
    (out / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print('EVIDENCE', out)
    print(json.dumps(proof))


if __name__ == '__main__':
    main()
