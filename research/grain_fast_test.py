#!/usr/bin/env python3
"""Byte-compare grain fast path to original kernel under host sanitizers; no USB."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/grain-fast'
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    flags=['-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
           '-fsanitize=address,undefined','-fno-omit-frame-pointer','-I'+str(ROOT/'payloads')]
    names=['reference_radius','workspace','validate','apply','dispatch']
    rename=['-Da7_film_frame_'+n+'=a7_film_frame_reference_'+n for n in names]
    # The public reference name for apply is intentionally simple.
    subprocess.run(['clang',*flags,'-DA7_FILM_REFERENCE_GRAIN',*rename,'-c',
                    str(ROOT/'payloads/a7-film-frame.c'),'-o',str(OUT/'reference.o')],check=True)
    subprocess.run(['clang',*flags,str(ROOT/'research/grain_fast_harness.c'),
                    str(ROOT/'payloads/a7-film-frame.c'),str(OUT/'reference.o'),'-o',str(OUT/'test')],check=True)
    result=subprocess.run([str(OUT/'test')],check=True,capture_output=True,timeout=60)
    print(result.stdout.decode(),end='')
    files=['payloads/a7-film-frame.c','payloads/a7-film-frame.h','research/grain_fast_harness.c','research/grain_fast_test.py']
    (OUT/'proof.json').write_text(json.dumps(dict(
        source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in files},
        result=result.stdout.decode(),camera_written=False,native_frame_bound=False,flash_ready=False),indent=2)+'\n')
if __name__=='__main__':main()
