#include "a7-fl-sd-recipe.h"
static const char *fields[16]={"contrast","highlights","shadows","fade","saturation",
 "sharpness","sharpness_range","clarity","grain","halation","black","curve_shadow",
 "midtone","curve_highlight","white","vignette"};
static const int low[16]={-9,-9,-9,0,-9,-3,1,0,0,-9,-9,-9,-9,-9,-9,-9};
static const int high[16]={9,9,9,9,9,3,5,9,9,9,9,9,9,9,9,9};
static int match(const unsigned char *p,unsigned n,const char *s){
 unsigned i=0;while(s[i]){if(i>=n||p[i]!=(unsigned char)s[i])return 0;i++;}return i==n;
}
int a7_fl_sd_recipe_name(const char *name){
 if(!name)return 0;
 if(name[0]=='.'&&name[1]=='_')return 0;
 unsigned n=0;while(name[n]){if(name[n]=='/'||name[n]=='\\'||n>=255)return 0;n++;}
 if(n<=7)return 0;
 const char *suffix=".a7look";
 for(unsigned i=0;i<7;i++){
  unsigned char c=(unsigned char)name[n-7+i];if(c>='A'&&c<='Z')c+=32;
  if(c!=(unsigned char)suffix[i])return 0;
 }return 1;
}
int a7_fl_sd_recipe_apply(const unsigned char *data,unsigned length,
 const struct a7_fl_preference *current,struct a7_fl_preference *next){
 if(!data||!current||!next||current->schema!=6||!length||length>16384)return -1;
 struct a7_fl_preference candidate=*current;
 unsigned seen[6]={0},pos=0,lines=0,changed=0,entries=0;
 if(length>=3&&data[0]==239&&data[1]==187&&data[2]==191)pos=3;
 while(pos<length){
  unsigned start=pos;while(pos<length&&data[pos]!='\n')pos++;
  unsigned end=pos;if(pos<length)pos++;
  if(end>start&&data[end-1]=='\r')end--;
  if(!lines++){if(!match(data+start,end-start,"A7FL-PATCH/1"))return -1;continue;}
  if(end==start)continue;
  unsigned p=start,bank=0;
  if(end-p<4||data[p++]!='F'||data[p++]!='L')return -1;
  if(data[p]>='2'&&data[p]<='6')bank=data[p++]-'1';
  if(data[p++]!='.')return -1;
  unsigned field_start=p;while(p<end&&data[p]!='=')p++;
  if(p==end)return -1;
  unsigned f=0;while(f<16&&!match(data+field_start,p-field_start,fields[f]))f++;
  if(f==16||(seen[bank]&(1u<<f)))return -1;
  seen[bank]|=1u<<f;p++;
  int sign=1,value=0;if(p<end&&data[p]=='-'){sign=-1;p++;}
  if(p==end)return -1;
  for(;p<end;p++){if(data[p]<'0'||data[p]>'9'||value>99)return -1;value=value*10+data[p]-'0';}
  value*=sign;if(value<low[f]||value>high[f])return -1;
  if(f<8){
   int mode=candidate.enabled;a7_fl_preference_switch(&candidate,(int)bank+1);
   changed|=candidate.parameters[f]!=value;candidate.parameters[f]=value;
   a7_fl_preference_switch(&candidate,mode);
  }else if(f==15){changed|=candidate.vignette[bank]!=value;candidate.vignette[bank]=value;}
  else{changed|=candidate.film[bank][f-8]!=value;candidate.film[bank][f-8]=value;}
  entries++;
 }
 if(!entries)return -1;
 *next=candidate;return changed?1:0;
}
