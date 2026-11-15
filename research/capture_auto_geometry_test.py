#!/usr/bin/env python3
"""Test source geometry from real snapshots and pin original resize consumers."""
import argparse,json,subprocess
from pathlib import Path
from kernel_probe import ROOT,sha,PINS
from capture_grain_route import Flat
from yc_route_audit import instruction

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--trace',type=Path,required=True)
p.add_argument('--avcam',type=Path,required=True)
a=p.parse_args()
blob=a.avcam.read_bytes()
if sha(blob)!=PINS['avcam']:raise ValueError('Wrong original camera image')
e=Flat(blob)
pins=[instruction(e,at,m,op) for at,m,op in (
    (0x11a04c,'ldrh.w','r3, [r4, #0x96]'),
    (0x11a050,'ldrh.w','r2, [r4, #0x94]'),
    (0x11a068,'ldrh.w','r2, [r4, #0xa6]'),
    (0x11a07e,'ldrh.w','r1, [r4, #0xa2]'),
    (0x11a082,'ldrh.w','r2, [r4, #0x9a]'),
    (0x11a086,'ldrh.w','r0, [r4, #0xa0]'),
    (0x11a08c,'ldrh.w','r1, [r4, #0x98]'),
    (0x11a184,'ldrh.w','r3, [r4, #0x78]'),
    (0x11ac00,'ldrh.w','r3, [r4, #0x74]'))]
trace=json.loads((a.trace/'geometry.json').read_text())
rows=trace['observations']
if [r['requested_size'] for r in rows]!=['L','M','S']:raise ValueError('Requires L/M/S sequence')
out=ROOT/'.lab/capture-auto-geometry';out.mkdir(exist_ok=True)
(out/'proof.json').unlink(missing_ok=True)
data='static const unsigned snapshots[3][368]={'+','.join('{'+','.join(map(str,r['values']))+'}' for r in rows)+'};\n'
source='''#include <string.h>
#include <assert.h>
#include <stdio.h>
static unsigned report[368];
#include "capture_auto_geometry.h"
'''+data+'''
int main(void){
 const unsigned widths[]={6000,3936,3008},strides[]={12160,12000,12000};
 for(unsigned i=0;i<3;i++){
  memcpy(report,snapshots[i],sizeof report);struct a7_capture_geometry g;
  assert(!auto_geometry(&g));assert(g.width==widths[i]&&g.height==4000&&g.stride==strides[i]&&g.offset==160);
  report[40+0xa4/4]^=1;assert(auto_geometry(&g)<0);
  memcpy(report,snapshots[i],sizeof report);report[40+0xac/4]^=1;assert(auto_geometry(&g)<0);
 }
 puts("REAL_SOURCE_GEOMETRY_PASSED L/M/S; destination height deliberately not used as source height");
}
'''
(out/'test.c').write_text(source)
subprocess.run(['clang','-O1','-fsanitize=address,undefined','-Wall','-Wextra','-Werror',
    '-I'+str(ROOT/'payloads'),'-I'+str(ROOT/'research/kernel_probe'),str(out/'test.c'),'-o',str(out/'test')],check=True)
r=subprocess.run([str(out/'test')],capture_output=True,check=True)
sources=['research/capture_auto_geometry_test.py','research/kernel_probe/capture_auto_geometry.h','payloads/a7-capture-geometry.h']
(out/'proof.json').write_text(json.dumps(dict(passed=True,source_sha256={s:sha((ROOT/s).read_bytes()) for s in sources},
    trace_sha256=sha((a.trace/'raw.bin').read_bytes()),avcam_sha256=sha(blob),original_consumer_instructions=pins,
    log=r.stdout.decode(),pixel_write_tested=False,camera_effects_verified=False),indent=2)+'\n')
print(r.stdout.decode(),end='')
