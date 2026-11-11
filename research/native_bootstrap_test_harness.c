/* Actual bootstrap source under QEMU. Only Linux I/O and module/backend calls
 * are mocked; original byte pins, maps parsing and lifecycle guards execute. */
#include <stdint.h>
#include "a7-fl-module.h"
int a7_fl_configure_menu(const struct a7_fl_platform *);
int a7_fl_initialize_color_prepared(void);
#define A7_FL_BOOTSTRAP_TEST 1
#include "../payloads/a7-fl-bootstrap.c"

#define VIEW 0x40000000u
#define CAUTION 0x50000000u
#define BACKUP 0x60000000u
#define VM ((void *)(VIEW+0xa61000))
static unsigned checks,prepare_calls,configure_calls,install_calls,color_calls,backup_calls;
static unsigned syscall_count,fail_at,read_chunk,fd_position[2],fd_open[2];
static int foreign_model,model_size,model_attr,model_read;
static struct a7_fl_platform supplied;
static struct a7_fl_module_status status;
static const char *map_text,*version_text;
static char map_buffer[4096];
static const char valid_maps[]=
 "40000000-40c00000 r-xp 00000000 00:00 1 /usr/lib/viewUnified2.so\n"
 "50000000-50b00000 r-xp 00000000 00:00 2 /usr/lib/CautionConfig.so\n"
 "60000000-60010000 r-xp 00000000 00:00 3 /usr/lib/libbackup.so\n"
 "70000000-71000000 rw-p 00000000 00:00 0 [heap]\n";
