#!/usr/bin/env python3
"""Build an original sRGB FL-inspired experiment; no camera writes or Sony LUTs.

The RGB cube is the complete desktop color transform. The 1025-node u16 file
contains only its tone curve, for offline native sampler research, not flashing.
"""
import argparse
import colorsys
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import time

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECIPE = ROOT / 'recipes/fl-inspired-v0.json'


def clamp(v):
    return min(1.0, max(0.0, v))


def decode(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def encode(v):
    return v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def validate(recipe):
    if recipe.get('version') != 1:
        raise ValueError('Unsupported recipe version')
    if recipe.get('input_space') != 'sRGB' or recipe.get('output_space') != 'sRGB':
        raise ValueError('Only display-referred sRGB input/output is implemented')
    def number(value, low, high):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f'Expected a finite number in [{low}, {high}], got {value!r}')
    number(recipe['strength'], 0, 1)
    number(recipe['exposure_ev'], -4, 4)
    number(recipe['saturation'], 0, 2)
    matrix = recipe['linear_matrix']
    if len(matrix) != 3 or any(len(row) != 3 for row in matrix):
        raise ValueError('Matrix must be 3 by 3')
    for row in matrix:
        for v in row:
            number(v, -2, 2)
        if abs(sum(row) - 1) > 1e-9:
            raise ValueError('Matrix rows must sum to one to preserve neutral grays')
    curve = recipe['tone_curve']
    if len(curve) < 2 or curve[0][0] != 0 or curve[-1][0] != 1:
        raise ValueError('Tone curve must cover [0, 1]')
    for point in curve:
        if len(point) != 2:
            raise ValueError('Tone points must contain x and y')
        for v in point:
            number(v, 0, 1)
    if any(b[0] <= a[0] or b[1] < a[1] for a, b in zip(curve, curve[1:])):
        raise ValueError('Tone curve must have increasing x and nondecreasing y')
    for band in recipe['hue_bands']:
        number(band['center'], 0, 360)
        number(band['width'], 1, 180)
        number(band['shift'], -45, 45)
        number(band['saturation'], 0, 2)
    split = recipe.get('split_tone')
    if split is not None:
        if len(split) != 5 or any(len(row) != 2 for row in split):
            raise ValueError('Split tone needs five Cb/Cr pairs')
        for cb, cr in split:
            number(cb, -.125, .125)
            number(cr, -.125, .125)
    model = recipe.get('reference_ycc_q10')
    if model is not None:
        if (len(model) != 5 or any(len(plane) != 9 for plane in model)
                or any(len(node) != 3 for plane in model for node in plane)):
            raise ValueError('Reference model needs five 9-by-3 planes')
        if any(type(v) is not int or abs(v) > 512 for plane in model for node in plane for v in node):
            raise ValueError('Reference coefficients must be integers in [-512, 512]')
    return recipe


def tone(value, points):
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if value <= x1:
            return y0 + (y1 - y0) * (value - x0) / (x1 - x0)
    return points[-1][1]


def reference_ycc(rgb, model):
    r, g, b = rgb
    y = .2126*r + .7152*g + .0722*b
    cb, cr = (b-y)/1.8556, (r-y)/1.5748
    k = min(7, int(8*y))
    f = 8*y - k
    weights = (1, 2*cb, 2*cr, 4*cb*cb, 4*cr*cr)
    dy, dcb, dcr = [sum(w * (p[k][j] + f*(p[k+1][j] - p[k][j]))
                       for w, p in zip(weights, model))/1024 for j in range(3)]
    y, cb, cr = y+dy, cb+dcb, cr+dcr
    return y+1.5748*cr, y-.187324*cb-.468124*cr, y+1.8556*cb


