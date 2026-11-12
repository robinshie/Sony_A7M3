/* Read-only: check callback owner before introducing callbacks in a late DSO. */
#define A7_RUNTIME_LIBRARY_ONLY
#include "a7-runtime-probe.c"
#include "a7-fl-preview-cycle-pins.h"
static struct {uint32_t magic,pid,obj,manager,status,words[10];} result;
__attribute__((constructor)) static void capture(void){
 result.magic=0x4137544d;result.pid=(uint32_t)sc3(20,0,0,0);
 report.maps_n=read_proc("/proc/self/maps",report.maps,sizeof report.maps-1);
 if(report.maps_n>0){
  report.maps[report.maps_n]=0;
  for(const char *p=report.maps;*p;){
   if(contains(p,"r-xp 00000000")&&contains(p,"/usr/lib/libObj.so")){result.obj=hex(&p);break;}
   while(*p&&*p!='\n')p++;if(*p)p++;
  }
  if(result.obj&&readable(result.obj+0x8641b2,16)){
   result.status=1;
   for(unsigned i=0;i<16;i++)if(*(uint8_t*)(result.obj+0x8641b2+i)!=a7_cycle_obj_pins[0][i])result.status=0;
   if(result.status&&copy_address(result.obj+0x13288bc,&result.manager,1)&&
      copy_address(result.manager,result.words,10))result.status=2;
  }
 }
 long fd=sc3(5,(long)"/tmp/jiritsu/a7timer.bin",1|64|128|0x8000,0600);if(fd<0)return;
 sc3(4,fd,(long)&result,sizeof result);sc3(118,fd,0,0);sc3(6,fd,0,0);
}
