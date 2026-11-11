/* Native YAP selection and register packing, not a Sony ISP simulation. */
#include <stdint.h>
#ifdef A7YAP_PRIVATE
#include "private-tables.h"
#endif
#define BASE 0x635c6000u
static unsigned cases,checks,logs,last_log_api;
static void put(const char*s){volatile uint32_t*u=(void*)0x09000000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};put(s);}}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok){checks++;if(!ok){put("FAIL YAP case=");number(cases);put(" check=");number(checks);put("\n");stop();}}
void native_log(const char *format,unsigned api){(void)format;logs++;last_log_api=api;}
static uint8_t small[2560],large[5120],input[0xa4],output[20];
static uint32_t aperture[(0x15c20+32)/4],device[6];
static uint8_t maker[6352+16];
static uint32_t context[0x6260/4+1],tag_status,tag_calls;
unsigned native_tag_lookup(unsigned handle,unsigned tag,void *entry){
 check(handle==0x1234abcd&&tag==0x2010);tag_calls++;
 if(!tag_status)((uint32_t*)entry)[2]=(uintptr_t)(maker+8);
 return tag_status;
}
static uint8_t byte_at(unsigned at,unsigned seed){return (uint8_t)((at*37u)^(at>>4)^seed);}
void guest_main(void){
 void (*calc)(void*,const void*)=(void*)(BASE+0x3f872d);
 void (*write)(void*,const void*)=(void*)(BASE+0x70fc21);
 void (*record)(void*,const void*)=(void*)(BASE+0x3cbd29);
 void (*read_record)(void*,const void*)=(void*)(BASE+0x3cc001);
 *(uint32_t*)(BASE+0x118d8b4+0x10ac)=(uintptr_t)small;
 *(uint32_t*)(BASE+0x118d8b4+0x7918)=(uintptr_t)large;
 for(unsigned seed=0;seed<4;seed++){
  for(unsigned i=0;i<sizeof small;i++)small[i]=byte_at(i,seed*73);
  for(unsigned i=0;i<sizeof large;i++)large[i]=byte_at(i,seed*109+41);
  for(unsigned api=0;api<256;api++)for(unsigned selector=0;selector<256;selector++){
   for(unsigned i=0;i<sizeof output;i++)output[i]=0xa5;
   for(unsigned i=0;i<sizeof input;i++)input[i]=0x69;
   *(uint32_t*)(input+0x84)=api;input[0xa0]=(uint8_t)selector;
   logs=0;last_log_api=~0u;cases++;
   calc(output+8,input);
   int from_small=api==3||api==4||api==6;
   int from_large=api==1||api==2||api==5;
   uint8_t expected[4]={0xa5,0xa5,0xa5,0xa5};
   if(from_small){expected[0]=small[0x27];expected[1]=small[0x26];expected[2]=small[0xb3];expected[3]=small[0xb2];}
   if(from_large){expected[0]=large[0x1050+selector];expected[1]=large[0x1040+selector];expected[2]=large[0x1037];expected[3]=large[0x1036];}
   check(logs==(unsigned)(!from_small&&!from_large));if(logs)check(last_log_api==api);
   for(unsigned i=0;i<sizeof output;i++)check(output[i]==(i>=8&&i<12?expected[i-8]:0xa5));
   for(unsigned i=0;i<sizeof input;i++){
    uint8_t want=0x69;if(i>=0x84&&i<0x88)want=(uint8_t)(api>>((i-0x84)*8));if(i==0xa0)want=(uint8_t)selector;
    check(input[i]==want);
   }
  }
 }
 for(unsigned i=0;i<sizeof aperture/sizeof *aperture;i++)aperture[i]=0xa57e19c3;
 for(unsigned v=0;v<65536;v++){
  uint16_t pair[2]={(uint16_t)v,(uint16_t)(v^0xa59c)};
  for(unsigned i=0;i<6;i++)device[i]=0x7c3a69b5;
  device[2]=(uintptr_t)(aperture+4); /* object starts at device+1; base is +4 */
  cases++;write(device+1,pair);
  check(aperture[4+0x15c1c/4]==((v<<16)|(v^0xa59c)));
  check(device[3]==0x7c3a6901); /* byte +8 dirty; neighbouring bytes preserved */
  check(device[0]==0x7c3a69b5&&device[1]==0x7c3a69b5&&device[4]==0x7c3a69b5&&device[5]==0x7c3a69b5);
  check(pair[0]==v&&pair[1]==(uint16_t)(v^0xa59c));
 }
 for(unsigned i=0;i<sizeof aperture/sizeof *aperture;i++)if(i!=4+0x15c1c/4)check(aperture[i]==0xa57e19c3);
 /* Validate the separately derived JPEG tag offsets through original code.
    The getter is original too; only the tag provider is a synthetic stub. */
 context[0x625c/4]=0x1234abcd;
 for(unsigned seed=0;seed<4;seed++)for(unsigned v=0;v<256;v++){
  uint16_t pair[6]={0x55aa,0x55aa,(uint16_t)(v|(seed<<8)),(uint16_t)((v^0x9c)|(seed<<12)),0x55aa,0x55aa};
  for(unsigned i=0;i<sizeof maker;i++)maker[i]=byte_at(i,seed);
  tag_status=0;tag_calls=logs=0;cases++;
  record(pair+2,context);
  check(tag_calls==1&&logs==0);
  for(unsigned i=0;i<sizeof maker;i++){
   unsigned expected=byte_at(i,seed);
   if(i==8+0x167d)expected=v;
   if(i==8+0x167e)expected=v^0x9c;
   check(maker[i]==expected);
  }
  check(pair[2]==(uint16_t)(v|(seed<<8))&&pair[3]==(uint16_t)((v^0x9c)|(seed<<12)));
  pair[2]=pair[3]=0xa55a;
  read_record(pair+2,context);
  check(tag_calls==2&&logs==0&&pair[2]==v&&pair[3]==(v^0x9c));
  check(pair[0]==0x55aa&&pair[1]==0x55aa&&pair[4]==0x55aa&&pair[5]==0x55aa);
 }
 for(unsigned fail=1;fail<=2;fail++){
  uint16_t pair[2]={0x369a,0x5c72};
  for(unsigned i=0;i<sizeof maker;i++)maker[i]=0xa5;
  tag_status=fail;tag_calls=logs=0;cases++;
  record(pair,context);read_record(pair,context);
  check(tag_calls==2&&logs==2&&pair[0]==0x369a&&pair[1]==0x5c72);
  for(unsigned i=0;i<sizeof maker;i++)check(maker[i]==0xa5);
 }
#ifdef A7YAP_PRIVATE
 for(unsigned bank=0;bank<2;bank++){
  for(unsigned i=0;i<sizeof small;i++)small[i]=private_table_0[i];
  for(unsigned i=0;i<sizeof large;i++)large[i]=(bank?private_table_2:private_table_1)[i];
  for(unsigned api=1;api<=6;api++)for(unsigned index=0;index<256;index++){
   *(uint32_t*)(input+0x84)=api;input[0xa0]=(uint8_t)index;
   for(unsigned i=0;i<sizeof output;i++)output[i]=0xa5;
   cases++;calc(output+8,input);
   int from_small=api==3||api==4||api==6;
   check(output[8]==(from_small?small[0x27]:large[0x1050+index]));
   check(output[9]==(from_small?small[0x26]:large[0x1040+index]));
   check(output[10]==(from_small?small[0xb3]:large[0x1037]));
   check(output[11]==(from_small?small[0xb2]:large[0x1036]));
   for(unsigned i=0;i<sizeof output;i++)if(i<8||i>=12)check(output[i]==0xa5);
  }
 }
#endif
 put("YAP_LPF_NATIVE_PASSED cases=");number(cases);put(" checks=");number(checks);put("\n");
 put("PARAMETER_BYTES_ONLY; HARDWARE_FILTER_EFFECT_NOT_VERIFIED\n");stop();
}
