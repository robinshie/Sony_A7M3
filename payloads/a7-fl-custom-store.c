#include "a7-fl-custom-store.h"
static int equal(const unsigned char*a,const unsigned char*b,unsigned n){while(n--)if(*a++!=*b++)return 0;return 1;}
int a7_custom_store_open(struct a7_custom_store*s,const struct a7_custom_io*io,struct a7_custom_catalog*out){
 if(!s||!io||!io->read||!io->replace||!out)return -1;
 s->ready=0;s->io=*io;s->selected=-1;
 struct a7_custom_catalog c[2];int valid[2]={0};
 for(unsigned i=0;i<2;i++){
  unsigned n=0;int rc=io->read(io->opaque,i,s->bytes[i],A7_CUSTOM_RECORD_BYTES,&n);
  if(rc<0||rc>1||n>A7_CUSTOM_RECORD_BYTES||(rc==1&&n))return -2;
  s->exists[i]=rc==0;s->sizes[i]=n;
  if(!rc)valid[i]=!a7_custom_decode(s->bytes[i],n,c+i);
 }
 if(!s->exists[0]&&!s->exists[1]){a7_custom_empty(out);s->ready=1;return 0;}
 if(!valid[0]&&!valid[1])return -3;
 if(valid[0]&&valid[1]&&c[0].generation==c[1].generation&&!equal(s->bytes[0],s->bytes[1],A7_CUSTOM_RECORD_BYTES))return -4;
 s->selected=valid[1]&&(!valid[0]||c[1].generation>c[0].generation)?1:0;
 *out=c[s->selected];
 /* Recover a surviving slot read-only; never overwrite an unknown/torn peer. */
 s->ready=(!s->exists[0]||valid[0])&&(!s->exists[1]||valid[1]);return s->ready?0:1;
}
int a7_custom_store_save(struct a7_custom_store*s,const struct a7_custom_catalog*next){
 if(!s||!s->ready||!next)return -1;
 unsigned char encoded[A7_CUSTOM_RECORD_BYTES],check[A7_CUSTOM_RECORD_BYTES];
 if(a7_custom_encode(next,encoded))return -2;
 struct a7_custom_catalog old;
 if(s->selected>=0){
  if(a7_custom_decode(s->bytes[s->selected],s->sizes[s->selected],&old)||old.generation>=0xfffffffeu||next->generation!=old.generation+1)return -3;
 }else if(next->generation!=1)return -3;
 for(unsigned i=0;i<2;i++){
  unsigned n=0;int rc=s->io.read(s->io.opaque,i,check,sizeof check,&n);
  if(rc!=(s->exists[i]?0:1)||n!=s->sizes[i]||!equal(check,s->bytes[i],n))return -4;
 }
 unsigned target=s->selected<0?0:1-(unsigned)s->selected;
 if(s->io.replace(s->io.opaque,target,s->bytes[target],s->sizes[target],s->exists[target],encoded,sizeof encoded)){s->ready=0;return -5;}
 for(unsigned i=0;i<2;i++){
  unsigned n=0;int rc=s->io.read(s->io.opaque,i,check,sizeof check,&n);
  unsigned want=i==target?sizeof encoded:s->sizes[i];
  if(rc!=((i==target||s->exists[i])?0:1)||n!=want||!equal(check,i==target?encoded:s->bytes[i],want)){s->ready=0;return -6;}
 }
 for(unsigned i=0;i<sizeof encoded;i++)s->bytes[target][i]=encoded[i];
 s->sizes[target]=sizeof encoded;s->exists[target]=1;s->selected=(int)target;return 0;
}
