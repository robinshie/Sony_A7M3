/* Read-only installation preflight. Does NOT remount, write /usr, or open the
 * block device writable. Only its temporary report is created when executed.
 * Source delivery alone does not claim that a live camera probe was run. */
#include <stdint.h>
static long call3(long n,long a,long b,long c) {
    register long nr __asm__("r7")=n;
    register long r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(nr),"r"(r1),"r"(r2):"memory","cc");
    return r0;
}
typedef struct {
    uint32_t type,block_size,blocks,free_blocks,available_blocks,files,free_files;
    uint32_t fsid[2],name_length,fragment_size,flags,spare[4];
} Statfs32;
static struct {
    uint32_t magic,version,bytes;
    int32_t uid,euid,cap_result,statfs_result,block_open,block_ro_result,block_read_only,mounts_bytes;
    uint32_t capability_header[2],capabilities[6];
    Statfs32 filesystem;
    char mounts[4096];
} result;
__attribute__((constructor)) static void probe(void) {
    result.magic=0x41374650;result.version=1;result.bytes=sizeof result;
    result.uid=call3(24,0,0,0);result.euid=call3(49,0,0,0);
    result.capability_header[0]=0x20080522;result.capability_header[1]=0;
    result.cap_result=call3(184,(long)result.capability_header,(long)result.capabilities,0);
    result.statfs_result=call3(99,(long)"/usr",(long)&result.filesystem,0);
    result.block_read_only=-1;
    long fd=call3(5,(long)"/dev/nflasha15",0,0);result.block_open=fd;
    if(fd>=0){result.block_ro_result=call3(54,fd,0x125e,(long)&result.block_read_only);call3(6,fd,0,0);}
    else result.block_ro_result=fd;
    fd=call3(5,(long)"/proc/mounts",0,0);
    if(fd<0)result.mounts_bytes=fd;
    else {
        while(result.mounts_bytes<(int)sizeof result.mounts){
            long n=call3(3,fd,(long)(result.mounts+result.mounts_bytes),sizeof result.mounts-result.mounts_bytes);
            if(n<=0){if(n<0)result.mounts_bytes=n;break;}result.mounts_bytes+=n;
        }
        if(result.mounts_bytes==sizeof result.mounts)result.mounts_bytes=-75;
        call3(6,fd,0,0);
    }
    fd=call3(5,(long)"/tmp/jiritsu/a7preflight.bin",1|64|128,0600);
    if(fd>=0){
        unsigned done=0;
        while(done<sizeof result){long n=call3(4,fd,(long)((char *)&result+done),sizeof result-done);if(n<=0)break;done+=n;}
        call3(118,fd,0,0);call3(6,fd,0,0);
    }
}
