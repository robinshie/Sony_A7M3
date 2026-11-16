/* Execute production I/O against real temporary files via an ARM syscall shim. */
#define _DARWIN_C_SOURCE
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
#include "../payloads/a7-fl-custom-store.h"
static char directory[256];static int fail_sync;
#ifdef A7_RECIPE_TEST
int a7_fl_import_slot(const struct a7_fl_store_io *,const struct a7_fl_store_io *,
                      const uint8_t [4][128],unsigned,const uint8_t [128]);
#endif
#ifdef A7_FL_FILM_CONTROLS
static unsigned dir_syncs,fail_dir_sync;
#endif
static void path(char *out,const char *in){assert(!strncmp(in,"/setting/",9));snprintf(out,512,"%s/%s",directory,in+9);}
long a7_custom_test_syscall(long nr,long a,long b,long c) {
    long rc=-1;
    if(nr==5){
        char name[512];
        if(!strcmp((const char *)a,"/setting")){assert(b&0x4000);strcpy(name,directory);}
        else path(name,(const char *)a);
        /* These are ARM Linux UAPI values, deliberately independent of host. */
        assert(!(b&0x20000));
        int flags=(b&3)|((b&64)?O_CREAT:0)|((b&128)?O_EXCL:0)|((b&0x8000)?O_NOFOLLOW:0)|((b&0x800)?O_NONBLOCK:0)|((b&0x4000)?O_DIRECTORY:0);
        rc=open(name,flags,(mode_t)c);
    }else if(nr==3)rc=read((int)a,(void *)b,(size_t)c);
    else if(nr==4)rc=write((int)a,(void *)b,(size_t)c);
    else if(nr==6)rc=close((int)a);
    else if(nr==19)rc=lseek((int)a,b,(int)c);
    else if(nr==93)rc=ftruncate((int)a,b);
    else if(nr==118){
        int fail=fail_sync;
#ifdef A7_FL_FILM_CONTROLS
        struct stat st;assert(!fstat((int)a,&st));
        if(S_ISDIR(st.st_mode)){++dir_syncs;fail|=fail_dir_sync;}
#endif
        if(fail){errno=EIO;rc=-1;}else rc=fsync((int)a);
    }
    else if(nr==197){
        struct stat st;rc=fstat((int)a,&st);
        if(!rc){unsigned char *p=(void *)b;memset(p,0,104);
            for(unsigned i=0;i<4;i++)p[16+i]=(unsigned char)((uint32_t)st.st_mode>>(8*i));
            for(unsigned i=0;i<8;i++)p[48+i]=(unsigned char)((uint64_t)st.st_size>>(8*i));}
    }else assert(!"Unexpected syscall");
    return rc<0?-errno:rc;
}
int main(void){
 strcpy(directory,"/private/tmp/a7-custom-posix-XXXXXX");assert(mkdtemp(directory));
 struct a7_custom_io io;extern void a7_custom_posix_io(struct a7_custom_io*);a7_custom_posix_io(&io);
 unsigned char a[A7_CUSTOM_RECORD_BYTES],b[A7_CUSTOM_RECORD_BYTES],out[A7_CUSTOM_RECORD_BYTES+1];
 memset(a,1,sizeof a);memset(b,2,sizeof b);unsigned n=77;
 assert(io.read(0,0,out,sizeof out,&n)==1&&n==0);
 assert(!io.replace(0,0,0,0,0,a,sizeof a));assert(!io.read(0,0,out,sizeof out,&n)&&n==sizeof a&&!memcmp(a,out,n));
 assert(io.replace(0,0,0,0,0,b,sizeof b)<0);assert(io.replace(0,0,b,sizeof b,1,b,sizeof b)<0);
 assert(!io.replace(0,0,a,sizeof a,1,b,sizeof b));
 fail_sync=1;assert(io.replace(0,0,b,sizeof b,1,a,sizeof a)<0);fail_sync=0;
 char p0[512],p1[512];path(p0,"/setting/A7CU0.CFG");path(p1,"/setting/A7CU1.CFG");
 assert(!symlink(p0,p1));assert(io.read(0,1,out,sizeof out,&n)<0);assert(io.replace(0,1,a,sizeof a,1,b,sizeof b)<0);assert(!unlink(p1));
 assert(!mkdir(p1,0700));assert(io.read(0,1,out,sizeof out,&n)<0);assert(!rmdir(p1));
 int fd=open(p1,O_CREAT|O_EXCL|O_WRONLY,0600);assert(fd>=0);assert(!ftruncate(fd,sizeof out+1));assert(!close(fd));
 assert(io.read(0,1,out,sizeof out,&n)<0);assert(!unlink(p1));
 fail_dir_sync=1;assert(io.replace(0,1,0,0,0,b,sizeof b)<0);assert(dir_syncs==2);
 assert(!io.read(0,0,out,sizeof out,&n)&&n==sizeof a&&!memcmp(a,out,n));
 assert(!unlink(p0));assert(!unlink(p1));assert(!rmdir(directory));
 puts("CUSTOM_POSIX_PASSED real files, preimages, exclusive create, fsync failure, symlink and size rejection");
}
