#!/usr/bin/env python3
"""Exercise FL selection/cancel, real ARM pixel output and both menu paths."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys

spec = importlib.util.spec_from_file_location('verify_ui', Path(__file__).with_name('verify-ui.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research'))
from fl_look import DEFAULT_RECIPE, cube_table, interpolate, validate


def verify(g, shots):
    g.expect('FL_LUT_SELFTEST_PASS 512')
    g.expect('FL_ADJUST_SELFTEST_PASS')
    g.expect('menu 1/1 File Format FL=0')
    g.press('m', 'shoot ')
    g.shot(shots, 'standard.png')
    g.press('f', 'fn 1')
    g.press('down', 'fn 7')
    for slot in range(8, 12):
        g.press('right', f'fn {slot}')
    # Creative Style retains its 13 original options plus RW; FL is absent.
    g.press('ret', 'option Creative Style 0 ')
    g.press('up', 'option Creative Style 13 ')
    g.shot(shots, 'creative-style-list.png')
    g.press('esc', 'fn 11')
    g.press('right', 'fn 12')
    g.press('ret', 'option Creative Look 0 ')
    g.press('up', 'option Creative Look 1 ')
    g.shot(shots, 'fl-list.png')
    assert 'FL=0' in g.press('ret', 'fl-preview ')
    g.shot(shots, 'fl-preview.png')
    g.press('l', 'fl-preview ')
    g.shot(shots, 'fl-preview-en.png')
    g.press('l', 'fl-preview ')
    g.press('esc', 'option Creative Look 1 ')
    g.press('esc', 'fn 12')
    assert 'FL=0' in g.press('ret', 'option Creative Look 0 ')
    g.press('up', 'option Creative Look 1 ')
    g.press('ret', 'fl-preview ')
    assert 'FL=1 LUT=33' in g.press('ret', 'fn 12')
    g.shot(shots, 'fl-fn.png')
    assert 'FL=1 LUT=33' in g.press('ret', 'option Creative Look 1 ')
    g.press('esc', 'fn 12')
    g.press('esc', 'shoot ')
    g.shot(shots, 'fl-shoot.png')
    # Cross-check actual QEMU framebuffer values against independent desktop
    # interpolation, not a pre-rendered host preview.
    from PIL import Image
    table = cube_table(validate(json.loads(DEFAULT_RECIPE.read_text())), 33)
    swatches = [0xd6d6d6,0xc6b83a,0x4aadb2,0x569146,0xab609a,0xbd5d4a,0x415b93]
    with Image.open(shots/'standard.png') as before, Image.open(shots/'fl-shoot.png') as after:
        assert before.size == after.size == (640,480)
        for i, color in enumerate(swatches):
            rgb = tuple((color>>s)&255 for s in (16,8,0))
            point = (640*(2*i+1)//14, 200)
            assert before.convert('RGB').getpixel(point) == rgb
            expected = interpolate(tuple(v/255 for v in rgb), table, 33)
            actual = after.convert('RGB').getpixel(point)
            assert all(abs(a-round(b*255)) <= 1 for a,b in zip(actual,expected)), (point,actual,expected)
    # MENU: Style and Look are sibling entries. Style changes disable Look;
    # turning Look off restores the previous style and its stored parameters.
    g.press('1', 'menu 1/1 ')
    for page in range(2, 13):
        g.press('pgdn', f'menu 1/{page} ')
    for _ in range(3):
        g.press('down', 'menu 1/12 ')
    g.shot(shots, 'fl-menu.png')
    g.press('ret', 'option Creative Style 0 ')
    g.press('up', 'option Creative Style 13 ')
    g.press('ret', 'preset ')
    assert 'FL=0' in g.press('ret', 'menu 1/12 Creative Style ')
    assert 'C=1 S=-1 H=-1' in g.press('ret', 'option Creative Style 13 ')
    g.press('esc', 'menu 1/12 Creative Style ')
    g.press('down', 'menu 1/12 Creative Look ')
    g.press('ret', 'option Creative Look 0 ')
    g.press('down', 'option Creative Look 1 ')
    g.press('ret', 'fl-preview ')
    assert 'FL=1' in g.press('ret', 'menu 1/12 Creative Look ')
    g.press('up', 'menu 1/12 Creative Style ')
    state = g.press('ret', 'option Creative Style 13 ')
    assert 'C=1 S=-1 H=-1' in state and 'FL=1' in state
    g.press('esc', 'menu 1/12 Creative Style ')
    g.press('down', 'menu 1/12 Creative Look ')
    g.press('ret', 'option Creative Look 1 ')
    g.press('up', 'option Creative Look 0 ')
    assert 'FL=0' in g.press('ret', 'menu 1/12 Creative Look ')
    g.press('up', 'menu 1/12 Creative Style ')
    assert 'C=1 S=-1 H=-1' in g.press('ret', 'option Creative Style 13 ')
    g.press('down', 'option Creative Style 0 ')
    assert 'FL=0' in g.press('ret', 'menu 1/12 Creative Style ')
    g.press('down', 'menu 1/12 Creative Look ')
    g.press('ret', 'option Creative Look 0 ')
    g.press('down', 'option Creative Look 1 ')
    g.press('ret', 'fl-preview ')
    g.press('ret', 'menu 1/12 Creative Look ')
    # The extra row did not remove Picture Profile: it moved to the next page.
    g.press('pgdn', 'menu 1/13 Picture Profile ')
    g.press('ret', 'option Picture Profile 0 ')
    g.press('down', 'option Picture Profile 1 ')
    assert 'FL=0' in g.press('ret', 'menu 1/13 Picture Profile ')
    g.press('pgup', 'menu 1/12 White Balance ')
    for _ in range(4):
        g.press('down', 'menu 1/12 ')
    g.shot(shots, 'fl-final.png')
    proof = {'arm_cube_vectors': 512, 'framebuffer_color_checks': 7,
             'cancel_preserves_selection': True, 'fn_and_menu_paths': True,
             'reopen_position': True, 'standard_and_rw_switch': True,
             'creative_look_is_sibling': True, 'style_parameters_preserved': True,
             'picture_profile_accessible_and_conflict_clears_look': True,
             'camera_integration': False, 'flash_ready': False,
             'screenshots_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(shots.glob('*.png'))}}
    (shots / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    print('PASS: Creative Look is a sibling of Creative Style; FL excluded from style list; Fn/MENU; cancel/apply/reopen; RW preserved; PP conflict.')
    print('PASS: 512 ARM RGB vectors; 7 live framebuffer colors; zh/en.')
    print('Independent QEMU model only; no Sony ISP or camera firmware integration.')


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('socket', type=Path)
    cli.add_argument('serial', type=Path)
    cli.add_argument('shots', type=Path)
    args = cli.parse_args()
    args.shots.mkdir(parents=True, exist_ok=True)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(5)
        sock.connect(str(args.socket))
        with sock.makefile('rwb') as stream:
            verify(module.Guest(stream, args.serial), args.shots.resolve())


if __name__ == '__main__':
    main()
