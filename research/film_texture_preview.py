#!/usr/bin/env python3
"""Render FL3 + grain/halation/five-point curve on desktop, never on camera.

Uses the tested C implementation, not an AI-generated illustration or an ISP
simulation. Requires Clang and Pillow. Full-size RGB image buffers live on Mac.
"""
import argparse
import ctypes
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time

from fl_look import cube_table, validate

ROOT = Path(__file__).resolve().parents[1]


class Parameters(ctypes.Structure):
    _fields_ = [('grain', ctypes.c_int), ('halation', ctypes.c_int),
                ('curve', ctypes.c_int * 5), ('radius', ctypes.c_uint), ('seed', ctypes.c_uint32)]


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--input', required=True, type=Path)
    cli.add_argument('--out', type=Path, default=ROOT / '.lab/fl3-film-preview')
    cli.add_argument('--recipe', type=Path, default=ROOT / 'recipes/leica-film-inspired.json')
    cli.add_argument('--grain', type=int, choices=range(10), default=5)
    cli.add_argument('--halation', type=int, choices=range(10), default=6)
    cli.add_argument('--curve', type=int, nargs=5, default=[2, -3, 0, 2, -2],
                     metavar=('BLACK', 'SHADOW', 'MID', 'HIGHLIGHT', 'WHITE'))
    cli.add_argument('--radius', type=int, choices=range(1, 17), default=8)
    cli.add_argument('--seed', type=int, default=1987)
    cli.add_argument('--assume-srgb', action='store_true')
    args = cli.parse_args()
    if any(v < -9 or v > 9 for v in args.curve) or not 0 <= args.seed <= 0xffffffff:
        cli.error('Curve must be -9..9 and seed must be uint32')
    out = args.out.resolve()
    names = ('libfilm-texture.dylib', 'libfilm-texture.so', 'fl3-color.png', 'fl3-film.png',
             'comparison.png', 'detail.png', 'curve.png', 'proof.json')
    if args.input.resolve() in {out / n for n in names} or args.recipe.resolve() in {out / n for n in names}:
        cli.error('Input files must not overlap generated outputs')
    recipe = validate(json.loads(args.recipe.read_text()))
    from PIL import Image, ImageCms, ImageDraw, ImageFilter, ImageFont, ImageOps
    raw = args.input.read_bytes()
    with Image.open(io.BytesIO(raw)) as source:
        if source.mode != 'RGB':
            cli.error('Only 8-bit RGB JPEG/PNG input is supported')
        photo = ImageOps.exif_transpose(source)
        srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
        if source.info.get('icc_profile'):
            photo = ImageCms.profileToProfile(photo, ImageCms.ImageCmsProfile(io.BytesIO(source.info['icc_profile'])), srgb, outputMode='RGB')
        elif args.assume_srgb:
            photo = photo.copy()
        else:
            cli.error('Untagged image: use --assume-srgb only for sRGB pixels')
    width, height = photo.size
    if width > 16384 or height > 16384:
        cli.error('Image dimensions exceed the tested kernel bounds')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'proof.json').unlink(missing_ok=True)
    table = cube_table(recipe, 33)
    base = photo.filter(ImageFilter.Color3DLUT(33, [c for row in table for c in row], channels=3))
    suffix = '.dylib' if sys.platform == 'darwin' else '.so'
    library = out / ('libfilm-texture' + suffix)
    subprocess.run(['clang', '-O2', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                    str(ROOT / 'payloads/a7-film-texture.c'), '-o', str(library)], check=True)
    kernel = ctypes.CDLL(str(library))
    kernel.a7_film_texture_workspace.argtypes = [ctypes.c_uint, ctypes.c_uint]
    kernel.a7_film_texture_workspace.restype = ctypes.c_size_t
    kernel.a7_film_texture.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint,
                                     ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint,
                                     ctypes.c_uint, ctypes.c_uint, ctypes.POINTER(Parameters),
                                     ctypes.c_void_p, ctypes.c_size_t]
    kernel.a7_film_texture.restype = ctypes.c_int
    pixel_bytes = width * height * 3
    src = (ctypes.c_uint8 * pixel_bytes).from_buffer_copy(base.tobytes())
    dst = (ctypes.c_uint8 * pixel_bytes)()
    workspace_bytes = kernel.a7_film_texture_workspace(width, args.radius)
    workspace = (ctypes.c_uint32 * ((workspace_bytes + 3) // 4))()
    params = Parameters(args.grain, args.halation, (ctypes.c_int * 5)(*args.curve), args.radius, args.seed)
    start = time.perf_counter()
    rc = kernel.a7_film_texture(src, pixel_bytes, width * 3, dst, pixel_bytes, width * 3,
                                width, height, ctypes.byref(params), workspace, workspace_bytes)
    seconds = time.perf_counter() - start
    if rc:
        raise ValueError('Texture kernel rejected the buffers or parameters')
    result = Image.frombytes('RGB', (width, height), bytes(dst))
    for name, im in (('fl3-color.png', base), ('fl3-film.png', result)):
        im.save(out / name, icc_profile=srgb.tobytes())
    font_path = Path('/System/Library/Fonts/Supplemental/Arial.ttf')
    font = ImageFont.truetype(str(font_path), 17) if font_path.exists() else ImageFont.load_default()
    def contact(images, labels, name, thumbnail=None):
        rendered = [im.copy() for im in images]
        if thumbnail:
            for im in rendered:
                im.thumbnail(thumbnail)
        canvas = Image.new('RGB', (sum(im.width for im in rendered), max(im.height for im in rendered) + 58), '#16181c')
        draw = ImageDraw.Draw(canvas)
        x = 0
        for im, label in zip(rendered, labels):
            draw.text((x + 10, 8), label, font=font, fill='white')
            draw.text((x + 10, 31), 'DESKTOP REFERENCE / NOT CAMERA OUTPUT', font=font, fill='#bababa')
            canvas.paste(im, (x, 58)); x += im.width
        canvas.save(out / name, icc_profile=srgb.tobytes())
    labels = ['Original', 'FL3 color only', f'FL3 + grain {args.grain} / halo {args.halation} / 5-point curve']
    contact([photo, base, result], labels, 'comparison.png', (640, 640))
    crop_w, crop_h = min(520, width), min(440, height)
    left, top = (width - crop_w) // 2, (height - crop_h) // 2
    box = (left, top, left + crop_w, top + crop_h)
    contact([im.crop(box) for im in (photo, base, result)], labels, 'detail.png')
    curve_image = Image.new('RGB', (640, 400), '#16181c'); draw = ImageDraw.Draw(curve_image)
    draw.text((30, 14), 'Five-point curve: black / shadow / mid / highlight / white', font=font, fill='white')
    xvals = [0, 64, 128, 192, 255]; yvals = []
    for x, v in zip(xvals, args.curve):
        yvals.append(max(yvals[-1] if yvals else 0, min(255, x + 4 * v)))
    draw.line([(45, 350), (595, 60)], fill='#666666', width=1)
    points = [(45 + x * 550 / 255, 350 - y * 290 / 255) for x, y in zip(xvals, yvals)]
    draw.line(points, fill='#f8a85a', width=3)
    for (x, y), value in zip(points, args.curve):
        draw.ellipse((x - 4, y - 4, x + 4, y + 4), fill='#ffffff')
        draw.text((x - 10, y + 8), f'{value:+}', font=font, fill='white')
    curve_image.save(out / 'curve.png')
    digest = lambda b: hashlib.sha256(b).hexdigest()
    proof = dict(camera_integration=False, flash_ready=False, input_sha256=digest(raw),
                 input_pixels=[width, height], recipe_sha256=digest(args.recipe.read_bytes()),
                 parameters=dict(grain=args.grain, halation=args.halation, curve=args.curve, radius=args.radius, seed=args.seed),
                 desktop_texture_seconds=seconds, workspace_bytes=workspace_bytes,
                 source_sha256={name: digest((ROOT / name).read_bytes()) for name in
                                ('payloads/a7-film-texture.c', 'payloads/a7-film-texture.h',
                                 'research/film_texture_preview.py', 'research/fl_look.py')},
                 output_sha256={name: digest((out / name).read_bytes()) for name in names if (out / name).exists()})
    (out / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(dict(out=str(out), seconds=seconds, workspace=workspace_bytes, camera_integration=False)))


if __name__ == '__main__':
    main()
