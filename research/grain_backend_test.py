#!/usr/bin/env python3
"""Validate userspace loader/config bridge under mocked syscalls; no USB."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'.lab/grain-backend';out.mkdir(exist_ok=True);(out/'proof.json').unlink(missing_ok=True)
(out/'a7-fl-grain-kernel.h').write_text('#define A7_GRAIN_KERNEL_NAME "a7test"\nstatic const unsigned a7_grain_kernel_source_id[]={11,22,33,44};\n')
(out/'blob.S').write_text('.data\n.globl _a7_grain_kernel_start,_a7_grain_kernel_end\n_a7_grain_kernel_start:\n.space 16\n_a7_grain_kernel_end:\n')
(out/'test.c').write_text(r'''
#include <assert.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include "a7-fl-grain-backend.h"
static unsigned installed,selection,loads,writes,position,closing;
static int bad_identity,bad_release,bad_parse,load_error,write_error,short_write,readback_bad,close_error;
static char report[4096],readback[32];
static void reset(void){installed=selection=loads=writes=position=closing=0;bad_identity=bad_release=bad_parse=load_error=write_error=short_write=readback_bad=close_error=0;}
static void make_report(void){unsigned used=0;for(unsigned i=0;i<368;i++){
 unsigned v=i==0?0x4137434b:i==1||i==3||i==4||i==11?1:i>=12&&i<16?(i-11)*11:0;
 if(i==12&&bad_identity)v=999;
 used+=(unsigned)snprintf(report+used,sizeof report-used,"%u%s",v,i==367?"\n":",");
 }if(bad_parse)report[0]='x';}
long a7_grain_test_syscall(long nr,long a,long b,long c){
 if(nr==5){const char*p=(const char*)a;position=0;
  assert(b==0x8000||b==0x8001);
  if(!strcmp(p,"/sys/module/a7test/parameters/report")){if(!installed)return -2;make_report();return 10;}
  assert(!strcmp(p,"/sys/module/a7test/parameters/selection"));
  snprintf(readback,sizeof readback,"%u\n",readback_bad?99:selection);return 11;
 }
 if(nr==6){if(close_error)return -5;closing++;return 0;}
 if(nr==3){assert(a==10||a==11);const char*s=a==10?report:readback;unsigned n=(unsigned)strlen(s)-position;
  if(n>(unsigned)c)n=(unsigned)c;if(n>13)n=13;memcpy((void*)b,s+position,n);position+=n;return n;}
 if(nr==122){memset((void*)a,0,390);strcpy((char*)a+130,bad_release?"wrong":"3.0.27_nl-rt106+");return 0;}
 if(nr==128){assert(b==16&&!strcmp((const char*)c,"arm=1 selection=0"));loads++;if(load_error)return load_error;installed=1;selection=0;return 0;}
 if(nr==4){assert(a==11&&c<=6);writes++;if(write_error)return write_error;if(short_write)return c-1;
  const char*p=(const char*)b;selection=0;for(long i=0;i<c&&p[i]!='\n';i++){assert(p[i]>='0'&&p[i]<='9');selection=selection*10+p[i]-'0';}return c;}
 assert(!"unexpected syscall");return -1;
}
int main(void){
 reset();assert(a7_fl_grain_apply(4,0)==-22&&a7_fl_grain_apply(1,10)==-22&&!loads&&!writes);
 assert(!a7_fl_grain_apply(3,9)&&selection==57&&loads==1&&writes==1);
 for(unsigned p=1;p<=3;p++)for(unsigned s=0;s<=9;s++)assert(!a7_fl_grain_apply(p,s)&&selection==((p<<4)|s)&&loads==1);
 assert(!a7_fl_grain_apply(0,9)&&selection==0&&loads==1);
 assert(a7_fl_film_apply(4,0,0)==-22&&a7_fl_film_apply(1,10,0)==-22&&a7_fl_film_apply(1,0,-10)==-22&&a7_fl_film_apply(1,0,10)==-22);
 for(unsigned p=1;p<=3;p++)for(unsigned g=0;g<=9;g++)for(int h=-9;h<=9;h++)
  assert(!a7_fl_film_apply(p,g,h)&&selection==((p<<9)|((unsigned)(h+9)<<4)|g)&&loads==1);
 assert(!a7_fl_film_apply(0,9,-9)&&selection==0);
 assert(a7_fl_vignette_apply(4,0,0,0)==-22&&a7_fl_vignette_apply(1,10,0,0)==-22&&a7_fl_vignette_apply(1,0,-10,0)==-22&&a7_fl_vignette_apply(1,0,10,0)==-22&&a7_fl_vignette_apply(1,0,0,-10)==-22&&a7_fl_vignette_apply(1,0,0,10)==-22);
 for(unsigned p=1;p<=3;p++)for(unsigned g=0;g<=9;g++)for(int h=-9;h<=9;h++)for(int v=-9;v<=9;v++)
  assert(!a7_fl_vignette_apply(p,g,h,v)&&selection==((p<<14)|((unsigned)(v+9)<<9)|((unsigned)(h+9)<<4)|g)&&loads==1);
 assert(!a7_fl_vignette_apply(0,9,-9,9)&&selection==0);
 reset();installed=1;bad_identity=1;assert(a7_fl_grain_apply(3,9)==-116&&!loads&&!writes);
 reset();installed=1;bad_parse=1;assert(a7_fl_grain_apply(3,9)==-71&&!loads&&!writes);
 reset();bad_release=1;assert(a7_fl_grain_apply(3,9)==-19&&!loads&&!writes);
 reset();load_error=-1;assert(a7_fl_grain_apply(3,9)==-1&&loads==1&&!writes);
 reset();write_error=-13;assert(a7_fl_grain_apply(3,9)==-13&&selection==0);
 reset();short_write=1;assert(a7_fl_grain_apply(3,9)==-5&&writes==1&&selection==0);
 reset();readback_bad=1;assert(a7_fl_grain_apply(3,9)==-5&&selection==57);
 reset();installed=1;close_error=1;assert(a7_fl_grain_apply(3,9)==-5&&!writes);
 puts("GRAIN_BACKEND_PASSED: load defaults Off, exact source identity, 30 grain and 570 film and 10830 vignette combinations, zero, reuse and I/O failures");
}
''')
subprocess.run(['clang','-O1','-g','-fsanitize=address,undefined','-Wall','-Wextra','-Werror','-DA7_FL_GRAIN_BACKEND_TEST','-I'+str(out),'-I'+str(ROOT/'payloads'),str(ROOT/'payloads/a7-fl-grain-backend.c'),str(out/'test.c'),str(out/'blob.S'),'-o',str(out/'test')],check=True)
r=subprocess.run([str(out/'test')],capture_output=True,text=True,check=True);print(r.stdout,end='')
sources=['research/grain_backend_test.py','payloads/a7-fl-grain-backend.c','payloads/a7-fl-grain-backend.h']
(out/'proof.json').write_text(json.dumps(dict(passed=True,source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sources},log=r.stdout,syscalls_mocked=True,camera_run=False,firmware_written=False),indent=2)+'\n')
