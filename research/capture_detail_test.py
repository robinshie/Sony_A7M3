#!/usr/bin/env python3
"""Host metadata bounds tests; no camera calls or pixel writes."""
import json,subprocess
from kernel_probe import ROOT,sha
out=ROOT/'.lab/capture-detail-record';out.mkdir(exist_ok=True)
(out/'proof.json').unlink(missing_ok=True)
sources=['research/capture_detail_test.py','research/capture_detail_harness.c','research/kernel_probe/capture_detail_record.h']
subprocess.run(['clang','-std=c11','-O1','-g','-fsanitize=address,undefined','-Wall','-Wextra','-Werror',str(ROOT/sources[1]),'-o',str(out/'test')],check=True)
r=subprocess.run([str(out/'test')],capture_output=True,check=True)
print(r.stdout.decode(),end='');(out/'log.txt').write_bytes(r.stdout+r.stderr)
(out/'proof.json').write_text(json.dumps(dict(passed=True,source_sha256={s:sha((ROOT/s).read_bytes()) for s in sources},log=r.stdout.decode(),camera_run=False,pixel_write=False),indent=2)+'\n')
