/* Execute production guards and replay adapter; model dispatch is recorded. */
#define A7_FL_PREVIEW_TEST 1
#include "../payloads/a7-fl-preview.c"
static unsigned checks,allocs,fail_at,freed,initialized,adds,requests,reads;
static int expected[4],bad_size,bad_read,changed,unreadable;
static unsigned objects[5][5];
static void put(const char *s){volatile unsigned *u=(void *)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok){checks++;if(!ok){put("FAIL preview replay guard/ABI\n");stop();}}
static int index_of(uint32_t id){static const uint32_t ids[]={0x1070175,0x1070178,0x1070187,0x107018a};for(int i=0;i<4;i++)if(ids[i]==id)return i;check(0);return 0;}
static int size(uint32_t id){index_of(id);return bad_size?2:1;}
static int read_value(uint32_t id,void *out){int i=index_of(id);reads++;*(uint8_t *)out=(uint8_t)(expected[i]+(changed&&reads==5));return bad_read?0:1;}
static int guard(void *p,uintptr_t address,unsigned n){check(p==objects&&n==16&&address>=0x01000000&&address<0x01200000);return !unreadable;}
static void *allocate(unsigned n){check(n==20&&allocs<5);allocs++;return allocs==fail_at?0:objects[allocs-1];}
static void release(void *p){check(!initialized&&freed<allocs&&p==objects[allocs-1-(fail_at?1:0)-freed]);freed++;}
static void *parameter(void *p,int value){check(initialized<4&&p==objects[initialized]&&value==expected[initialized]);objects[initialized][4]=(unsigned)value;initialized++;return p;}
static void *list(void *p,unsigned value){check(initialized==4&&p==objects[4]&&!value);initialized++;return p;}
static void add(void *p,unsigned id,void *value){static const unsigned ids[]={383,386,389,392,383};check(initialized==5&&adds<5&&p==objects[4]&&id==ids[adds]&&value==objects[adds%4]);adds++;}
static void request(const char *name,unsigned command,void *p){static const char text[]="@M00B";for(unsigned i=0;i<sizeof text;i++)check(name[i]==text[i]);check(command==38&&p==objects[4]&&adds==5&&!freed);requests++;}
void a7_fl_preview_test_bind(struct native_api *api){
 check((uintptr_t)api->allocate==0x0115867c&&(uintptr_t)api->parameter==0x011617cd&&
       (uintptr_t)api->list==0x0115d230&&(uintptr_t)api->add==0x0115c7b8&&
       (uintptr_t)api->request==0x0115aa58&&(uintptr_t)api->release==0x01159c64);
 *api=(struct native_api){allocate,parameter,list,add,request,release};
}
static void reset(void){allocs=freed=initialized=adds=requests=reads=fail_at=0;bad_size=bad_read=changed=unreadable=0;}
static int call(void){struct a7_fl_api api={0};api.size=size;api.read=read_value;return a7_fl_preview_request(0x01000000,&api,guard,objects);}
void guest_main(void){
 for(unsigned i=0;i<6;i++)for(unsigned j=0;j<16;j++)*(uint8_t *)(0x01000000+a7_preview_offsets[i]+j)=a7_preview_pins[i][j];
 for(int style=0;style<=15;style++)for(int c=-3;c<=3;c++)for(int s=-3;s<=3;s++)for(int h=-3;h<=3;h++){
  reset();expected[0]=style;expected[1]=c;expected[2]=s;expected[3]=h;int rc=call();
  if(style==0||style==13||style==15)check(rc==A7_FL_PREVIEW_VALUE&&!allocs&&!requests);
  else {check(rc==1&&allocs==5&&!freed&&requests==1&&reads==8);for(unsigned i=0;i<4;i++)check(report.active[i]==expected[i]);}
 }
 expected[0]=3;expected[1]=1;expected[2]=expected[3]=-1;
 for(unsigned i=1;i<=5;i++){reset();fail_at=i;check(call()==A7_FL_PREVIEW_ALLOC&&allocs==i&&freed==i-1&&!initialized&&!requests);}
 reset();changed=1;check(call()==A7_FL_PREVIEW_CHANGED&&freed==5&&!initialized&&!requests);
 reset();bad_size=1;check(call()==A7_FL_PREVIEW_READ&&!reads&&!allocs);
 reset();bad_read=1;check(call()==A7_FL_PREVIEW_READ&&reads==1&&!allocs);
 for(unsigned i=1;i<4;i++){int old=expected[i];for(int v=-4;v<=4;v+=8){reset();expected[i]=v;check(call()==A7_FL_PREVIEW_VALUE&&!allocs&&!requests);}expected[i]=old;}
 reset();unreadable=1;check(call()==A7_FL_PREVIEW_PIN&&!reads&&!allocs);
 for(unsigned i=0;i<6;i++){reset();uint8_t *p=(void *)(0x01000000+a7_preview_offsets[i]);*p^=1;check(call()==A7_FL_PREVIEW_PIN&&!reads&&!allocs);*p^=1;}
 reset();check(a7_fl_preview_request(0,0,0,0)==A7_FL_PREVIEW_ARGUMENT&&a7_fl_preview_request(0xffffffff,0,0,0)==A7_FL_PREVIEW_ARGUMENT);
 put("NATIVE_PREVIEW_REQUEST_PASSED: exact active style replay, no backup writes, allocation/identity/read guards; request is NOT completion\n");stop();
}
