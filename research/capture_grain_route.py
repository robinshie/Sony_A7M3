#!/usr/bin/env python3
"""Pin the 4.04 SoftFocus -> JPEG resource route; no camera I/O or patches.

These are AV-CAM file offsets. The native processing service is SA, not a
Linux callback in a7fl.so. Address conversion alone grants no writable lease.
"""
import argparse
import json
import struct
from pathlib import Path

from yc_route_audit import AVCAM_SHA, call, instruction, log_reference, require, sha

ROOT = Path(__file__).resolve().parents[1]


class Flat:
    def __init__(self, data):
        self.data = data

    def read(self, at, size):
        require(0 <= at <= len(self.data) - size, 'AV-CAM range outside file')
        return self.data[at:at + size]

    def word(self, at):
        return struct.unpack('<I', self.read(at, 4))[0]


def audit(path):
    e = Flat(path.read_bytes())
    require(sha(e.data) == AVCAM_SHA, 'Requires pinned ILCE-7M3 4.04 AV-CAM')
    calls = [call(e, a, b, 'bl') for a, b in (
        (0x34f668, 0x54cb2c), (0x34f6ca, 0x54ccd4),
        (0x34f766, 0x54cbf8), (0x34f796, 0x326ef4),
        (0x54cd1c, 0x54a928), (0x54cd3e, 0x54a928), (0x54cd60, 0x54a928),
        (0x54a93a, 0x3a5520), (0x54a956, 0x646ddc),
        (0x54cdfe, 0x7bf0a2), (0x54ce4e, 0x7d4d6a),
        (0x7d4d9a, 0x54a7a4), (0x54a7ba, 0x54a16c), (0x54a7d6, 0x54a700),
        (0x54a1b8, 0x7d4bda), (0x54a1be, 0x7bde46), (0x54a73c, 0x54a63c),
        (0x340258, 0x35cfc8), (0x3402b2, 0x33fff4),
    )]
    pins = [instruction(e, a, op, args) for a, op, args in (
        (0x34f638, 'ldrh.w', 'r2, [r3, #0xf6]'),
        (0x34f63c, 'ldrh.w', 'r3, [r3, #0xf8]'),
        (0x34f64c, 'ldrh', 'r3, [r3, #0x16]'),
        (0x34f70e, 'ldrb.w', 'r2, [sp, #0xd6]'),
        (0x34f712, 'cmp', 'r2, #1'),
        (0x34f794, 'movs', 'r1, #8'),
        (0x326ff6, 'ldrh.w', 'r4, [r2, #0xf8]'),
        (0x326ffa, 'ldrh.w', 'r0, [r2, #0xf6]'),
        (0x327000, 'strh.w', 'r4, [r2, #0xf6]'),
        (0x327006, 'strh.w', 'r0, [r2, #0xf8]'),
        (0x54cd2e, 'tst.w', 'r0, #0x7f'),
        (0x54cd50, 'tst.w', 'r0, #0x7f'),
        (0x54cd72, 'tst.w', 'r0, #0x7f'),
        (0x54cdb0, 'tst.w', 'r3, #0xf'),
        (0x54cdc0, 'tst.w', 'r3, #7'),
        (0x54cdd0, 'tst.w', 'r3, #0xf'),
        (0x54ce4c, 'movs', 'r2, #0x18'),
        (0x7d4c0e, 'movs', 'r3, #0x41'),
        (0x7bde48, 'movs', 'r2, #0x1c'),
        (0x7bde4a, 'movw', 'r0, #0x101'),
        (0x54a736, 'movs', 'r1, #0x41'),
        (0x54a94e, 'cmp', 'r2, #1'),
        (0x646dec, 'cmp', 'r2, #3'),
        (0x646e16, 'b.w', '#0x1dc34'),
        (0x1dc40, 'ldr.w', 'r3, [r3, #0x304]'),
        (0x1dc44, 'blx', 'r3'),
    )]
    logs = [log_reference(e, a, text) for a, text in (
        (0x54a18e, 'ExecuteSendCalcStartMSG_MULTI'),
        (0x54a71e, 'ExecuteRcvStartDoneMSG_MULTI'),
        (0x54cd28, "GetAddr error `src_addr'"),
        (0x54cd4a, "GetAddr error `dst_addr'"),
        (0x54cd6c, "GetAddr error `work_addr'"),
        (0x54cdb8, 'SA param width alignment error\n'),
        (0x54cdc8, 'SA param height alignment error\n'),
        (0x54cdd8, 'SA param line_ofs alignment error\n'),
    )]
    return dict(avcam_sha256=AVCAM_SHA, calls=calls, instructions=pins, logs=logs,
                source_context_offset='0x62f6', destination_context_offset='0x62f8',
                workspace_context_offset='0x6316', swap_selector=8,
                sa_function=24, start_done_command=65, send_endpoint=257,
                address_alignment=128, width_alignment=16,
                height_alignment=8, line_offset_alignment=16,
                scope='Static native instructions/logs; no sensor, encoder, or pixel processing executed',
                linux_callable_pixel_hook_verified=False,
                pixel_layout_verified=False, writable_ownership_verified=False,
                cache_sync_verified=False, camera_written=False, flash_ready=False,
                source_sha256={p: sha((ROOT / p).read_bytes()) for p in
                               ('research/capture_grain_route.py', 'research/yc_route_audit.py')})


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--avcam', required=True, type=Path)
    cli.add_argument('--out', type=Path, default=ROOT / '.lab/capture-grain-route')
    a = cli.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    proof = a.out / 'proof.json'
    proof.unlink(missing_ok=True)
    result = audit(a.avcam)
    proof.write_text(json.dumps(result, indent=2) + '\n')
    print('CAPTURE_GRAIN_ROUTE_PASSED', len(result['calls']), 'calls,',
          len(result['instructions']), 'instructions,', len(result['logs']), 'log identities')
    print('EVIDENCE', proof)


if __name__ == '__main__':
    main()
