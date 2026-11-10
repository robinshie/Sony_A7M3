#!/usr/bin/env python3
"""Verify the optional recipe UI, cancellation and parameter state in QEMU."""
import argparse
import importlib.util
from pathlib import Path
import socket

spec = importlib.util.spec_from_file_location('verify_ui', Path(__file__).with_name('verify-ui.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def verify(g, shots):
    g.expect('menu 1/1 File Format')
    g.press('m', 'shoot')
    g.press('f', 'fn 1')
    g.press('down', 'fn 7')
    for slot in range(8,12):
        g.press('right', f'fn {slot}')
    g.press('ret', 'option Creative Style 0')
    g.press('up', 'option Creative Style 13')
    g.shot(shots, 'creative-list.png')
    g.press('ret', 'preset ')
    g.shot(shots, 'retro-wardrobe-zh.png')
    assert g.press('l', 'preset ').endswith('[en]')
    g.shot(shots, 'retro-wardrobe-en.png')
    g.press('l', 'preset ')
    g.press('esc', 'option Creative Style 13')
    g.press('esc', 'fn 11')
    before = g.press('ret', 'option Creative Style 0')
    assert 'C=0 S=0 H=0 WB=Auto PP=Off FX=Off' in before, before
    g.press('up', 'option Creative Style 13')
    g.press('ret', 'preset ')
    g.press('ret', 'fn 11')
    applied = g.press('ret', 'option Creative Style 13')
    assert 'C=1 S=-1 H=-1 WB=Daylight PP=Off FX=Off' in applied, applied
    assert 'BASE=Neutral' in applied, applied
    g.shot(shots, 'creative-applied.png')
    # Keep all original entries selectable; choosing one clears prototype tuning.
    for index in range(13):
        g.press('down', f'option Creative Style {index}')
        g.press('ret', 'fn 11')
        state = g.press('ret', f'option Creative Style {index}')
        assert 'C=0 S=0 H=0' in state, state
    g.press('esc', 'fn 11')
    g.press('right', 'fn 12')
    g.press('ret', 'option Picture Effect 0')
    g.press('down', 'option Picture Effect 1')
    g.press('ret', 'fn 12')
    g.press('left', 'fn 11')
    reset = g.press('ret', 'option Creative Style 0')
    assert 'C=0 S=0 H=0' in reset and 'FX=Toy Camera' in reset, reset
    g.press('up', 'option Creative Style 13')
    g.press('ret', 'preset ')
    g.press('ret', 'fn 11')
    reapplied = g.press('ret', 'option Creative Style 13')
    assert 'C=1 S=-1 H=-1 WB=Daylight PP=Off FX=Off' in reapplied, reapplied
    assert 'BASE=Neutral' in reapplied, reapplied
    g.press('ret', 'preset ')
    print('PASS: cancel preserves state; apply sets Neutral recipe tuning and WB/PP/effect;')
    print('13 original styles retained; effect conflict clears tuning; reapply restores recipe; zh/en screens captured.')
    print('Scope: independent UI state only. No native firmware integration or JPEG processing.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('socket', type=Path)
    p.add_argument('serial', type=Path)
    p.add_argument('shots', type=Path)
    a = p.parse_args()
    a.shots.mkdir(parents=True,exist_ok=True)
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as s:
        s.settimeout(5)
        s.connect(str(a.socket))
        with s.makefile('rwb') as stream:
            verify(module.Guest(stream,a.serial),a.shots.resolve())


if __name__ == '__main__':
    main()
