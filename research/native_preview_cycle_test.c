#define A7_FL_PREVIEW_CYCLE_TEST 1
#include "../payloads/a7-fl-preview-cycle.c"
static unsigned checks,allocs,freed,requests,removed,fail_at,expired_add;
static int expected[4],last[4],bad_size,bad_read,changed,clock_error,timer_error,library_error,span_error;
static unsigned objects[32][8],manager[10];
static struct stamp clock_value;
struct timer_record {uint32_t link;void *opaque;struct stamp deadline;void (*callback)(void*,struct stamp*,void*);uint8_t due;};
static struct timer_record records[8],*head;
static unsigned record_count,repeat_on_restore;
static void put(const char *s){volatile unsigned *u=(void*)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok){checks++;if(!ok){put("FAIL preview cycle\n");stop();}}
static int ix(uint32_t id){static const uint32_t ids[]={0x1070175,0x1070178,0x1070187,0x107018a};for(int i=0;i<4;i++)if(ids[i]==id)return i;check(0);return 0;}
static unsigned reads;
static int size(uint32_t id){ix(id);return bad_size?2:1;}
static int read_value(uint32_t id,void *out){int i=ix(id);reads++;*(uint8_t*)out=(uint8_t)(expected[i]+(changed&&reads==5));return bad_read?0:1;}
static int guard(void *p,uintptr_t at,unsigned n){(void)p;return !span_error&&n&&((at>=0x01000000&&at+n<0x03400000)||at==(uintptr_t)manager);}
static int call(void){struct a7_fl_api api={0};api.size=size;api.read=read_value;return a7_fl_preview_request(0x01000000,&api,guard,0);}
static void *allocate(unsigned n){check(n==20&&allocs<32);allocs++;return allocs==fail_at?0:objects[allocs-1];}
static void release(void *p){check(p==objects[allocs-1-(fail_at?1:0)-freed]);freed++;}
static void *parameter(void *p,int value){((unsigned*)p)[4]=(unsigned)value;return p;}
static void *list(void *p,unsigned n){check(!n);((unsigned*)p)[0]=0;return p;}
static void add(void *p,unsigned id,void *v){static const unsigned ids[]={383,386,389,392,383};unsigned *l=p;check(l[0]<5&&id==ids[l[0]]);l[1+l[0]++]=(unsigned)v;}
static void request(const char *name,unsigned cmd,void *p){
 static const char text[]="@M00B";for(unsigned i=0;i<sizeof text;i++)check(name[i]==text[i]);
 unsigned *l=p;check(cmd==38&&l[0]==5&&l[1]==l[5]&&!freed);
 for(unsigned i=0;i<4;i++)last[i]=(int)((unsigned*)l[i+1])[4];
 requests++;
 if(repeat_on_restore&&requests==2){repeat_on_restore=0;check(call()==1);}
}
int cycle_test_clock(struct stamp *t){*t=clock_value;return clock_error;}
int fixture_clock_now(struct stamp *t){*t=clock_value;return 0;}
int fixture_add_ms(struct stamp *t,unsigned n){t->nsec+=(int)n*1000000;if(t->nsec>=1000000000){t->nsec-=1000000000;t->sec++;}return 0;}
void *fixture_next_record(void *unused,void *previous){(void)unused;return previous?0:head;}
int fixture_detach_record(void *unused,void *p){(void)unused;check(p==head);head=0;return 0;}
static void tick(void){unsigned root=0;((int(*)(void*))0x02861c3d)(&root);}
static void *timer_add(void *m,struct stamp *when,void (*cb)(void*,struct stamp*,void*),void *opaque){
 check(m==manager&&record_count<8&&!head&&!state.lock);
 if(timer_error)return 0;
 struct timer_record *r=&records[record_count++];*r=(struct timer_record){0,opaque,*when,cb,0};head=r;
 if(expired_add){clock_value=*when;tick();}
 return r;
}
static int timer_remove(void *m,void *r){check(m==manager&&r&&head!=r);removed++;return 0;}
static void *open_lib(const char *name,int flags){static const char path[]="/usr/lib/libObj.so";for(unsigned i=0;i<sizeof path;i++)check(name[i]==path[i]);check(flags==6);return library_error?0:(void*)1;}
static int close_lib(void *h){check(h==(void*)1);return 0;}
static int eq(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static void *symbol(void *h,const char *n){check(h==(void*)1);if(eq(n,"timerManager"))return (void*)0x033288bc;if(eq(n,"_ZN12TimerManager6removeEP18timeCallBackRecord"))return (void*)0x0286420d;check(eq(n,"_ZN12TimerManager3addEP8timespecPFvP18timeCallBackRecordS1_PvES4_"));return (void*)0x028641b3;}
void cycle_test_loader(void *(**a)(const char*,int),void *(**b)(void*,const char*),int (**c)(void*)){*a=open_lib;*b=symbol;*c=close_lib;}
void cycle_test_bind(struct native_api *a){check((uintptr_t)a->request==0x01159924&&(uintptr_t)a->timer_add==0x028641b3&&(uintptr_t)a->timer_remove==0x0286420d);*a=(struct native_api){allocate,parameter,list,add,request,release,timer_add,timer_remove};}
static void zero(void *p,unsigned n){uint8_t *b=p;while(n--)*b++=0;}
static void reset(void){
 zero(&state,sizeof state);zero(&report,sizeof report);zero(&cycle,sizeof cycle);zero(objects,sizeof objects);zero(records,sizeof records);
 allocs=freed=requests=removed=fail_at=expired_add=reads=record_count=repeat_on_restore=0;
 bad_size=bad_read=changed=clock_error=timer_error=library_error=span_error=0;head=0;clock_value=(struct stamp){12,850000000};
}
static void finish_cycle(void){check(head!=0);clock_value=head->deadline;tick();check(!head&&!cycle.pending&&cycle.restored==1&&removed==1);}
void guest_main(void){
 for(unsigned i=0;i<sizeof a7_cycle_view_offsets/sizeof a7_cycle_view_offsets[0];i++)for(unsigned j=0;j<16;j++)*(uint8_t*)(0x01000000+a7_cycle_view_offsets[i]+j)=a7_cycle_view_pins[i][j];
 for(unsigned i=0;i<sizeof a7_cycle_obj_offsets/sizeof a7_cycle_obj_offsets[0];i++)for(unsigned j=0;j<16;j++)*(uint8_t*)(0x02000000+a7_cycle_obj_offsets[i]+j)=a7_cycle_obj_pins[i][j];
 *(void**)0x033288bc=manager;manager[9]=42;
 for(int style=0;style<=15;style++)for(int c=-3;c<=3;c++)for(int s=-3;s<=3;s++)for(int h=-3;h<=3;h++){
  reset();expected[0]=style;expected[1]=c;expected[2]=s;expected[3]=h;
  int rc=call();if(style==0||style==13||style==15){check(rc==A7_FL_PREVIEW_VALUE&&!requests);continue;}
  check(rc==1&&requests==1&&allocs==10&&!freed&&cycle.pending==2&&head->deadline.sec==13&&head->deadline.nsec==150000000);
  check(last[0]!=style);for(unsigned i=1;i<4;i++)check(last[i]==expected[i]);
  tick();check(requests==1&&cycle.pending==2); /* original dispatcher: not yet due */
  check(call()==1&&requests==1&&allocs==10&&cycle.coalesced==1);
  finish_cycle();check(requests==2&&report.issued==1&&report.attempts==2&&report.last_result==2);
  for(unsigned i=0;i<4;i++)check(last[i]==expected[i]);
 }
 expected[0]=3;expected[1]=1;expected[2]=expected[3]=-1;
 for(unsigned n=1;n<=10;n++){reset();fail_at=n;check(call()==A7_FL_PREVIEW_ALLOC&&freed==n-1&&!requests&&!head);}
 reset();changed=1;check(call()==A7_FL_PREVIEW_CHANGED&&freed==10&&!requests&&!head);
 reset();clock_error=1;check(call()==A7_FL_PREVIEW_TIMER&&freed==10&&!requests&&!head);
 reset();timer_error=1;check(call()==A7_FL_PREVIEW_TIMER&&freed==10&&!requests&&!cycle.pending);
 reset();expired_add=1;check(call()==A7_FL_PREVIEW_TIMER&&freed==10&&!requests&&!cycle.pending&&removed==1);
 reset();manager[9]=43;check(call()==A7_FL_PREVIEW_LIBRARY&&!requests);manager[9]=42;
 reset();library_error=1;check(call()==A7_FL_PREVIEW_LIBRARY&&!allocs);
 reset();bad_size=1;check(call()==A7_FL_PREVIEW_READ&&!allocs);
 reset();bad_read=1;check(call()==A7_FL_PREVIEW_READ&&!allocs);
 reset();span_error=1;check(call()==A7_FL_PREVIEW_PIN&&!allocs);
 reset();check(call()==1);bad_read=1;finish_cycle();check(last[0]==3&&cycle.restore_result==A7_FL_PREVIEW_READ&&report.last_result==A7_FL_PREVIEW_READ);
 reset();check(call()==1);expected[0]=5;expected[1]=-2;finish_cycle();check(last[0]==5&&last[1]==-2); /* newer user selection wins */
 reset();check(call()==1);expected[0]=cycle.temporary_style;finish_cycle();check(last[0]==5); /* model exposes temporary value */
 expected[0]=3;reset();check(call()==1);repeat_on_restore=1;clock_value=head->deadline;tick();check(cycle.pending==2&&requests==3&&allocs==20&&cycle.restored==1);clock_value=head->deadline;tick();check(!head&&!cycle.pending&&requests==4&&cycle.restored==2);
 for(unsigned i=0;i<sizeof a7_cycle_view_offsets/sizeof a7_cycle_view_offsets[0];i++){reset();uint8_t *p=(void*)(0x01000000+a7_cycle_view_offsets[i]);*p^=1;check(call()==A7_FL_PREVIEW_PIN&&!requests);*p^=1;}
 for(unsigned i=0;i<sizeof a7_cycle_obj_offsets/sizeof a7_cycle_obj_offsets[0];i++){reset();uint8_t *p=(void*)(0x02000000+a7_cycle_obj_offsets[i]);*p^=1;check(call()==A7_FL_PREVIEW_LIBRARY&&!requests);*p^=1;}
 reset();check(a7_fl_preview_request(0,0,0,0)==A7_FL_PREVIEW_ARGUMENT);
 put("NATIVE_PREVIEW_CYCLE_PASSED: original timer dispatcher, delayed restore, coalescing, prearmed-expiry, allocation/clock/pin/read failures; no ISP acknowledgement\n");stop();
}
