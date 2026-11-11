#!/usr/bin/env python3
"""Verify eight adjustment controls and rendered pixels in the ARM UI model."""
import argparse
import importlib.util
import json
from pathlib import Path
import re
import socket

from PIL import Image

spec = importlib.util.spec_from_file_location('verify_ui', Path(__file__).with_name('verify-ui.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
DEFAULT = [0,0,0,0,0,3,3,0]
MINIMUM = [-9,-9,-9,0,-9,0,1,0]
MAXIMUM = [9,9,9,9,9,9,5,9]


def values(state):
    return list(map(int, re.search(r'ADJ=([^ ]+)', state)[1].split(',')))


def verify(g, out):
    g.expect('FL_LUT_SELFTEST_PASS 512')
    g.expect('FL_ADJUST_SELFTEST_PASS')
    g.expect('menu 1/1 File Format')
    def open_from_shoot():
        g.press('f', 'fn 1')
        g.press('down', 'fn 7')
        for slot in range(8,13):g.press('right', f'fn {slot}')
        return g.press('ret', 'option Creative Look ')
    g.press('m', 'shoot ')
    open_from_shoot()
    g.press('down', 'option Creative Look 1 ')
    state = g.press('ret', 'fl-preview ')
    assert values(state)==DEFAULT
    g.shot(out, 'adjust-default.png')
    for i in range(8):
        if i:g.press('right', 'fl-preview ')
        state=g.press('c', 'fl-preview ')
        assert f'FOCUS={i}' in state and values(state)==DEFAULT
        for _ in range(20):state=g.press('up', 'fl-preview ')
        assert values(state)[i]==MAXIMUM[i],state
        for _ in range(20):state=g.press('down', 'fl-preview ')
        assert values(state)[i]==MINIMUM[i],state
        assert all(v==DEFAULT[j] for j,v in enumerate(values(state)) if j!=i)
        g.press('c', 'fl-preview ')
        if i==6:
            g.press('left', 'fl-preview ');g.press('up', 'fl-preview ');g.press('right', 'fl-preview ')
        g.shot(out, f'item-{i}-before.png')
        g.press('up', 'fl-preview ')
        g.shot(out, f'item-{i}-after.png')
        with Image.open(out/f'item-{i}-before.png') as before, Image.open(out/f'item-{i}-after.png') as after:
            assert before.crop((19,101,306,243)).tobytes()==after.crop((19,101,306,243)).tobytes(),f'left reference changed: {i}'
            assert before.crop((334,101,621,243)).tobytes()!=after.crop((334,101,621,243)).tobytes(),f'no rendered effect: {i}'
    g.press('c', 'fl-preview ')
    g.press('right', 'fl-preview ')
    state=g.press('up', 'fl-preview ')
    assert values(state)==[1,0,0,0,0,3,3,0]
    assert 'FL=1' in g.press('ret','fn 12')
    assert values(g.press('ret','option Creative Look 1 '))==[1,0,0,0,0,3,3,0]
    state=g.press('ret','fl-preview ')
    assert values(state)[0]==1
    g.press('down','fl-preview ')
    assert values(g.press('esc','option Creative Look 1 '))[0]==1
    g.press('ret','fl-preview ')
    g.press('c','fl-preview ')
    assert values(g.press('esc','option Creative Look 1 '))[0]==1, 'reset leaked despite cancel'
    g.press('ret','fl-preview ')
    g.press('c','fl-preview ')
    g.press('ret','fn 12')
    assert values(g.press('ret','option Creative Look 1 '))==DEFAULT
    g.press('esc','fn 12');g.press('esc','shoot ')
    g.press('r','shoot ')
    open_from_shoot()
    g.press('ret','fl-preview ')
    for _ in range(6):g.press('right','fl-preview ')
    state=g.press('up','fl-preview ')
    assert values(state)[6]==3,'movie sharpness range must be locked'
    g.shot(out,'adjust-movie-range.png')
    g.press('esc','option Creative Look 1 ');g.press('esc','fn 12');g.press('esc','shoot ')
    g.press('r','shoot ')
    open_from_shoot();g.press('ret','fl-preview ')
    g.shot(out,'adjust-final.png')
    (out/'adjust-proof.json').write_text(json.dumps({
        'all_eight_ranges_clamped':True,'all_eight_have_rendered_effect':True,
        'reference_image_unchanged':True,'apply_cancel_reset_reopen':True,
        'movie_sharpness_range_locked':True,'camera_integration':False,'flash_ready':False},indent=2)+'\n')
    print('PASS: all 8 bounds, rendered effects, unchanged reference; apply/cancel/reset/reopen; movie range lock.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('socket',type=Path);parser.add_argument('serial',type=Path);parser.add_argument('shots',type=Path)
    args=parser.parse_args();args.shots.mkdir(parents=True,exist_ok=True)
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.settimeout(5);sock.connect(str(args.socket))
        with sock.makefile('rwb') as stream:
            verify(module.Guest(stream,args.serial),args.shots.resolve())


if __name__=='__main__':main()
