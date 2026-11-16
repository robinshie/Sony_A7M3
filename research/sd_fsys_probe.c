/* Read-only query of the already loaded original Fsys library. */
#include <stdint.h>
extern void *dlopen(const char *,int);
extern void *dlsym(void *,const char *);
extern int dlclose(void *);
static long sc(long n,long a,long b,long c){
 register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
static struct {uint32_t magic;int status;uint32_t drives;
 int opened[3],read[3],closed[3];unsigned char bytes[3][25];
 int listing[3]; char names[3][16][256];int ends[3],eof,error;
} report={.magic=0x53444653,.status=-1};
__attribute__((constructor))static void run(void){
 void *h=dlopen("/usr/lib/libInfraFsys.so",6);
 if(h){
  uint32_t (*get)(void)=(void *)dlsym(h,"Fsys_GetMountDrives");
  if(get){report.drives=get();report.status=0;}else report.status=-2;

  int (*first)(const char*,unsigned,void*)=(void*)dlsym(h,"Fsys_FindFirst");
  int (*next)(void*)=(void*)dlsym(h,"Fsys_FindNext");
  void *(*long_open)(const char*,const char*)=(void*)dlsym(h,"pf2_fopen");
  unsigned (*long_read)(void*,unsigned,unsigned,void*)=(void*)dlsym(h,"pf2_fread");
  int (*long_close)(void*)=(void*)dlsym(h,"pf2_fclose");
  int (*long_eof)(void*)=(void*)dlsym(h,"pf2_feof");
  int (*long_error)(void*)=(void*)dlsym(h,"pf2_ferror");
  const unsigned char *(*drive_info)(void*)=(void*)dlsym(h,"GetDriveInfoFromFindInfo");
  if(first&&next){
   for(unsigned i=0;i<3;i++){
    union {uint64_t align;unsigned char bytes[2088];} info;
    char path[]="A:/*";path[0]=(char)('A'+i);
    int rc=first(path,128,info.bytes);report.listing[i]=rc;
    char internal=0;
    if(!rc&&drive_info){
     const unsigned char *d=drive_info(info.bytes);
     if(d)internal=(char)d[10];
    }
    for(unsigned n=0;!rc&&n<16;n++){
     const char *name=*(const char**)info.bytes;
     if(!name){report.listing[i]=-998;break;}
     unsigned k=0;for(;k<255&&name[k];k++)report.names[i][n][k]=name[k];
     report.names[i][n][k]=0;
     rc=next(info.bytes);
    }
    report.ends[i]=rc;
    report.opened[i]=report.read[i]=report.closed[i]=-999;
    int found=0;
    for(unsigned n=0;n<16;n++){
     const char *want="FL6-grain-1.a7look";unsigned k=0;
     while(want[k]&&report.names[i][n][k]==want[k])k++;
     if(!want[k]&&!report.names[i][n][k])found=1;
    }
    if(found&&report.listing[i]==0&&long_open&&long_read&&long_close){
     char full[]="A:/FL6-grain-1.a7look";
     if(internal<'A'||internal>'Z')continue;
     full[0]=internal;
     void *file=long_open(full,"rb");
     report.opened[i]=file?0:-1;
     if(file){
      report.read[i]=(int)long_read(report.bytes[i],1,25,file);
      if(long_eof&&long_error){
       unsigned char extra;long_read(&extra,1,1,file);
       report.eof=long_eof(file);report.error=long_error(file);
      }
      report.closed[i]=long_close(file);
     }
    }
   }
  }
  dlclose(h);
 }
 long fd=sc(5,(long)"/tmp/jiritsu/sdfsys.bin",1|64|128,0600);
 if(fd<0)return;
 sc(4,fd,(long)&report,sizeof report);sc(6,fd,0,0);
}
