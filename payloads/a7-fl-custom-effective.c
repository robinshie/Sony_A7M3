#include "a7-fl-custom-effective.h"
int a7_custom_effective(const struct a7_custom_catalog*c,uint32_t slot,
 const struct a7_fl_preference*builtin,struct a7_fl_preference*out){
 if(!builtin||!out||builtin==out||builtin->schema!=6)return -1;
 struct a7_custom_look look;
 if(a7_custom_resolve(c,slot,&look))return -1;
 struct a7_fl_preference p=*builtin;
 a7_fl_preference_switch(&p,look.base);
 for(unsigned i=0;i<8;i++)p.parameters[i]=look.values[i];
 for(unsigned i=0;i<7;i++)p.film[look.base-1][i]=look.values[i+8];
 p.vignette[look.base-1]=look.values[15];
 p.candidate_crc=0;*out=p;return 0;
}
