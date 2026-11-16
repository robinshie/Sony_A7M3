#!/usr/bin/env python3
"""Bind the tested ARM file stager to stock 4.04. Build only; no USB runner.

This stages module/locales. It cannot activate the full installation: stock
view, CautionConfig and image-resource activation are a separate unresolved step.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
from local import file_sha
from native_install_build import array, pin_sources
from stock_first_install import read_files, stock_input, json_bytes, VIEW, LOCALES
from stock_install_bundle import read_bundle, apply_delta, sha


def build(stock, candidate, out):
    stock_input(stock)
    manifest, deltas, module = read_bundle(candidate)
    fault_path = ROOT/'.lab/native-install-test/proof.json'
    module_path = ROOT/'.lab/native-module-custom-candidate/proof.json'
    for path in (fault_path, module_path):
        pin_sources(json.loads(path.read_text()))
    proof = json.loads(module_path.read_text())
    if proof.get('passed') is not True or proof.get('module_sha256') != sha(module):
        raise ValueError('Missing current module integration proof')
    fault = json.loads(fault_path.read_text())
    if file_sha(fault_path.parent/'host.log') != fault['host_log_sha256']:
        raise ValueError('Fault test log changed')
    original = read_files(stock, [VIEW]+LOCALES)
    values = [module]+[apply_delta(original[p], deltas[p]) for p in LOCALES]
    sizes = [len(raw) for raw in values]
    digests = [bytes.fromhex(sha(raw)) for raw in values]
    old_sizes = [len(original[p]) for p in LOCALES]
    old_hashes = [bytes.fromhex(sha(original[p])) for p in LOCALES]
    attestation = bytes.fromhex(file_sha(module_path))
    vhash = bytes.fromhex(sha(original[VIEW]))
    vsize = len(original[VIEW])
    h = hashlib.sha256(b'A7M3-4.04-filesystem-stage-v1\0'+struct.pack('<II',1,0)+attestation)
    for size, digest in zip(sizes, digests):
        h.update(struct.pack('<I', size)+digest)
    for size, digest in zip(old_sizes, old_hashes):
        h.update(struct.pack('<I', size)+digest)
    h.update(struct.pack('<I', vsize)+vhash)
    binding = h.digest()
    out.mkdir(parents=True, exist_ok=False)
    asm = '.syntax unified\n.section .rodata.bundle,"a"\n'
    for i, raw in enumerate(values):
        (out/f'input{i}.bin').write_bytes(raw)
        asm += f'.balign 4\n.global input{i}\ninput{i}:\n.incbin "input{i}.bin"\n'
    asm += '.section .note.GNU-stack,"",%progbits\n'
    (out/'bundle.S').write_text(asm)
    source = '#include "native_install.h"\nextern const unsigned char input0[],input1[],input2[];\n'
    source += 'static const NativeInstallBundle bundle={1,0,'+array(attestation)+',{'+','.join(
        '{input%d,%d,%s}' % (i,sizes[i],array(digests[i])) for i in range(3))+'},'+array(old_sizes)+','+str(vsize)+',{'+','.join(array(x) for x in old_hashes)+'},'+array(vhash)+'};\n'
    source += 'static const unsigned char expected[32]='+array(binding)+';\n'
    source += '''static NativeInstallReport report;
__attribute__((constructor)) static void stage(void) {
 long fd=native_install_linux_syscall(0,5,(long)"/tmp/jiritsu/a7stockstage.bin",1|64|128,0600,0,0,0);
 if(fd<0)return;
 native_install_run(&bundle,expected,native_install_linux_syscall,0,&report);
 unsigned used=0;while(used<sizeof report){long n=native_install_linux_syscall(0,4,fd,(long)((unsigned char*)&report+used),sizeof report-used,0,0,0);if(n<=0)break;used+=(unsigned)n;}
 native_install_linux_syscall(0,118,fd,0,0,0,0,0);
 native_install_linux_syscall(0,6,fd,0,0,0,0,0);
}
'''
    (out/'bundle.c').write_text(source)
    sources = ['research/native_install.c','research/native_install_linux.c']
    flags = ['-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-mno-unaligned-access','-fPIC','-ffreestanding',
             '-fno-builtin','-fno-stack-protector','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
             '-Os','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I',str(ROOT/'research')]
    objects = []
    for i, path in enumerate([ROOT/p for p in sources]+[out/'bundle.c',out/'bundle.S']):
        obj = out/f'{i}.o'
        subprocess.run(['arm-none-eabi-gcc',*flags,'-c',str(path),'-o',str(obj)],cwd=out,check=True)
        objects.append(str(obj))
    payload = out/'stock-stage-only.so'
    subprocess.run(['arm-none-eabi-ld','-shared','-Bsymbolic','--no-undefined','-z','noexecstack',*objects,'-o',str(payload)],check=True)
    report = dict(kind='stock-404-stage-only-candidate-v1', model='ILCE-7M3', firmware='4.04', executed=False, flash_ready=False,
                  complete_installation=False, bundle_sha256=binding.hex(), payload_sha256=file_sha(payload),
                  candidate_sha256=file_sha(candidate), module_proof_sha256=file_sha(module_path),
                  fault_proof_sha256=file_sha(fault_path), stock_view_sha256=vhash.hex(),
                  payload_bytes=payload.stat().st_size,
                  inputs=[dict(path=p,size=len(data),sha256=sha(data)) for p,data in zip(['/lib/a7fl.so']+LOCALES,values)],
                  phase='Module and locale filesystem staging only; no loader/config/icon/WBI activation',
                  source_sha256={p:file_sha(ROOT/p) for p in sources+['research/native_install.h','payloads/sha256.h',
                      'research/stock_stage_build.py','research/stock_first_install.py','research/native_install_build.py',
                      'research/ext2_patch.py','tools/stock_install_bundle.py','local.py']})
    (out/'manifest.json').write_bytes(json_bytes(report))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stock',type=Path,required=True)
    p.add_argument('--candidate',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a = p.parse_args()
    output = a.out.resolve()
    if not output.is_relative_to((ROOT/'.lab').resolve()):
        p.error('Only a fresh .lab output directory is supported')
    print(json.dumps(build(a.stock.resolve(),a.candidate.resolve(),output),indent=2))
