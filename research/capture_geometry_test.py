#!/usr/bin/env python3
"""Exercise the bounded three-shot metadata recorder under sanitizers."""
import json
import subprocess
import argparse
from kernel_probe import ROOT, sha

p=argparse.ArgumentParser();p.add_argument('--layout',action='store_true');a=p.parse_args()
out=ROOT/('.lab/capture-layout-record' if a.layout else '.lab/capture-geometry-record')
out.mkdir(exist_ok=True)
(out/'proof.json').unlink(missing_ok=True)
sources=['research/capture_geometry_test.py','research/capture_geometry_harness.c',
         'research/kernel_probe/capture_geometry_record.h',
         'research/kernel_probe/capture_geometry.c']
if a.layout:sources+=['research/kernel_probe/capture_layout_record.h','research/kernel_probe/capture_layout.c']
subprocess.run(['clang','-std=c11','-O1','-g','-fsanitize=address,undefined',
                '-Wall','-Wextra','-Werror',*(['-DTEST_LAYOUT=1'] if a.layout else []),
                str(ROOT/sources[1]),'-o',str(out/'test')],check=True)
r=subprocess.run([str(out/'test')],capture_output=True,check=True)
(out/'log.txt').write_bytes(r.stdout+r.stderr)
(out/'proof.json').write_text(json.dumps(dict(passed=True,
    source_sha256={s:sha((ROOT/s).read_bytes()) for s in sources},
    log=r.stdout.decode(),camera_run=False,pixel_write=False),indent=2)+'\n')
print(r.stdout.decode(),end='')
