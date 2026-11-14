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
#include "../payloads/a7-fl-posix.h"
static char directory[256];static int fail_sync;
#ifdef A7_FL_FILM_CONTROLS
static unsigned dir_syncs,fail_dir_sync;
#endif
static void path(char *out,const char *in){assert(!strncmp(in,"/setting/",9));snprintf(out,512,"%s/%s",directory,in+9);}
long a7_fl_test_syscall(long nr,long a,long b,long c) {
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
    strcpy(directory,"/private/tmp/a7-fl-posix-XXXXXX");assert(mkdtemp(directory));
    struct a7_fl_store_io io;a7_fl_posix_io(&io);
    unsigned char a[128],b[128],readback[129];for(unsigned i=0;i<128;i++){a[i]=(unsigned char)i;b[i]=(unsigned char)(255-i);}
    unsigned n=77;assert(io.read(0,0,readback,129,&n)==1&&n==0);
    assert(!io.replace(0,0,0,0,0,a));assert(!io.read(0,0,readback,129,&n)&&n==128&&!memcmp(a,readback,128));
    assert(io.replace(0,0,0,0,0,b)!=0); /* O_EXCL */
    assert(io.replace(0,0,b,128,1,b)!=0); /* Exact preimage */
    assert(!io.replace(0,0,a,128,1,b));
    fail_sync=1;assert(io.replace(0,0,b,128,1,a)!=0);fail_sync=0;
    char p0[512],p1[512];path(p0,"/setting/A7FL0.CFG");path(p1,"/setting/A7FL1.CFG");
    assert(!symlink(p0,p1));assert(io.read(0,1,readback,129,&n)<0);assert(io.replace(0,1,a,128,1,b)!=0);assert(!unlink(p1));
    assert(!mkdir(p1,0700));assert(io.read(0,1,readback,129,&n)<0);assert(!rmdir(p1));
    int fd=open(p1,O_CREAT|O_EXCL|O_WRONLY,0600);assert(fd>=0);assert(!ftruncate(fd,130));assert(!close(fd));
    assert(io.read(0,1,readback,129,&n)<0);assert(io.replace(0,1,a,128,1,b)!=0);
    assert(!unlink(p0));assert(!unlink(p1));
#ifdef A7_FL_FILM_CONTROLS
    struct a7_fl_store_io work;a7_fl_posix_worklog_io(&work);
    assert(!work.replace(work.opaque,0,0,0,0,b));
    assert(io.read(io.opaque,0,readback,129,&n)==1);
    assert(!work.read(work.opaque,0,readback,129,&n)&&n==128&&!memcmp(readback,b,128));
    assert(dir_syncs==2);
    fail_dir_sync=1;assert(work.replace(work.opaque,1,0,0,0,b)<0&&dir_syncs==3);
    path(p0,"/setting/A7FW0.CFG");path(p1,"/setting/A7FW1.CFG");
    assert(!unlink(p0));assert(!unlink(p1));
#endif
    assert(!rmdir(directory));
    puts("NATIVE_POSIX_PASSED actual file create/read/replace/fsync, exact preimages, symlink/directory/oversize rejection");
}
