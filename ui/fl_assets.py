"""Generate a fixed-point cube and independent reference vectors for ARM UI."""
import hashlib
import json
from pathlib import Path
import random
import struct

from fl_look import DEFAULT_RECIPE, cube_table, interpolate, validate


def generate(out):
    recipe = validate(json.loads(DEFAULT_RECIPE.read_text()))
    size = 33
    cube = cube_table(recipe, size)
    values = [round(v * 65535) for row in cube for v in row]
    header = ['#define FL_LUT_SIZE 33\nstatic const uint16_t fl_cube[] = {\n']
    header += [','.join(map(str, values[i:i+24])) + ',\n' for i in range(0, len(values), 24)]
    header.append('};\nstatic const uint32_t fl_vectors[][2] = {\n')
    rng = random.Random(20261111)
    inputs = [(r,g,b) for b in (0,255) for g in (0,255) for r in (0,255)]
    inputs += [(x,x,x) for x in range(256)]
    inputs += [tuple(rng.randrange(256) for _ in range(3)) for _ in range(512-len(inputs))]
    def pack(rgb):
        return rgb[0] << 16 | rgb[1] << 8 | rgb[2]
    for rgb in inputs:
        expected = interpolate(tuple(v/255 for v in rgb), cube, size)
        result = tuple(round(v*255) for v in expected)
        header.append(f'{{0x{pack(rgb):06x},0x{pack(result):06x}}},\n')
    header.append('};\n')
    (out / 'fl_data.h').write_text(''.join(header))
    sources = ['ui/build.py', 'ui/fl_assets.py', 'ui/fl_lut.h', 'ui/fl_adjust.h', 'ui/ui.c', 'ui/zh-cn.json',
               'research/fl_look.py', 'recipes/fl-inspired-v0.json']
    root = Path(__file__).resolve().parents[1]
    proof = {'cube_size': size, 'channels': 'RGB u16, R fastest', 'input_output': 'sRGB',
             'cube_sha256': hashlib.sha256(struct.pack(f'<{len(values)}H', *values)).hexdigest(),
             'source_sha256': {p: hashlib.sha256((root/p).read_bytes()).hexdigest() for p in sources},
             'arm_reference_vectors': len(inputs), 'reference_tolerance_u8': 1,
             'scope': 'Independent ARM UI model; synthetic image processed by a real RGB LUT',
             'camera_integration': False, 'flash_ready': False}
    (out / 'fl-build.json').write_text(json.dumps(proof, indent=2) + '\n')
