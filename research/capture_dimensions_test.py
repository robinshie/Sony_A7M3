#!/usr/bin/env python3
"""Synthetic full-size bounds and grain/halo/vignette tests under ASan/UBSan."""
import json
import subprocess
from kernel_probe import ROOT,sha

out=ROOT/'.lab/capture-dimensions-test';out.mkdir(exist_ok=True)
(out/'proof.json').unlink(missing_ok=True)
sources=['research/capture_dimensions_test.py','research/capture_dimensions_harness.c',
         'payloads/a7-capture-geometry.h','payloads/a7-film-frame.c','payloads/a7-film-frame.h',
         'payloads/a7-film-vignette.c','payloads/a7-film-vignette.h']
subprocess.run(['clang','-std=c11','-O2','-g','-fsanitize=address,undefined',
    '-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I'+str(ROOT/'payloads'),
    *[str(ROOT/sources[i]) for i in (1,3,5)],'-o',str(out/'test')],check=True)
r=subprocess.run([str(out/'test')],capture_output=True,timeout=180)
(out/'log.txt').write_bytes(r.stdout+r.stderr)
print((r.stdout+r.stderr).decode(),end='')
if r.returncode or b'CAPTURE_DIMENSIONS_PASSED' not in r.stdout:
    raise ValueError('Dimensions/processing tests failed')
(out/'proof.json').write_text(json.dumps(dict(passed=True,
    source_sha256={s:sha((ROOT/s).read_bytes()) for s in sources},log=r.stdout.decode(),
    camera_run=False,native_adapter_connected=False,flash_ready=False,
    scope='Synthetic UYVY geometry, padding, all three spatial stages; no camera M/S assertion'),indent=2)+'\n')