def transform(rgb, recipe):
    if len(rgb) != 3 or any(not math.isfinite(v) or not 0 <= v <= 1 for v in rgb):
        raise ValueError('RGB must contain three finite sRGB values in [0, 1]')
    strength = recipe['strength']
    if strength == 0:
        return tuple(rgb)
    if (model := recipe.get('reference_ycc_q10')) is not None:
        return tuple(clamp(a + strength*(b-a)) for a, b in zip(rgb, reference_ycc(rgb, model)))
    linear = [decode(v) * 2 ** recipe['exposure_ev'] for v in rgb]
    mixed = [encode(clamp(sum(a * b for a, b in zip(row, linear))))
             for row in recipe['linear_matrix']]
    h, s, v = colorsys.rgb_to_hsv(*mixed)
    hue, scale, shift = h * 360, recipe['saturation'], 0.0
    for band in recipe['hue_bands']:
        distance = abs((hue - band['center'] + 180) % 360 - 180)
        weight = max(0.0, 1 - distance / band['width'])
        weight = weight * weight * (3 - 2 * weight)
        shift += weight * band['shift']
        scale *= 1 + weight * (band['saturation'] - 1)
    colored = colorsys.hsv_to_rgb(((hue + shift) % 360) / 360, clamp(s * scale), v)
    result = [tone(c, recipe['tone_curve']) for c in colored]
    if (split := recipe.get('split_tone')) is not None:
        y = .2126 * colored[0] + .7152 * colored[1] + .0722 * colored[2]
        i = min(int(y * 4), 3)
        f = y * 4 - i
        cb, cr = (a + f * (b - a) for a, b in zip(split[i], split[i + 1]))
        result = [clamp(c + offset) for c, offset in
                  zip(result, (1.5748 * cr, -.187324 * cb - .468124 * cr, 1.8556 * cb))]
    return tuple(clamp(a + strength * (b - a)) for a, b in zip(rgb, result))


def cube_table(recipe, size):
    if not isinstance(size, int) or not 2 <= size <= 65:
        raise ValueError('Cube size must be an integer from 2 through 65')
    # Red varies fastest, then green, then blue (Pillow and Adobe Cube order).
    return [transform((r / (size-1), g / (size-1), b / (size-1)), recipe)
            for b in range(size) for g in range(size) for r in range(size)]


def interpolate(rgb, table, size):
    """Trilinear reference for tests; image rendering uses Pillow's native loop."""
    pos = [clamp(v) * (size-1) for v in rgb]
    base = [min(int(v), size-2) for v in pos]
    frac = [v-i for v, i in zip(pos, base)]
    out = [0.0] * 3
    for b in (0, 1):
        for g in (0, 1):
            for r in (0, 1):
                weight = math.prod(t if d else 1-t for d, t in zip((r, g, b), frac))
                node = table[base[0]+r + size*(base[1]+g) + size*size*(base[2]+b)]
                for c in range(3):
                    out[c] += weight * node[c]
    return tuple(out)


def native_tone(recipe):
    """Only the scalar tone component, NOT the full RGB transform or an ISP LUT.

    Native nodes lie at i*64, i=0..1024; the last coordinate is 65536.
    Capping its value at 65535 means even an identity table is not exact at
    the upper endpoint when sampled by the native integer interpolator.
    """
    values = []
    for i in range(1025):
        x = min(i * 64, 65535) / 65535
        y = x + recipe['strength'] * (tone(x, recipe['tone_curve']) - x)
        values.append(int(clamp(y) * 65535 + 0.5))
    return struct.pack('<1025H', *values)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build(recipe, size, out):
    out.mkdir(parents=True, exist_ok=True)
    (out / 'proof.json').unlink(missing_ok=True)
    table = cube_table(recipe, size)
    label = ('FL Inspired Experimental v0' if recipe['id'] == 'fl-inspired-v0'
             else recipe.get('name', recipe['id']))
    label = label.encode('ascii', 'replace').decode().replace('"', "'").replace('\r', ' ').replace('\n', ' ')
    cube = ('# Original FL-inspired experiment, not Sony FL. Input/output: sRGB.\n'
            f'TITLE "{label}"\n'
            f'LUT_3D_SIZE {size}\nDOMAIN_MIN 0 0 0\nDOMAIN_MAX 1 1 1\n')
    cube += ''.join(' '.join(f'{v:.9f}' for v in row) + '\n' for row in table)
    files = {'fl-inspired.cube': cube.encode(), 'tone-u16le-1025.bin': native_tone(recipe),
             'recipe.json': (json.dumps(recipe, ensure_ascii=False, indent=2) + '\n').encode()}
    for name, content in files.items():
        (out / name).write_bytes(content)
    proof = {'recipe_id': recipe['id'], 'cube_size': size,
             'input_output': 'display-referred sRGB, normalized 0..1',
             'interpolation': 'trilinear', 'files_sha256': {k: digest(v) for k, v in files.items()},
             'source_sha256': digest(Path(__file__).read_bytes()),
             'native_tone_scope': 'scalar curve only; excludes matrix, hue/saturation, split tone and reference YCC fitting',
             'sony_fl_match_validated': False, 'camera_integration': False, 'flash_ready': False}
    return table, proof


