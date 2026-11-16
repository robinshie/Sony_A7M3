#!/usr/bin/env python3
"""Preview the built look tables on one synthetic RGB color chart."""
import argparse
import itertools
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
LABELS = ('原厂 4.04 · 创意外观关', 'FL · 实验版', 'FL2', 'FL3 · 徕卡胶片',
          'FL4 · 经典负片', 'FL5 · 经典纪实', 'FL6 · 自然人像')
SAMPLES = (
    (19, 19, 19), (46, 46, 46), (84, 84, 84), (128, 128, 128),
    (171, 171, 171), (208, 208, 208), (228, 228, 228), (246, 246, 246),
    (63, 38, 34), (123, 81, 65), (170, 109, 85), (217, 159, 130),
    (239, 186, 160), (239, 214, 184), (218, 208, 180), (240, 232, 210),
    (147, 41, 51), (220, 96, 56), (233, 161, 49), (204, 185, 75),
    (118, 133, 56), (52, 107, 61), (42, 133, 117), (61, 175, 162),
    (34, 52, 84), (76, 132, 190), (151, 188, 218), (94, 86, 142),
    (158, 103, 152), (188, 121, 147), (106, 77, 59), (232, 198, 89),
)
EXTRACT = r'''
#include <stdio.h>
#include <string.h>
#include "a7-fl-module-data.h"
#include "a7-fl-cinema.h"
#include "a7-fl-leica.h"
#include "a7-fl-classic-looks.h"
#include "a7-fl-fivepoint-preview.h"
int main(void) {
    uint8_t base[1280], table[1280];
    if (fwrite(a7_pkg_original[0], 1, sizeof table, stdout) != sizeof table) return 1;
    for (int i=1; i<=6; ++i) {
        int v[10],curve[5];
        for(int j=0;j<10;++j) if(scanf("%d",&v[j])!=1) return 4;
        const A7FLColorParams p={v[0],v[1],v[2],v[3],v[4]};
        for(int j=0;j<5;++j) curve[j]=v[5+j];
        if (i==1) memcpy(base,a7_pkg_base,sizeof base);
        else {
            int rc;
            if (i==2) rc=a7_cinema_base(a7_pkg_original[0],a7_pkg_expand,a7_pkg_compress,base);
            else if (i==3) rc=a7_leica_base(a7_pkg_original[0],a7_pkg_expand,a7_pkg_compress,base);
            else rc=a7_classic_base(i,a7_pkg_original[0],a7_pkg_expand,a7_pkg_compress,base);
            if (rc) return 2;
        }
        if (a7_fl_fivepoint_preview(base,a7_pkg_expand,a7_pkg_compress,&p,curve,table) ||
            fwrite(table,1,sizeof table,stdout) != sizeof table) return 3;
    }
    /* Off stores the adjusted FL base CRC without applying its five-point curve. */
    int v[5];
    for(int j=0;j<5;++j) if(scanf("%d",&v[j])!=1) return 4;
    const A7FLColorParams off={v[0],v[1],v[2],v[3],v[4]};
    if(a7_fl_adjust_lut(a7_pkg_base,1280,a7_pkg_expand,a7_pkg_compress,&off,table,1280) ||
       fwrite(table,1,sizeof table,stdout)!=sizeof table) return 5;
    return 0;
}
'''


def extract_tables(build, banks=None, include_off_crc=False):
    banks = [[0]*16 for _ in range(6)] if banks is None else banks
    values = [v for bank in banks for v in (*bank[:5], *bank[10:15])] + banks[0][:5]
    with tempfile.TemporaryDirectory() as tmp:
        source, exe = Path(tmp) / 'extract.c', Path(tmp) / 'extract'
        source.write_text(EXTRACT)
        flags = ('SIX_LOOKS', 'CAPTURE_VIGNETTE', 'CAPTURE_HALATION', 'FILM_CONTROLS', 'LEICA_LOOK')
        subprocess.run(['cc', '-O2', '-I', str(build), '-I', str(ROOT/'payloads'),
                        *('-DA7_FL_'+flag for flag in flags), str(source),
                        str(ROOT/'payloads/a7-fl-fivepoint.c'), '-o', str(exe)], check=True)
        data = subprocess.check_output([str(exe)], input=' '.join(map(str, values)).encode())
    if len(data) != 8*1280:
        raise ValueError('Expected original, six generated preview tables and Off CRC input')
    if not include_off_crc:
        data = data[:7*1280]
    return [data[n:n+1280] for n in range(0, len(data), 1280)]


def sample(rgb, table, codec):
    r, g, b = (v/255 for v in rgb)
    y = .2126*r + .7152*g + .0722*b
    cb, cr = (b-y)/1.8556, (r-y)/1.5748
    xyz = (y*4, 4+codec.compress(round(cb*1024))/32, 4+codec.compress(round(cr*1024))/32)
    lo = [min(int(v), size-2) for v, size in zip(xyz, (5, 9, 9))]
    frac = [v-cell for v, cell in zip(xyz, lo)]
    out = [0., 0., 0.]
    for vertex in itertools.product((0, 1), repeat=3):
        a, b, c = (offset+start for offset, start in zip(vertex, lo))
        i = a*81+b*9+c
        direct = [table[i+p*405] for p in range(3)]
        signed = [n if n < 128 else n-256 for n in direct]
        values = ((a*64+signed[0])/256,
                  codec.expand((b-4)*32+signed[1]*3//4)/1024,
                  codec.expand((c-4)*32+signed[2]*3//4)/1024)
        weight = 1.
        for offset, f in zip(vertex, frac):
            weight *= f if offset else 1-f
        for p, v in enumerate(values):
            out[p] += weight*v
    y, cb, cr = out
    return tuple(round(max(0., min(1., v))*255) for v in
                 (y+1.5748*cr, y-.187324*cb-.468124*cr, y+1.8556*cb))


def render(output, tables, codec, font, caption='相同色卡、默认调节值｜预览色表模拟，非真机 JPEG'):
    from PIL import Image, ImageDraw, ImageFont
    large, title, small = (ImageFont.truetype(str(font), n) for n in (29, 20, 16))
    image = Image.new('RGB', (1152, 470), '#171a1f')
    draw = ImageDraw.Draw(image)
    draw.text((24, 15), 'Sony A7 III｜原厂与六套创意外观', font=large, fill='#ffffff')
    draw.text((24, 58), caption, font=small, fill='#c1c8d1')
    for n, (label, table) in enumerate(zip((*LABELS, '输入色卡'), (*tables, None))):
        x, y = 24+280*(n % 4), 100+181*(n//4)
        draw.text((x, y), label, font=title, fill='#f4f5f7')
        draw.rounded_rectangle((x, y+31, x+263, y+160), radius=8, fill='#242830')
        for j, rgb in enumerate(SAMPLES):
            color = sample(rgb, table, codec) if table is not None else rgb
            u, v = x+10+31*(j % 8), y+40+29*(j//8)
            draw.rectangle((u, v, u+25, v+23), fill=color)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def main():
    from native_fl import Codec
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--bundle', type=Path, default=ROOT/'.lab/native-fl-01')
    p.add_argument('--font', type=Path, default=Path('/System/Library/Fonts/Hiragino Sans GB.ttc'))
    a = p.parse_args()
    codec = Codec((a.bundle/'codec.bin').read_bytes())
    render(a.output, extract_tables(a.build.resolve()), codec, a.font)


if __name__ == '__main__':
    main()