static a7_menu_node items[3];
static a7_menu_node *still_children[3];
static void put(const char *s){volatile unsigned *uart=(void *)0x09000000;while(*s){while(uart[6]&32){}uart[0]=*s++;}}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]='0'+n%10;n/=10;}while(n);while(i){char c[2]={b[--i],0};put(c);}}
static void finish(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");while(1){}}
static void check(int ok,const char *name){checks++;if(!ok){put("FAIL ");put(name);put(" check=");number(checks);put("\n");finish();}}
void *memcpy(void *d,const void *s,unsigned n){unsigned char *a=d;const unsigned char *b=s;while(n--)*a++=*b++;return d;}
void *memset(void *d,int v,unsigned n){unsigned char *a=d;while(n--)*a++=(unsigned char)v;return d;}
static unsigned length(const char *s){unsigned n=0;while(s[n])n++;return n;}
static int equal(const char *a,const char *b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static void append(char *to,const char *s){memcpy(to+length(to),s,length(s)+1);}
static int backup_size(uint32_t id){backup_calls++;check(id==0x3e0005,"identity size property only");return model_size;}
static int backup_attr(uint32_t id){backup_calls++;check(id==0x3e0005,"identity attr property only");return model_attr;}
static int backup_read(uint32_t id,void *out){backup_calls++;check(id==0x3e0005,"identity read property only");memset(out,0,16);memcpy(out,foreign_model?"ILCE-7M4":"ILCE-7M3",8);return model_read;}
static int backup_write(uint16_t bank,uint32_t id,const void *data){(void)bank;(void)id;(void)data;check(0,"bootstrap must not write via identity API");return -1;}
void a7_fl_bootstrap_test_backup(struct a7_fl_api *p){
 check((uintptr_t)p->size==BACKUP+0x1175&&(uintptr_t)p->attr==BACKUP+0x11d5&&
       (uintptr_t)p->read==BACKUP+0x1205&&(uintptr_t)p->write==BACKUP+0x1359,"real Backup entry pointers retain Thumb bit");
 p->size=backup_size;p->attr=backup_attr;p->read=backup_read;p->write=backup_write;
}
long a7_fl_bootstrap_test_syscall3(long nr,long a,long b,long c){
 syscall_count++;if(syscall_count==fail_at)return -5;
 if(nr==5){int fd=equal((const char *)a,"/proc/self/maps")?0:equal((const char *)a,"/version.txt")?1:-1;
  check(fd>=0,"bootstrap only reads expected files");check(!(b&3),"bootstrap files opened read-only");fd_open[fd]=1;fd_position[fd]=0;return fd+3;}
 if(nr==3){int fd=(int)a-3;check(fd>=0&&fd<2&&fd_open[fd],"read valid mock descriptor");const char *data=fd?version_text:map_text;
  unsigned n=length(data)-fd_position[fd];if(n>(unsigned)c)n=(unsigned)c;if(!fd&&read_chunk&&n>read_chunk)n=read_chunk;
  memcpy((void *)b,data+fd_position[fd],n);fd_position[fd]+=n;return n;}
 if(nr==6){int fd=(int)a-3;check(fd>=0&&fd<2&&fd_open[fd],"close valid mock descriptor");fd_open[fd]=0;return 0;}
 check(0,"unexpected bootstrap syscall");return -1;
}
void a7_fl_posix_io(struct a7_fl_store_io *io){memset(io,0,sizeof *io);}
int a7_fl_prepare(const struct a7_fl_platform *p){prepare_calls++;supplied=*p;check(p->view_manager==0,"color prepare has no UI argument");return 0;}
int a7_fl_configure_menu(const struct a7_fl_platform *p){configure_calls++;supplied=*p;check(p->parent_count==1&&p->parents[0]==(void *)(VIEW+0xa6dfa4),"native still-only page matches profile");check(p->anchors[0]==&items[2]&&p->creative_style==(void *)(CAUTION+0xa75ff4),"native anchor matches actual final still-page child");return 0;}
const struct a7_fl_module_status *a7_fl_status(void){return &status;}
int a7_fl_initialize_color_prepared(void){color_calls++;check(supplied.event(0,A7_FL_BOOT_EVENT)==1&&!supplied.event(0,A7_FL_INSTALL_EVENT),"boot event permits only color lifecycle");check(supplied.identity(0)==1,"boot core rechecks real identity guard");return 0;}
int a7_fl_install_prepared(uintptr_t base,void *vm){install_calls++;check(base==VIEW&&vm==VM,"module receives exact view and ViewManager");check(supplied.event(0,A7_FL_INSTALL_EVENT)==1&&!supplied.event(0,A7_FL_BOOT_EVENT),"MENU event permits only menu lifecycle");check(supplied.identity(0)==1,"menu core rechecks real identity guard");status.installed=1;return 0;}
extern int test_call_install(uintptr_t,void *,unsigned);
extern int test_old_call_install(uintptr_t,void *,unsigned);
static void reset(void){
 memset(&boot,0,sizeof boot);memset(&status,0,sizeof status);memset(&supplied,0,sizeof supplied);
 prepare_calls=configure_calls=install_calls=color_calls=backup_calls=syscall_count=fail_at=read_chunk=0;
 foreign_model=0;model_size=model_read=16;model_attr=1;map_text=valid_maps;version_text="37114_13.2026020901";
 memset(fd_open,0,sizeof fd_open);
 memcpy((void *)(BACKUP+0x1174),a7_pin_size,16);memcpy((void *)(BACKUP+0x11d4),a7_pin_attr,16);
 memcpy((void *)(BACKUP+0x1204),a7_pin_read,16);memcpy((void *)(BACKUP+0x1358),a7_pin_write,16);
 memcpy((void *)(CAUTION+0x68338c),a7_pin_ctor,16);memcpy((void *)(CAUTION+0x6830aa),a7_pin_init,16);
 *(uintptr_t *)(VIEW+0xa61c18)=VIEW+0x87f720;
 memset(items,0,sizeof items);
 for(unsigned j=0;j<3;j++)still_children[j]=&items[j];
 a7_menu_node *p=(void *)(VIEW+0xa6dfa4);memset(p,0,sizeof *p);p->vtable=(void *)(CAUTION+0x918ec8);p->children=still_children;p->count=3;p->depth=3;p->parent=(void *)(VIEW+0xa69c88);p->properties=(void *)(VIEW+0xa725a0);p->serial=p->index=14;
}
static void cold_page(void){a7_menu_node *p=(void *)(VIEW+0xa6dfa4);p->depth=p->selected=p->serial=p->index=p->state=0;p->parent=0;p->children=(void *)(VIEW+0x8f3214);memcpy(p->children,still_children,sizeof still_children);}
static void rejected(const char *name){check(test_call_install(VIEW,VM,0)!=0,name);check(!configure_calls&&!install_calls&&!color_calls,"rejected guard never reaches active module");}
void guest_main(void){
 reset();check(test_call_install(VIEW,VM,0)==0,"valid MENU bootstrap");check(prepare_calls==1&&configure_calls==1&&install_calls==1&&!color_calls,"MENU lifecycle routing");
 check(!boot.installing&&!boot.lock,"lifecycle guard and lock cleared");check(!event(0,A7_FL_INSTALL_EVENT)&&!event(0,A7_FL_CONFIRM_EVENT),"no event outside active lifecycle");
 check(test_call_install(VIEW,VM,0)==0&&prepare_calls==1&&configure_calls==1&&install_calls==2,"repeat MENU preserves prepared identity");
 check(test_call_install(VIEW,(void *)((uintptr_t)VM+4),0)!=0&&install_calls==2,"different ViewManager rejected after install");
 reset();check(test_call_install(VIEW,(void *)1,1)==0,"boot ignores invalid UI argument");check(color_calls==1&&prepare_calls==1&&!configure_calls&&!install_calls,"boot does not dereference menu pages");
 check(test_call_install(VIEW,VM,0)==0&&prepare_calls==1&&configure_calls==1&&install_calls==1,"MENU configures pages after color startup");
 reset();((a7_menu_node *)(VIEW+0xa6dfa4))->count=-1;check(test_call_install(VIEW,(void *)1,1)==0&&color_calls==1,"boot independent of uninitialized menu page");
 reset();cold_page();
 check(test_call_install(VIEW,VM,0)==0&&configure_calls==1&&install_calls==1,"cold static native pages accepted before original graph initialization");
 reset();check(a7_fl_install(VIEW,VM,0)!=0&&!syscall_count,"unrecognized direct caller rejected before I/O");
 check(test_old_call_install(VIEW,VM,0)!=0&&!syscall_count,"obsolete loader return address rejected");
 check(test_call_install(VIEW,VM,2)!=0&&!syscall_count,"invalid mode rejected before I/O");
 check(test_call_install(VIEW+4,VM,0)!=0&&!syscall_count,"mismatched view base rejected before I/O");
 reset();boot.lock=1;check(test_call_install(VIEW,VM,0)==A7_FL_MODULE_BUSY&&!syscall_count,"recursive bootstrap rejected");
 reset();version_text="37114_13.2026020901x";rejected("extra build byte rejected");
 reset();version_text="37114_13.202602090";rejected("truncated build rejected");
 reset();version_text="37114_13.2026020902";rejected("foreign build rejected");
 reset();foreign_model=1;rejected("foreign camera model rejected");
 reset();model_size=15;rejected("wrong model data size rejected");
 reset();model_attr=2;rejected("wrong model data attribute rejected");
 reset();model_read=15;rejected("short model read rejected");
 const uintptr_t pins[]={BACKUP+0x1174,BACKUP+0x11d4,BACKUP+0x1204,BACKUP+0x1358,CAUTION+0x68338c,CAUTION+0x6830aa};
 for(unsigned j=0;j<6;j++){reset();*(unsigned char *)pins[j]^=1;rejected("changed original function pin rejected");check(!backup_calls,"changed machine code rejected before API call");}
 reset();*(uintptr_t *)(VIEW+0xa61c18)^=4;rejected("foreign process-manager vtable rejected");
 reset();check(test_call_install(VIEW,(void *)0x2000,0)!=0&&!install_calls,"unmapped ViewManager rejected");
 reset();check(test_call_install(VIEW,(void *)((uintptr_t)VM+1),0)!=0&&!install_calls,"unaligned ViewManager rejected");
 for(unsigned f=0;f<7;f++){reset();a7_menu_node *p=(void *)(VIEW+0xa6dfa4);if(!f)p->vtable=0;else if(f==1)p->count=4;else if(f==2)p->depth=2;else if(f==3)p->parent=0;else if(f==4)p->properties=0;else if(f==5)p->serial=13;else p->index=13;rejected("mismatched native warm page profile rejected");}
 for(unsigned f=0;f<7;f++){reset();cold_page();a7_menu_node *p=(void *)(VIEW+0xa6dfa4);if(!f)p->children=still_children;else if(f==1)p->parent=(void *)VIEW;else if(f==2)p->depth=1;else if(f==3)p->selected=1;else if(f==4)p->serial=1;else if(f==5)p->index=1;else p->state=1;rejected("mismatched native cold page profile rejected");}
 reset();((a7_menu_node *)(VIEW+0xa6dfa4))->children=(void *)((uintptr_t)still_children+1);rejected("unaligned child array rejected");
 for(unsigned j=0;j<3;j++){reset();still_children[j]=(void *)((uintptr_t)&items[j]+1);rejected("every unaligned still child rejected");reset();still_children[j]=(void *)0x2000;rejected("every unmapped still child rejected");}
 reset();read_chunk=7;check(test_call_install(VIEW,VM,0)==0,"fragmented maps reads handled");
 reset();check(maps(),"initial maps parsed");map_text="40000000-40c00000 r-xp 00000000 00:00 1 /usr/lib/viewUnified2.so\n";check(!maps()&&!boot.caution&&!boot.backup,"missing later libraries cannot reuse stale bases");
 reset();map_text="40000000-40c00000 r-xp 00000000 00:00 1 /usr/lib/viewUnified2.so\n50000000-50b00000 r-xp 00000000 00:00 2 /usr/lib/CautionConfig.so\n60000000-60010000 r-xp 00000000 00:00 3 /usr/lib/libbackup.so.bak\n70000000-71000000 rw-p 00000000 00:00 0 [heap]\n";
 check(!maps(),"lookalike mapped filename rejected");
 reset();check(test_call_install(VIEW,(void *)1,1)==0,"prepare stable library bases");
 map_text="40000000-40c00000 r-xp 00000000 00:00 1 /usr/lib/viewUnified2.so\n52000000-52b00000 r-xp 00000000 00:00 2 /usr/lib/CautionConfig.so\n60000000-60010000 r-xp 00000000 00:00 3 /usr/lib/libbackup.so\n70000000-71000000 rw-p 00000000 00:00 0 [heap]\n";
 memcpy((void *)0x5268338c,a7_pin_ctor,16);memcpy((void *)0x526830aa,a7_pin_init,16);
 check(test_call_install(VIEW,(void *)1,1)!=0&&color_calls==1,"changed library base rejects before cached platform call");
 reset();map_text="40000000-40000000 r-xp 00000000 00:00 1 /usr/lib/viewUnified2.so\n";check(!maps(),"empty mapping rejected");
 reset();map_text="100000000-100000010 r-xp 00000000 00:00 1 /usr/lib/viewUnified2.so\n";check(!maps(),"overflowing mapping rejected");
 reset();check(maps(),"span fixture maps");check(span(0,VIEW,16)&&!span(0,0,4)&&!span(0,0xfffffffcu,8)&&!span(0,0x40bffffc,8),"mapped-span boundaries and overflow");
 memset(map_buffer,0,sizeof map_buffer);append(map_buffer,valid_maps);append(map_buffer,"72000000-72001000 rw-p 00000000 00:00 0 /dev/test\n73000000-73001000 r--p 00000000 00:00 1 /usr/share/table\n74000000-74001000 rw-s 00000000 00:00 1 [shared]\n");map_text=map_buffer;
 check(maps()&&!span(0,0x72000000,4)&&!span(0,0x73000000,4)&&!span(0,0x74000000,4),"device/resource/shared maps excluded");
 reset();for(unsigned fail=1;fail<=3;fail++){reset();fail_at=fail;check(test_call_install(VIEW,VM,0)!=0&&!install_calls,"maps syscall failure rejects");}
 put("NATIVE_BOOTSTRAP_CHECKS ");number(checks);put("\nNATIVE_BOOTSTRAP_TESTS_PASSED\n");finish();
}
