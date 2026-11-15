#!/usr/bin/env python3
"""ASan/UBSan test of actual repeat dispatch and selection; native pixel work mocked."""
import json,subprocess,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'.lab/capture-repeat-control';out.mkdir(exist_ok=True);(out/'proof.json').unlink(missing_ok=True)
sources=['research/capture_repeat_test.py','research/kernel_probe/capture_frame.c','research/kernel_probe/capture_repeat_control.h']
frame=(ROOT/sources[1]).read_text();dispatch=frame[frame.index('void a7_multi_record('):frame.index('static int on_undef(')]
header=r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <errno.h>
#include <limits.h>
#define A7_EARLY 1
#define A7_LEASE 1
#define A7_GRAIN_REPEAT 1
#define ACCESS_ONCE(v) (*(volatile __typeof__(v) *)&(v))
struct kernel_param{int unused;};
struct kernel_param_ops{int(*set)(const char*,const struct kernel_param*);int(*get)(char*,const struct kernel_param*);};
static int param_get_uint(char *p,const struct kernel_param*k){(void)p;(void)k;return 0;}
static int kstrtoint(const char*s,unsigned b,int*out){char*e;long v=strtol(s,&e,b);if(e==s||(*e&&strcmp(e,"\n"))||v<INT_MIN||v>INT_MAX)return -EINVAL;*out=v;return 0;}
#define module_param_cb(a,b,c,d)
#include "capture_repeat_control.h"
typedef unsigned atomic_t;
static unsigned report[368],total,sampled[4],jiffies=109;
static int atomic_cmpxchg(atomic_t*p,unsigned old,unsigned value){unsigned n=*p;if(n==old)*p=value;return n;}
static int atomic_inc_return(atomic_t*p){return ++*p;}
static void atomic_set(atomic_t*p,unsigned value){*p=value;}
#define smp_mb() ((void)0)
#define smp_wmb() ((void)0)
static unsigned early_calls,lease_calls,inject,seen_strength,seen_seed;
static int early_error,lease_error;
static unsigned regs[14]={0x641b6f10U};
void a7_multi_record(unsigned,const unsigned*);
static int take_early_record(const unsigned*r){assert(r==regs);early_calls++;return early_error;}
static int take_lease_test(void){lease_calls++;seen_strength=frame_selection&15;seen_seed=frame_seed;
 if(inject){inject=0;assert(!selection_set("18",0));a7_multi_record(2,regs);assert(frame_selection==57&&frame_seed==seen_seed);}
 report[349]=24000000;return lease_error;}
'''
tail=r'''
int main(void){
 (void)selection_ops;unsigned valid=0;char text[32];
 for(unsigned n=0;n<65536;n++){unsigned old=selection;snprintf(text,sizeof text,"%u",n);int rc=selection_set(text,0);
  if((n==0)||(n>=16&&n<=57&&(n&15)<=9)){assert(rc==0&&selection==n);valid++;}
  else assert(rc==-EINVAL&&selection==old);
 }assert(valid==31);
 assert(selection_set("-1",0)==-EINVAL&&selection_set("57junk",0)==-EINVAL);
 assert(!selection_set("57",0));a7_multi_record(1,regs);unsigned wrong[14]={0};a7_multi_record(2,wrong);assert(total==0);
 inject=1;a7_multi_record(2,regs);assert(total==1&&early_calls==1&&lease_calls==1&&completed==1&&!sampled[2]&&seen_strength==9);
 unsigned previous=seen_seed;a7_multi_record(2,regs);assert(total==2&&completed==2&&seen_strength==2&&previous!=seen_seed);
 assert(!selection_set("0",0));a7_multi_record(2,regs);assert(total==3&&skipped==1&&lease_calls==2&&!sampled[2]);
 assert(!selection_set("48",0));a7_multi_record(2,regs);assert(skipped==2&&lease_calls==2);
 assert(!selection_set("57",0));early_error=-EINVAL;a7_multi_record(2,regs);assert(failed==1&&selection==0&&lease_calls==2&&!sampled[2]);
 early_error=0;lease_error=-EIO;assert(!selection_set("57",0));a7_multi_record(2,regs);assert(failed==2&&selection==0&&completed==2&&!sampled[2]);
 lease_error=0;assert(!selection_set("57",0));sampled[2]=1;unsigned count=total;a7_multi_record(2,regs);assert(total==count);sampled[2]=0;
 a7_multi_record(2,regs);assert(completed==3&&failed==2&&!sampled[2]);
 puts("REPEAT_CONTROL_PASSED: 65536 selections, off, repeated shots, distinct seeds, in-flight update, reentry, failure disable");return 0;
}
'''
(out/'test.c').write_text(header+dispatch+tail)
subprocess.run(['clang','-O1','-g','-fsanitize=address,undefined','-Wall','-Wextra','-Werror','-I'+str(ROOT/'research/kernel_probe'),str(out/'test.c'),'-o',str(out/'test')],check=True)
r=subprocess.run([str(out/'test')],check=True,capture_output=True,text=True);print(r.stdout,end='')
(out/'proof.json').write_text(json.dumps(dict(passed=True,source_sha256={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in sources},log=r.stdout,scope='Actual selection parser and dispatch; atomic operations sequentially mocked with reentry injection, native lease and pixels mocked',camera_run=False,firmware_written=False),indent=2)+'\n')
