#!/usr/bin/env python3
"""Fault-test the filesystem installer and cross-link its unbound ARM core."""
import hashlib
import json
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'.lab/native-install-test'


def main():
    OUT.mkdir(parents=True,exist_ok=True);(OUT/'proof.json').unlink(missing_ok=True)
    sources=['research/native_install'+s for s in ('.c','.h','_linux.c','_harness.c','_test.py')]+['payloads/sha256.h']
    subprocess.run(['cc','-std=c11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-fsanitize=address,undefined',str(ROOT/'research/native_install.c'),str(ROOT/'research/native_install_harness.c'),'-o',str(OUT/'test')],check=True)
    run=subprocess.run([str(OUT/'test')],check=True,text=True,capture_output=True);log=run.stdout+run.stderr
    (OUT/'host.log').write_text(log);print(log,end='')
    if 'NATIVE_INSTALL_TESTS_PASSED' not in log or 'FAIL' in log:raise ValueError('Installer fault test failed')
    for name in ('native_install','native_install_linux'):
        subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-fPIC','-ffreestanding','-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables','-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-c',str(ROOT/'research'/f'{name}.c'),'-o',str(OUT/f'{name}.o')],check=True)
    subprocess.run(['arm-none-eabi-ld','-shared','--no-undefined','-z','noexecstack',str(OUT/'native_install.o'),str(OUT/'native_install_linux.o'),'-o',str(OUT/'installer-unbound.so')],check=True)
    h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    proof={'source_sha256':{n:h(ROOT/n) for n in sources},'host_log_sha256':h(OUT/'host.log'),
           'arm_core_sha256':h(OUT/'installer-unbound.so'),'flash_ready':False,'bound_bundle':False,
           'scope':'ASan/UBSan host syscall-shim fault injection plus no-undefined ARM ELF link; no live remount or file writes'}
    (OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')


if __name__=='__main__':main()