def preview(source, table, size, out, assume_srgb, label='FL-inspired v0'):
    from PIL import Image, ImageCms, ImageDraw, ImageFilter, ImageOps
    data = source.read_bytes()
    with Image.open(io.BytesIO(data)) as opened:
        if opened.mode != 'RGB':
            raise ValueError('Preview accepts 8-bit RGB JPEG/PNG; decode RAW separately')
        photo = ImageOps.exif_transpose(opened)
        srgb = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB'))
        icc = opened.info.get('icc_profile')
        if icc:
            photo = ImageCms.profileToProfile(photo, ImageCms.ImageCmsProfile(io.BytesIO(icc)), srgb, outputMode='RGB')
        elif not assume_srgb:
            raise ValueError('Untagged input: pass --assume-srgb only if its pixels are sRGB')
        else:
            photo = photo.copy()
    start = time.perf_counter()
    lut = ImageFilter.Color3DLUT(size, [c for row in table for c in row], channels=3)
    result = photo.filter(lut)
    elapsed = time.perf_counter() - start
    result.save(out / 'fl-preview.png', icc_profile=srgb.tobytes())
    before, after = photo.copy(), result.copy()
    before.thumbnail((900, 900)); after.thumbnail((900, 900))
    comparison = Image.new('RGB', (before.width * 2, before.height + 32), '#202020')
    comparison.paste(before, (0, 32)); comparison.paste(after, (before.width, 32))
    draw = ImageDraw.Draw(comparison)
    draw.text((10, 8), 'Before (sRGB)', fill='white')
    draw.text((before.width+10, 8), f'{label} / desktop experiment', fill='white')
    comparison.save(out / 'comparison.png', icc_profile=srgb.tobytes())
    return {'input_sha256': digest(data), 'output_sha256': digest((out / 'fl-preview.png').read_bytes()),
            'pixels': list(photo.size), 'desktop_filter_seconds': elapsed,
            'profile': 'converted ICC to sRGB' if icc else 'user explicitly assumed sRGB'}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('action', choices=('build', 'preview'))
    cli.add_argument('--recipe', type=Path, default=DEFAULT_RECIPE)
    cli.add_argument('--out', type=Path, default=ROOT / '.lab/fl-v0')
    cli.add_argument('--size', type=int, choices=(17, 33, 65), default=33)
    cli.add_argument('--input', type=Path)
    cli.add_argument('--assume-srgb', action='store_true')
    args = cli.parse_args()
    if args.action == 'preview' and args.input is None:
        cli.error('preview requires --input')
    if args.input and args.input.resolve() in {args.out.resolve() / name for name in
                                             ('fl-preview.png', 'comparison.png', 'recipe.json', 'fl-inspired.cube', 'tone-u16le-1025.bin', 'proof.json')}:
        cli.error('Input must not be one of the generated output files')
    recipe = validate(json.loads(args.recipe.read_text()))
    table, proof = build(recipe, args.size, args.out)
    if args.action == 'preview':
        label = 'FL-inspired v0' if recipe['id'] == 'fl-inspired-v0' else recipe.get('name', recipe['id'])
        proof['preview'] = preview(args.input, table, args.size, args.out, args.assume_srgb, label)
    (args.out / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'out': str(args.out.resolve()), 'cube_size': args.size,
                      'camera_integration': False, 'flash_ready': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
