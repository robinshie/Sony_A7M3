#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
static unsigned calls,fail_call,checks;
static unsigned char params[240],input[32],node[32],child0[32],child8[288];
static int read_meta(void *dest,unsigned long addr,unsigned size){
    unsigned addrs[]={0x60100000,0x60200000,0x60300000,0x60400000,0x60500000};
    unsigned sizes[]={240,32,32,32,288};void *data[]={params,input,node,child0,child8};
    calls++;
    if(calls==fail_call)return -14;
    for(unsigned i=0;i<5;i++)if(addr==addrs[i]){assert(size==sizes[i]);memcpy(dest,data[i],size);return 0;}
    assert(addr==0);return -34;
}
#define DETAIL_READ read_meta
#include "kernel_probe/capture_detail_record.h"
#define CHECK(x) do{assert(x);checks++;}while(0)
int main(void){
    unsigned regs[14]={0x61000000,0x60100000,2,3,4,0x60200000,6,7,8,9,10,11,12,13};
    unsigned out[178];
    for(unsigned n=0;n<64;n++)for(fail_call=0;fail_call<=5;fail_call++){
        for(unsigned i=0;i<sizeof params;i++)params[i]=(unsigned char)(n+i);
        unsigned a=0x60300000,b=0x60400000,c=0x60500000;
        memcpy(input+16,&a,4);memcpy(node,&b,4);memcpy(node+8,&c,4);
        memset(out,0xa5,sizeof out);calls=0;detail_snapshot(out+1,regs,n);
        CHECK(calls==5);CHECK(out[0]==0xa5a5a5a5);CHECK(out[177]==0xa5a5a5a5);
        CHECK(out[1]==3);CHECK(out[2]==n);CHECK(out[176]==n);
        CHECK(out[3]==regs[0]);CHECK(out[8]==regs[5]);
        if(!fail_call){CHECK(!memcmp(out+11,params,240));CHECK(!memcmp(out+95,child8,288));for(unsigned i=167;i<172;i++)CHECK(out[i]==0);}
        else CHECK((int)out[166+fail_call]==-14);
        if(fail_call==2){CHECK((int)out[169]==-34);CHECK((int)out[170]==-34);CHECK((int)out[171]==-34);}
        if(fail_call==3){CHECK((int)out[170]==-34);CHECK((int)out[171]==-34);}
    }
    printf("DETAIL_METADATA_PASSED checks=%u cases=384\n",checks);
}
