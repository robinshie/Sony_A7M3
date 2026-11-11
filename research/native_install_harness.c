/* Host syscall shim: inject one failure at every syscall in a successful run. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "native_install.h"
#include "../payloads/sha256.h"
typedef struct {unsigned char data[16384];unsigned size,synced;} Node;
typedef struct {char path[128];int node;} Entry;
typedef struct {int open,node,write;unsigned position;char path[128];} FD;
static Node nodes[32];static Entry entries[32];static FD fds[64];static unsigned node_count,entry_count,calls,fail_at,checks;
static int readonly_mount,fail_ro,block_readonly,short_io;
static NativeInstallBundle bundle;static unsigned char expected[32],module[128],zh[128],en[128],oldzh[64],olden[64],view[128];
static const char *targets[3]={"/usr/lib/a7fl.so","/usr/share/app/string_simplifiedchinese.uxc","/usr/share/app/string_english.uxc"};
static void check(int ok,const char *what){checks++;if(!ok){fprintf(stderr,"FAIL %s at injected syscall %u / call %u\n",what,fail_at,calls);exit(1);}}
static void digest(const unsigned char *data,unsigned n,unsigned char out[32]){Sha256 h;sha_init(&h);sha_update(&h,data,n);sha_finish(&h,out);}
static int find(const char *path){for(unsigned j=0;j<entry_count;j++)if(entries[j].path[0]&&!strcmp(entries[j].path,path))return (int)j;return -1;}
static int add(const char *path,const void *data,unsigned n){int e=(int)entry_count++,k=(int)node_count++;check(e<32&&k<32,"mock capacity");strcpy(entries[e].path,path);entries[e].node=k;nodes[k].size=n;nodes[k].synced=1;if(n)memcpy(nodes[k].data,data,n);return e;}
static int exact(const char *path,const void *data,unsigned n){int e=find(path);return e>=0&&nodes[entries[e].node].size==n&&!memcmp(nodes[entries[e].node].data,data,n);}
static void reset(void){memset(nodes,0,sizeof nodes);memset(entries,0,sizeof entries);memset(fds,0,sizeof fds);node_count=entry_count=calls=0;readonly_mount=1;fail_ro=block_readonly=short_io=0;add(targets[1],oldzh,sizeof oldzh);add(targets[2],olden,sizeof olden);add("/usr/lib/viewUnified2.so",view,sizeof view);}
static long syscall_shim(void *context,long nr,long a,long b,long c,long d,long e,long f){
    (void)context;(void)e;(void)f;calls++;
    if(calls==fail_at){if(nr==6&&a>=0&&a<64)fds[a].open=0;return -5;}
    if(nr==49)return 0;
    if(nr==184){uint32_t *p=(uint32_t *)b;for(unsigned j=0;j<6;j++)p[j]=0xffffffff;return 0;}
    if(nr==99){uint32_t *s=(uint32_t *)b;memset(s,0,64);s[0]=0xef53;s[1]=1024;s[2]=205449;s[3]=s[4]=9567;s[6]=52330;s[11]=readonly_mount?4129:4128;return 0;}
    if(nr==54){check(b==0x125e,"only read-only block ioctl");*(int *)c=block_readonly;return 0;}
    if(nr==21){check(!strcmp((char *)a,"/dev/nflasha15")&&!strcmp((char *)b,"/usr")&&!strcmp((char *)c,"ext2"),"only intended remount");if((d&1)&&fail_ro)return -5;readonly_mount=(int)(d&1);return 0;}
    if(nr==5){
        const char *path=(const char *)a;int node=-1,eidx=find(path);
        if(b&0x4000){if(strcmp(path,"/usr/lib")&&strcmp(path,"/usr/share/app")&&strcmp(path,"/setting"))return -2;node=-4;}
        else if(!strcmp(path,"/proc/mounts"))node=-2;
        else if(!strcmp(path,"/dev/nflasha15")){check(!(b&3),"block never writable");node=-3;}
        else if(b&64){if(eidx>=0)return -17;if(!strncmp(path,"/usr/",5)&&readonly_mount)return -30;eidx=add(path,0,0);nodes[entries[eidx].node].synced=0;node=entries[eidx].node;}
        else {if(eidx<0)return -2;node=entries[eidx].node;}
        for(int fd=3;fd<64;fd++)if(!fds[fd].open){fds[fd].open=1;fds[fd].node=node;fds[fd].position=0;fds[fd].write=(int)(b&1);strcpy(fds[fd].path,path);return fd;}return -24;
    }
    if(nr==6){if(a<0||a>=64||!fds[a].open)return -9;fds[a].open=0;return 0;}
    if(nr==3){
        if(a<0||a>=64||!fds[a].open)return -9;FD *fd=&fds[a];const unsigned char *data;unsigned size;
        const char *mount=readonly_mount?"/dev/nflasha15 /usr ext2 ro,relatime,errors=continue 0 0\n":"/dev/nflasha15 /usr ext2 rw,relatime,errors=continue 0 0\n";
        if(fd->node==-2){data=(const unsigned char *)mount;size=(unsigned)strlen(mount);}else if(fd->node<0)return -21;else{data=nodes[fd->node].data;size=nodes[fd->node].size;}
        unsigned n=size-fd->position;if(n>(unsigned)c)n=(unsigned)c;if(short_io&&n>17)n=17;memcpy((void *)b,data+fd->position,n);fd->position+=n;return n;
    }
    if(nr==4){
        if(a<0||a>=64||!fds[a].open||!fds[a].write)return -9;FD *fd=&fds[a];check(fd->node>=0,"write regular files only");
        check(strcmp(fd->path,"/usr/lib/viewUnified2.so")!=0,"view file never written");
        if(!strncmp(fd->path,"/usr/",5)&&readonly_mount)return -30;
        unsigned n=(unsigned)c;if(short_io&&n>13)n=13;Node *node=&nodes[fd->node];check(fd->position+n<=sizeof node->data,"mock data capacity");
        memcpy(node->data+fd->position,(void *)b,n);fd->position+=n;if(node->size<fd->position)node->size=fd->position;node->synced=0;return n;
    }
    if(nr==118){if(a<0||a>=64||!fds[a].open)return -9;if(fds[a].node>=0)nodes[fds[a].node].synced=1;return 0;}
    if(nr==9){if(readonly_mount)return -30;int old=find((char *)a);if(old<0)return -2;if(find((char *)b)>=0)return -17;check(nodes[entries[old].node].synced,"hardlinks only to fsynced complete files");int at=(int)entry_count++;check(at<32,"link capacity");strcpy(entries[at].path,(char *)b);entries[at].node=entries[old].node;return 0;}
    if(nr==10){if(!strncmp((char *)a,"/usr/",5)&&readonly_mount)return -30;int at=find((char *)a);if(at<0)return -2;entries[at].path[0]=0;return 0;}
    if(nr==38){if(readonly_mount)return -30;int from=find((char *)a),to=find((char *)b);if(from<0)return -2;check(nodes[entries[from].node].synced,"rename publishes complete synced inode");if(to>=0)entries[to].path[0]=0;strcpy(entries[from].path,(char *)b);return 0;}
    fprintf(stderr,"Unexpected syscall %ld\n",nr);exit(1);
}
static void invariant(const NativeInstallReport *r){
    check(exact("/usr/lib/viewUnified2.so",view,sizeof view),"view bytes unchanged");
    check(exact(targets[1],oldzh,sizeof oldzh)||exact(targets[1],zh,sizeof zh),"Chinese always complete old or new");
    check(exact(targets[2],olden,sizeof olden)||exact(targets[2],en,sizeof en),"English always complete old or new");
    for(unsigned j=3;j<64;j++)check(!fds[j].open,"all descriptors closed");
    if(r->rollback_ok){check(exact(targets[1],oldzh,sizeof oldzh)&&exact(targets[2],olden,sizeof olden)&&find(targets[0])<0,"claimed rollback restores originals and removes module");}
    if(r->status==0){check(readonly_mount&&r->readonly_confirmed,"success read-only confirmed");check(exact(targets[0],module,sizeof module)&&exact(targets[1],zh,sizeof zh)&&exact(targets[2],en,sizeof en),"success files match bundle");}
}
int main(void){
    for(unsigned j=0;j<128;j++){module[j]=(unsigned char)j;zh[j]=(unsigned char)(j+3);en[j]=(unsigned char)(j+7);view[j]=(unsigned char)(j+19);}
    memcpy(module,"\177ELF\1\1\1",7);memcpy(module+16,"\3\0\50\0",4);
    for(unsigned j=0;j<64;j++){oldzh[j]=(unsigned char)(j+31);olden[j]=(unsigned char)(j+53);}
    bundle.version=1;bundle.module_attestation[0]=1;bundle.files[0]=(NativeInstallFile){module,sizeof module,{0}};bundle.files[1]=(NativeInstallFile){zh,sizeof zh,{0}};bundle.files[2]=(NativeInstallFile){en,sizeof en,{0}};
    for(unsigned j=0;j<3;j++)digest(bundle.files[j].bytes,bundle.files[j].size,bundle.files[j].sha256);
    bundle.old_locale_sizes[0]=sizeof oldzh;bundle.old_locale_sizes[1]=sizeof olden;bundle.view_size=sizeof view;
    digest(oldzh,sizeof oldzh,bundle.old_locale_sha[0]);digest(olden,sizeof olden,bundle.old_locale_sha[1]);digest(view,sizeof view,bundle.view_sha);native_install_bundle_sha(&bundle,expected);
    NativeInstallReport report;reset();fail_at=0;check(native_install_run(&bundle,expected,syscall_shim,0,&report)==0,"successful install");unsigned total=calls;invariant(&report);
    for(unsigned failure=1;failure<=total;failure++){
        reset();fail_at=failure;int rc=native_install_run(&bundle,expected,syscall_shim,0,&report);invariant(&report);
        check(rc!=0,"each injected syscall failure prevents success");check(readonly_mount,"single syscall fault ends read-only");
    }
    reset();fail_at=0;short_io=1;check(native_install_run(&bundle,expected,syscall_shim,0,&report)==0,"short read/write loops");invariant(&report);
    reset();fail_ro=1;check(native_install_run(&bundle,expected,syscall_shim,0,&report)==-4&&!report.readonly_confirmed,"persistent remount-ro failure reported");invariant(&report);
    reset();block_readonly=1;check(native_install_run(&bundle,expected,syscall_shim,0,&report)!=0&&readonly_mount&&find("/setting/A7FL.INSTALL")<0,"read-only block rejects before journal");invariant(&report);
    reset();bundle.placeholder=1;native_install_bundle_sha(&bundle,expected);check(native_install_run(&bundle,expected,syscall_shim,0,&report)!=0&&calls==0,"placeholder rejects before syscalls");bundle.placeholder=0;native_install_bundle_sha(&bundle,expected);
    reset();expected[0]^=1;check(native_install_run(&bundle,expected,syscall_shim,0,&report)!=0&&calls==0,"bundle digest mismatch rejects before syscalls");expected[0]^=1;
    reset();module[63]^=1;check(native_install_run(&bundle,expected,syscall_shim,0,&report)!=0&&calls==0,"modified module bytes reject before syscalls");module[63]^=1;
    reset();check(native_install_run(&bundle,expected,syscall_shim,0,&report)==0,"prepare retained journal");check(native_install_run(&bundle,expected,syscall_shim,0,&report)!=0,"repeat install rejects");
    printf("NATIVE_INSTALL_FAULT_POINTS %u\nNATIVE_INSTALL_CHECKS %u\nNATIVE_INSTALL_TESTS_PASSED\n",total,checks);return 0;
}
