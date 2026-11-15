#!/usr/bin/env python3
"""Exercise read failures, handle generation, extent bounds and state changes."""
import argparse,json,subprocess
from pathlib import Path
from kernel_probe import ROOT,sha
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--bundle',required=True,type=Path)
a=p.parse_args()
out=ROOT/'.lab/capture-early-record';out.mkdir(exist_ok=True)
(out/'proof.json').unlink(missing_ok=True)
sources=['research/capture_early_test.py','research/capture_early_harness.c','research/kernel_probe/capture_early_record.h']
subprocess.run(['clang','-std=c11','-O1','-g','-fsanitize=address,undefined','-Wall','-Wextra','-Werror',
    '-I'+str(a.bundle),str(ROOT/sources[1]),'-o',str(out/'test')],check=True)
r=subprocess.run([str(out/'test')],capture_output=True,check=True)
print(r.stdout.decode(),end='');(out/'log.txt').write_bytes(r.stdout+r.stderr)
(out/'proof.json').write_text(json.dumps(dict(passed=True,source_sha256={s:sha((ROOT/s).read_bytes()) for s in sources},
    pin_header_sha256=sha((a.bundle/'dmm-pins.h').read_bytes()),log=r.stdout.decode(),
    camera_run=False,pixel_write=False),indent=2)+'\n')
