#include "a7-fl-custom-text.h"
int a7_custom_text_paint(const struct a7_custom_text_api*a,void*root){
 if(!a||!root||!a->text||!a->resolve)return -1;
 unsigned painted=0;
 for(unsigned row=0;row<7;row++){
  unsigned char *button=(unsigned char*)root+0x3118+row*0x10a8;
  const unsigned offsets[2]={0x7a8,0xb18};
  for(unsigned i=0;i<2;i++){
   void*label=button+offsets[i];
   uint32_t id=*(const uint32_t*)((const unsigned char*)label+0x2dc);
   const char*s=a->resolve(id);
   if(s){a->text(label,s);painted++;}
  }
 }
 /* Native PAS_MenuListPopup at +0xbaa8 has six GEN_Label rows at
  * +0x1050, stride0x370; witnessed original construction/population. */
 for(unsigned row=0;row<6;row++){
  void*label=(unsigned char*)root+0xbaa8+0x1050+row*0x370;
  uint32_t id=*(const uint32_t*)((unsigned char*)label+0x2dc);
  const char*s=a->resolve(id);if(s){a->text(label,s);painted++;}
 }
 return (int)painted;
}
