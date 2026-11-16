#include <assert.h>
#include <string.h>
#include <stdio.h>
#include "a7-fl-custom-store.h"
static unsigned char disk[2][A7_CUSTOM_RECORD_BYTES];static unsigned lengths[2],writes;static int present[2],torn;
static int readslot(void*ctx,unsigned slot,unsigned char*out,unsigned cap,unsigned*n){(void)ctx;assert(slot<2);*n=lengths[slot];assert(cap>=*n);memcpy(out,disk[slot],*n);return present[slot]?0:1;}
static int replace(void*ctx,unsigned slot,const unsigned char*old,unsigned n,int exists,const unsigned char*next,unsigned size){
 (void)ctx;assert(slot<2&&size==A7_CUSTOM_RECORD_BYTES&&exists==present[slot]&&n==lengths[slot]&&!memcmp(old,disk[slot],n));
 writes++;present[slot]=1;lengths[slot]=torn?size/2:size;memcpy(disk[slot],next,lengths[slot]);return torn?-1:0;
}
int main(void){
 struct a7_custom_io io={readslot,replace,0};struct a7_custom_store s;struct a7_custom_catalog c,next,recovered;
 assert(!a7_custom_store_open(&s,&io,&c)&&c.count==0);
 struct a7_custom_look l={.id="independent",.name="Independent",.base=6,.values={0,0,0,0,0,0,3,0,1,0,0,0,0,0,0,0}};
 assert(!a7_custom_append(&c,&l,&next)&&next.looks[0].slot==7);
 assert(!a7_custom_store_save(&s,&next)&&writes==1);
 assert(!a7_custom_store_open(&s,&io,&recovered)&&recovered.count==1&&recovered.looks[0].values[8]==1);
 next=recovered;next.generation++;next.active=7;next.looks[0].values[8]=3;
 assert(!a7_custom_store_save(&s,&next)&&writes==2);
 assert(!a7_custom_store_open(&s,&io,&recovered)&&recovered.active==7&&recovered.looks[0].values[8]==3);
 assert(a7_custom_store_save(&s,&next)<0&&writes==2);
 next=recovered;next.generation++;next.looks[0].values[8]=4;torn=1;
 assert(a7_custom_store_save(&s,&next)<0&&writes==3&&!s.ready);
 assert(a7_custom_store_open(&s,&io,&recovered)==1&&recovered.generation==2&&recovered.looks[0].values[8]==3);
 assert(a7_custom_store_save(&s,&next)<0&&writes==3);
 puts("CUSTOM_STORE_PASSED: independent create/save/reopen, active selection, stale generation refusal, interrupted save fallback");
}
