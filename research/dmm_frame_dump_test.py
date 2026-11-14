#!/usr/bin/env python3
"""Check bounded read-only frame export and cleanup with modeled syscalls."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sampled',action='store_true');args=p.parse_args()
 out=ROOT/('.lab/dmm-frame-sparse' if args.sampled else '.lab/dmm-frame-dump');out.mkdir(parents=True,exist_ok=True);(out/'proof.json').unlink(missing_ok=True)
 sources=('research/dmm_frame_dump.c','research/dmm_frame_dump.h','research/dmm_frame_dump_test.c','research/dmm_frame_dump_test.py','ui/start.S')
 flags=['-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',str(ROOT/sources[2])]
 if args.sampled:flags+=['-DA7_DMM_SPARSE_FRAME']
 subprocess.run(['clang',*flags,'-fsanitize=address,undefined','-o',str(out/'host')],check=True)
 host=subprocess.run([str(out/'host')],check=True,capture_output=True,timeout=30)
 (out/'guest.ld').write_text('ENTRY(_start)\nSECTIONS {. = 0x100000; .text : {*(.text.start) *(.text*)} .rodata : {*(.rodata*)} .data : {*(.data*)} .bss (NOLOAD) : {__bss_start = .; *(.bss*) *(COMMON) . = ALIGN(8); __bss_end = .;} }\n')
 subprocess.run(['arm-none-eabi-gcc',*flags,'-DDUMP_QEMU','-mcpu=cortex-a9','-mthumb','-mno-unaligned-access','-ffreestanding','-fno-builtin','-nostdlib','-T',str(out/'guest.ld'),str(ROOT/'ui/start.S'),'-lgcc','-o',str(out/'test.elf')],check=True)
 arm=subprocess.run(['qemu-system-arm','-M','realview-pbx-a9','-smp','1','-m','64','-nodefaults','-audio','none','-nic','none','-display','none','-monitor','none','-serial','stdio','-semihosting-config','enable=on,target=native','-device',f'loader,file={out}/test.elf,cpu-num=0'],check=True,capture_output=True,timeout=30)
 for name,result in (('host',host),('arm',arm)):
  (out/(name+'.log')).write_bytes(result.stdout+result.stderr)
  if b'DMM_FRAME_DUMP_PASSED' not in result.stdout or b'FAIL' in result.stdout+result.stderr:raise ValueError('Frame dump check failed')
 if host.stdout!=arm.stdout:raise ValueError('Host and ARM results differ')
 print(arm.stdout.decode(),end='')
 sha=lambda b:hashlib.sha256(b).hexdigest()
 (out/'proof.json').write_text(json.dumps(dict(source_sha256={s:sha((ROOT/s).read_bytes()) for s in sources},log=arm.stdout.decode().splitlines(),
  host_log_sha256=sha(host.stdout+host.stderr),arm_log_sha256=sha(arm.stdout+arm.stderr),syscalls_modeled=True,
  sampled=args.sampled,camera_executed=False,pixel_format_proven=False,exclusive_ownership_proven=False),indent=2)+'\n')
if __name__=='__main__':main()
