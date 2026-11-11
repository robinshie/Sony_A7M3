#include "native_menu_wbi.c"
static unsigned checks,position,fdmode,writes,opens,failwrite,shortwrite,badcap,badtype,mutate,syncfail;
static unsigned char disk[1024],expected[1024];
static void say(const char*s){volatile unsigned*p=(void*)0x09000000;while(*s){while(p[6]&32){}p[0]=*s++;}}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");for(;;){}}
static void fail(unsigned n){say("NWB_FAIL ");char b[12];unsigned i=0;do{b[i++]=(char)('0'+n%10);n/=10;}while(n);while(i){char s[2]={b[--i],0};say(s);}say("\n");stop();}
#define CHECK(x) do{checks++;if(!(x))fail(__LINE__);}while(0)
static long fake(void*ctx,long n,long a,long b,long c,long d,long e,long f){(void)ctx;(void)d;(void)e;(void)f;
 if(n==EUID)return 0;if(n==PID)return 163;
 if(n==OPEN){CHECK(eq((void*)a,path,sizeof path));CHECK(b==0x8000||b==(0x8000|0x1002));fdmode=(unsigned)b;position=0;opens++;if((b&3)&&mutate)disk[42]^=1;return 7;}
 if(n==CLOSE)return a==7?0:-9;
 if(n==FSTAT64){clear((void*)b,128);*(uint32_t*)(b+16)=badtype?0x8000:0x6000;return 0;}
 if(n==IOCTL){CHECK((unsigned long)b==0x80041272u);((uint32_t*)c)[0]=badcap?0x03b00000:0x03c00000;((uint32_t*)c)[1]=0;return 0;}
 if(n==SEEK){CHECK(c==0&&b==0);position=0;return 0;}
 if(n==RD){CHECK(position+(unsigned)c<=1024);for(unsigned i=0;i<(unsigned)c;i++)((unsigned char*)b)[i]=disk[position+i];position+=(unsigned)c;return c;}
 if(n==WR){CHECK(fdmode==(0x8000|0x1002));CHECK(position+(unsigned)c<=512);writes++;if(failwrite&&writes==failwrite)return -5;if(shortwrite&&(unsigned)c>17)c=17;for(unsigned i=0;i<(unsigned)c;i++)disk[position+i]=((unsigned char*)b)[i];position+=(unsigned)c;return c;}
 if(n==SYNC)return syncfail?-5:0;return -38;
}
static void reset(void){clear(disk,sizeof disk);*(uint32_t*)disk=0x31494257;*(uint32_t*)(disk+20)=512;for(unsigned i=512;i<1024;i++)disk[i]=(unsigned char)i;for(unsigned i=0;i<1024;i++)expected[i]=disk[i];writes=opens=failwrite=shortwrite=badcap=badtype=mutate=syncfail=0;}
void guest_main(void){NwbReport r;CHECK(sizeof r==1112);reset();CHECK(nwb_run(fake,0,0,0,&r)==0);CHECK(r.phase==3&&r.header_kind==2&&r.neighbor_ok&&r.capacity_lo==62914560&&!writes&&opens==1);CHECK(eq(disk,expected,1024));
 reset();CHECK(nwb_run(fake,0,1,expected,&r)==0);CHECK(r.phase==100&&r.written==512&&r.fsync_ok&&r.neighbor_ok&&opens==3);unsigned char z[512];clear(z,512);CHECK(eq(disk,z,512)&&eq(disk+512,expected+512,512));
 reset();shortwrite=1;CHECK(nwb_run(fake,0,1,expected,&r)==0&&r.written==512&&writes>1&&r.neighbor_ok);
 reset();shortwrite=1;failwrite=2;CHECK(nwb_run(fake,0,1,expected,&r)<0&&r.written==17&&r.error==-5&&writes==2&&eq(disk+512,expected+512,512));
 reset();badcap=1;CHECK(nwb_run(fake,0,1,expected,&r)<0&&!writes);
 reset();badtype=1;CHECK(nwb_run(fake,0,1,expected,&r)<0&&!writes);
 reset();expected[10]^=1;CHECK(nwb_run(fake,0,1,expected,&r)==-5&&!writes&&opens==1);
 reset();mutate=1;CHECK(nwb_run(fake,0,1,expected,&r)==-5&&!writes&&opens==2);
 reset();disk[0]=0;CHECK(nwb_run(fake,0,1,expected,&r)==-4&&!writes);
 reset();disk[20]=1;CHECK(nwb_run(fake,0,1,expected,&r)==-4&&!writes);
 reset();clear(disk,512);CHECK(nwb_run(fake,0,0,0,&r)==1&&!writes&&r.header_kind==0);CHECK(nwb_run(fake,0,1,expected,&r)==-3&&!writes);
 reset();syncfail=1;CHECK(nwb_run(fake,0,1,expected,&r)<0&&r.written==512&&!r.fsync_ok&&r.error==-5);
 say("NWB_ARM_ALL_PASS: read-only; exact1024preimage; block/size/magic/sector guards; short writes; partial failure; reopen race; fsync failure; neighbor unchanged\n");stop();}
