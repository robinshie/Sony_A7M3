#include "a7-fl-custom.h"
static void zero(void*p,unsigned n){unsigned char*b=p;while(n--)*b++=0;}
static int eq(const char*a,const char*b){while(*a&&*a==*b){a++;b++;}return *a==*b;}
static const char*fields[16]={"contrast","highlights","shadows","fade","saturation","sharpness","sharpness_range","clarity","grain","halation","black","curve_shadow","midtone","curve_highlight","white","vignette"};
static const int low[16]={-9,-9,-9,0,-9,-3,1,0,0,-9,-9,-9,-9,-9,-9,-9};
static const int high[16]={9,9,9,9,9,3,5,9,9,9,9,9,9,9,9,9};
struct reader{const unsigned char*p,*end;};
static void ws(struct reader*r){while(r->p<r->end&&(*r->p==' '||*r->p=='\n'||*r->p=='\r'||*r->p=='\t'))r->p++;}
static int take(struct reader*r,unsigned c){ws(r);if(r->p==r->end||*r->p!=c)return 0;r->p++;return 1;}
/* Require canonical UTF-8; reject overlong, surrogate and out-of-range encodings. */
static int utf8(const unsigned char*s,unsigned n){
 for(unsigned i=0;i<n;){unsigned c=s[i++],k,min,x;
  if(c<32||c==127)return 0;
  if(c<128)continue;
  if(c>=0xc2&&c<=0xdf){k=1;min=0x80;x=c&31;}
  else if(c>=0xe0&&c<=0xef){k=2;min=0x800;x=c&15;}
  else if(c>=0xf0&&c<=0xf4){k=3;min=0x10000;x=c&7;}else return 0;
  if(k>n-i)return 0;
  while(k--){c=s[i++];if((c&0xc0)!=0x80)return 0;x=(x<<6)|(c&63);}
  if(x<min||x>0x10ffff||(x>=0xd800&&x<=0xdfff))return 0;
 }return 1;
}
static int string(struct reader*r,char*out,unsigned cap){
 if(!take(r,'"'))return 0;
 unsigned n=0;
 while(r->p<r->end&&*r->p!='"'){
  unsigned c=*r->p++;
  if(c=='\\'){if(r->p==r->end)return 0;c=*r->p++;if(c!='"'&&c!='\\'&&c!='/')return 0;}
  if(n+1>=cap)return 0;
  out[n++]=(char)c;
 }
 if(!take(r,'"')||!utf8((unsigned char*)out,n))return 0;
 out[n]=0;return 1;
}
static int number(struct reader*r,int*out){
 ws(r);int sign=1,v=0;unsigned n=0;
 if(r->p<r->end&&*r->p=='-'){sign=-1;r->p++;}
 if(r->p==r->end)return 0;
 const unsigned char*first=r->p;
 while(r->p<r->end&&*r->p>='0'&&*r->p<='9'){
  if(++n>2)return 0;
  v=v*10+*r->p++-'0';
 }
 if(!n||(n>1&&*first=='0'))return 0;
 *out=sign*v;return 1;
}
static int valid_look(const struct a7_custom_look*l){
 if(!l||l->base<1||l->base>6)return 0;
 unsigned n=0;
 while(n<49&&l->id[n]){unsigned c=(unsigned char)l->id[n];if(!((c>='a'&&c<='z')||(c>='0'&&c<='9')||(n&&(c=='_'||c=='-'))))return 0;n++;}
 if(!n||n>=49)return 0;
 n=0;while(n<64&&l->name[n])n++;
 if(!n||n>=64||l->name[0]==' '||l->name[n-1]==' '||!utf8((const unsigned char*)l->name,n))return 0;
 for(unsigned i=0;i<16;i++)if(l->values[i]<low[i]||l->values[i]>high[i])return 0;
 return 1;
}
int a7_custom_parse(const unsigned char*data,unsigned n,struct a7_custom_look*out){
 if(!data||!out||!n||n>16384)return -1;
 struct reader r={data,data+n};struct a7_custom_look l;zero(&l,sizeof l);unsigned seen=0;
 if(n>=3&&data[0]==239&&data[1]==187&&data[2]==191)r.p+=3;
 if(!take(&r,'{'))return -1;
 for(unsigned k=0;k<5;k++){
  char key[32],value[64]={0};unsigned bit=0;
  if(k&&!take(&r,','))return -1;
  if(!string(&r,key,sizeof key)||!take(&r,':'))return -1;
  if(eq(key,"parameters")){
   bit=16;if(!take(&r,'{'))return -1;unsigned mask=0;
   for(unsigned f=0;f<16;f++){
    char field[32];int v;
    if(f&&!take(&r,','))return -1;
    if(!string(&r,field,sizeof field)||!take(&r,':')||!number(&r,&v))return -1;
    unsigned j=0;while(j<16&&!eq(field,fields[j]))j++;
    if(j==16||(mask&(1u<<j))||v<low[j]||v>high[j])return -1;
    mask|=1u<<j;l.values[j]=(int8_t)v;
   }
   if(!take(&r,'}'))return -1;
  }else{
   if(!string(&r,value,sizeof value))return -1;
   if(eq(key,"format")){bit=1;if(!eq(value,"A7FL-LOOK/1"))return -1;}
   else if(eq(key,"id")){bit=2;unsigned i=0;do{if(i>=sizeof l.id)return -1;l.id[i]=value[i];}while(value[i++]);}
   else if(eq(key,"name")){bit=4;for(unsigned i=0;i<sizeof value;i++)l.name[i]=value[i];}
   else if(eq(key,"base")){bit=8;if(eq(value,"FL"))l.base=1;else if(value[0]=='F'&&value[1]=='L'&&value[2]>='2'&&value[2]<='6'&&!value[3])l.base=(uint8_t)(value[2]-'0');else return -1;}
   else return -1;
  }
  if(seen&bit)return -1;
  seen|=bit;
 }
 if(!take(&r,'}'))return -1;
 ws(&r);if(r.p!=r.end||seen!=31||!valid_look(&l))return -1;
 *out=l;return 0;
}
void a7_custom_empty(struct a7_custom_catalog*c){zero(c,sizeof*c);c->next_slot=7;}
static int valid(const struct a7_custom_catalog*c){
 if(!c||c->count>A7_CUSTOM_MAX||c->next_slot!=7+c->count||c->generation==0xffffffffu)return 0;
 unsigned active=!c->active;
 for(unsigned i=0;i<c->count;i++){
  const struct a7_custom_look*l=c->looks+i;
  if(!valid_look(l)||l->slot!=7+i||l->slot>=c->next_slot)return 0;
  active|=c->active==l->slot;
  for(unsigned j=0;j<i;j++)if(l->slot==c->looks[j].slot||eq(l->id,c->looks[j].id))return 0;
 }return active;
}
int a7_custom_append(const struct a7_custom_catalog*c,const struct a7_custom_look*l,struct a7_custom_catalog*out){
 if(!valid(c)||!valid_look(l)||!out||c->count>=A7_CUSTOM_MAX||c->generation>=0xfffffffeu||c->next_slot>=0xfffffffeu)return -1;
 for(unsigned i=0;i<c->count;i++)if(eq(l->id,c->looks[i].id))return -2;
 struct a7_custom_catalog next=*c;next.looks[next.count]=*l;next.looks[next.count++].slot=next.next_slot++;next.generation++;*out=next;return 0;
}
static void put(unsigned char*p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(v>>(8*i));}
static uint32_t get(const unsigned char*p){return p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
static uint32_t crc(const unsigned char*p,unsigned n){uint32_t v=~0u;while(n--){v^=*p++;for(unsigned i=0;i<8;i++)v=(v>>1)^((0u-(v&1))&0xedb88320u);}return ~v;}
int a7_custom_encode(const struct a7_custom_catalog*c,unsigned char out[A7_CUSTOM_RECORD_BYTES]){
 if(!out||!valid(c))return -1;
 zero(out,A7_CUSTOM_RECORD_BYTES);const char*magic="A7CUSTOM";
 for(unsigned i=0;i<8;i++)out[i]=(unsigned char)magic[i];
 put(out+8,1);put(out+12,c->generation);put(out+16,c->next_slot);put(out+20,c->active);put(out+24,c->count);
 for(unsigned i=0;i<c->count;i++){
  unsigned char*p=out+28+i*176;const struct a7_custom_look*l=c->looks+i;put(p,l->slot);p[4]=l->base;
  for(unsigned j=0;l->id[j];j++)p[8+j]=(unsigned char)l->id[j];
  for(unsigned j=0;l->name[j];j++)p[57+j]=(unsigned char)l->name[j];
  for(unsigned j=0;j<16;j++)p[121+j]=(unsigned char)l->values[j];
 }
 put(out+A7_CUSTOM_RECORD_BYTES-4,crc(out,A7_CUSTOM_RECORD_BYTES-4));return 0;
}
int a7_custom_decode(const unsigned char*data,unsigned n,struct a7_custom_catalog*out){
 if(!data||!out||n!=A7_CUSTOM_RECORD_BYTES||get(data+8)!=1||get(data+n-4)!=crc(data,n-4))return -1;
 const char*magic="A7CUSTOM";for(unsigned i=0;i<8;i++)if(data[i]!=(unsigned char)magic[i])return -1;
 struct a7_custom_catalog c;zero(&c,sizeof c);c.generation=get(data+12);c.next_slot=get(data+16);c.active=get(data+20);c.count=get(data+24);
 if(c.count>A7_CUSTOM_MAX)return -1;
 for(unsigned i=0;i<c.count;i++){
  const unsigned char*p=data+28+i*176;struct a7_custom_look*l=c.looks+i;l->slot=get(p);l->base=p[4];
  for(unsigned j=0;j<49;j++)l->id[j]=(char)p[8+j];
  for(unsigned j=0;j<64;j++)l->name[j]=(char)p[57+j];
  for(unsigned j=0;j<16;j++)l->values[j]=(int8_t)p[121+j];
 }
 if(!valid(&c))return -1;
 unsigned char canonical[A7_CUSTOM_RECORD_BYTES];if(a7_custom_encode(&c,canonical))return -1;
 for(unsigned i=0;i<n;i++)if(canonical[i]!=data[i])return -1;
 *out=c;return 0;
}
int a7_custom_resolve(const struct a7_custom_catalog*c,uint32_t slot,struct a7_custom_look*out){
 if(!out||!valid(c))return -1;
 for(unsigned i=0;i<c->count;i++)if(c->looks[i].slot==slot){*out=c->looks[i];return 0;}
 return -1;
}
