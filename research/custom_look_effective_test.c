#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "a7-fl-custom-effective.h"
int main(void){
 struct a7_custom_catalog empty,c; a7_custom_empty(&empty);
 struct a7_custom_look l={.id="independent",.name="Independent",.base=6,.values={4,2,-3,1,2,1,4,2,7,-2,1,2,3,4,5,-6}};
 assert(!a7_custom_append(&empty,&l,&c));
 struct a7_fl_preference builtin={.schema=6,.enabled=1,.generation=72};
 builtin.parameters[0]=8;builtin.parameters[6]=3;builtin.film[5][0]=1;
 struct a7_fl_preference original=builtin,effective;
 assert(!a7_custom_effective(&c,7,&builtin,&effective));
 assert(!memcmp(&builtin,&original,sizeof builtin));
 assert(effective.enabled==6&&effective.parameters[0]==4&&effective.parameters[6]==4&&effective.film[5][0]==7&&effective.film[5][1]==-2&&effective.vignette[5]==-6);
 assert(!effective.candidate_crc&&effective.generation==72);
 assert(a7_custom_effective(&c,7,&builtin,&builtin)<0&&!memcmp(&builtin,&original,sizeof builtin));
 assert(a7_custom_effective(&c,8,&builtin,&effective)<0);
 puts("CUSTOM_EFFECTIVE_PASSED: separate working values, base selection, original six-bank bytes unchanged");
}
