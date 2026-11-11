#define NATIVE_MENU_PROBE_TEST
#include "native_menu_probe.c"
#include "actual-maps.h"
static unsigned clock_step,clock_value;
uint32_t native_menu_probe_test_time(void){clock_value+=clock_step;return clock_value;}
static void put(const char *s){volatile unsigned *u=(volatile unsigned *)0x09000000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void done(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok,const char *s){if(!ok){put("FAIL ");put(s);put("\n");done();}}
static void zero(void *p,unsigned n){for(unsigned i=0;i<n;++i)((uint8_t *)p)[i]=0;}
static void maps(const char *p){unsigned i=0;zero(&report,sizeof report);range_count=0;while(p[i]){report.maps[i]=p[i];i++;}report.maps_n=i;check(parse_maps(),"parse maps");}
void guest_main(void){
 uint32_t out[4];
 maps((const char *)actual_maps);
 check(report.view_base==0x14f89000&&report.caution_base==0x15a17000,"actual camera bases");
 check(span(report.view_base+0xa61c10,0xa8df9c-0xa61c10),"actual BSS crosses readable file/anonymous boundary");
 check(!span(report.view_base+0x849a30,0x8000),"actual library guard gap rejected");
 maps("40000000-40a80000 r-xp 00000000 00:00 1 /usr/lib/viewUnified2.so\n"
      "40a80000-40a90000 rw-p 00000000 00:00 0 \n"
      "42000000-42a80000 r-xp 00000000 00:00 2 /usr/lib/CautionConfig.so\n"
      "43000000-43001000 rw-s 00000000 00:00 3 /dev/mock\n"
      "44000000-44001000 rw-p 00000000 00:00 4 /tmp/unrelated\n"
      "45000000-45001000 rw-p 00000000 00:00 0 [heap]\n");
 check(!safe_copy(0x40000001,out,1),"unaligned pointer rejected before load");
 check(!safe_copy(0xfffffffcu,out,2),"overflow rejected");
 check(!safe_copy(0x41000000,out,1),"unmapped pointer rejected");
 check(!safe_copy(0x43000000,out,1),"device/shared mapping rejected");
 check(!safe_copy(0x44000000,out,1),"unrelated file mapping rejected");
 check(span(0x45000000,0x1000),"heap allowed");
 uint32_t *node=(uint32_t *)0x40a61c10,*children=(uint32_t *)0x40a50000,*cs=(uint32_t *)0x42a75ff4;
 node[0]=0x42918ec8;node[1]=(uint32_t)children;node[2]=3;
 children[0]=(uint32_t)cs;children[1]=0x43000000;children[2]=0x44000001;
 cs[0]=0x42925860;
 uint32_t *ancestor=(uint32_t *)0x40a70000,*pages=(uint32_t *)0x40a50020;
 ancestor[0]=0x42918ec8;ancestor[1]=(uint32_t)pages;ancestor[2]=2;
 pages[0]=(uint32_t)node;pages[1]=0x40a61c38;node[4]=(uint32_t)ancestor;node[5]=3;
 zero(&witness,sizeof witness);scan_nodes();
 check(witness.status==3&&witness.count==1&&witness.parents[0].address==(uint32_t)node,"bounded good parent scan");
 check(witness.ancestor_count==1&&witness.ancestors[0].words[2]==2&&witness.ancestors[0].pages[0][3]==3,"ancestor and per-page count witness");
 check(witness.parents[0].children[1].title==~0u,"bad child properties do not dereference device");
 node[1]=(uint32_t)children+1;zero(&witness,sizeof witness);scan_nodes();
 check(witness.status==3&&!witness.count,"false positive unaligned childarray ignored");
 node[1]=(uint32_t)children;node[2]=0xffffffff;zero(&witness,sizeof witness);scan_nodes();
 check(witness.status==3&&!witness.count,"huge count ignored");
 node[2]=3;clock_step=2500;zero(&witness,sizeof witness);scan_nodes();
 check(witness.status==4,"two-second budget stops scan");
 put("NATIVE_MENU_PROBE_PASSED: actual808-line maps, split BSS, unaligned/overflow/unmapped/device/file pointers, bounded scan and deadline\n");done();
}
