#include "a7-fl-sd-files.h"
#include "a7-fl-sd-recipe.h"
int a7_sd_list_files(const struct a7_sd_api *api,char drive,struct a7_sd_list *list){
 if(!api||!api->first||!api->next||!api->drive_info||!list||drive<'A'||drive>'Z')return -1;
 union {uint64_t align;unsigned char raw[2088];} info;
 char root[]="A:/*";root[0]=drive;list->count=0;
 int rc=api->first(root,128,info.raw);
 if(rc)return rc==2?0:rc;
 const unsigned char *device=api->drive_info(info.raw);
 if(!device||device[10]<'A'||device[10]>'Z')return -2;
 char internal=(char)device[10];
 for(unsigned visited=0;visited<1024;visited++){
  const char *name=*(const char**)info.raw;
  if(!name)return -2;
  if(a7_fl_sd_recipe_name(name)){
   if(list->count==A7_SD_FILES)return -3;
   list->internal[list->count]=internal;
   char *path=list->paths[list->count++];
   path[0]=drive;path[1]=':';path[2]='/';
   unsigned i=0;do{path[i+3]=name[i];}while(name[i++]);
  }
  rc=api->next(info.raw);
  if(rc==2)return 0; /* Measured on all three mounted drives. */
  if(rc){list->count=0;return rc;}
 }
 return -4;
}
int a7_sd_read_file(const struct a7_sd_api *api,const char *path,char internal,
 unsigned char *data,unsigned *size){
 if(!api||!api->open||!api->read||!api->close||!api->eof||!api->error||
    !api->first||!api->drive_info||!path||!data||!size)return -1;
 *size=0;
 if(path[0]<'A'||path[0]>'Z'||path[1]!=':'||path[2]!='/'||
    !a7_fl_sd_recipe_name(path+3))return -1;
 union {uint64_t align;unsigned char raw[2088];} info;
 char root[]="A:/*";root[0]=path[0];
 if(api->first(root,128,info.raw))return -2;
 const unsigned char *device=api->drive_info(info.raw);
 if(!device||device[10]!=(unsigned char)internal)return -2;
 char translated[260];unsigned j=0;
 do{translated[j]=path[j];}while(path[j++]);
 translated[0]=internal;
 void *file=api->open(translated,"rb");if(!file)return -2;
 unsigned n=0;int rc=0;
 while(n<A7_SD_BYTES){
  unsigned got=api->read(data+n,1,A7_SD_BYTES-n,file);
  if(got>A7_SD_BYTES-n){rc=-3;break;}
  int error=api->error(file),eof=api->eof(file);
  /* This PrFILE implementation reports code 8 for a normal EOF. */
  if(error && !(error==8&&eof==1)){rc=-7;break;}
  if(!got){if(api->eof(file)<=0)rc=-8;break;}
  n+=got;
 }
 if(!rc&&n==A7_SD_BYTES){
  unsigned char extra;if(api->read(&extra,1,1,file))rc=-4;
  else {
   int error=api->error(file);
   if(api->eof(file)!=1||(error&&error!=8))rc=-7;
  }
 }
 if(api->close(file))rc=-5;
 if(!n&&!rc)rc=-6;
 if(!rc)*size=n;
 return rc;
}
