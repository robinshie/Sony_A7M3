#ifndef A7_FL_CUSTOM_STORE_H
#define A7_FL_CUSTOM_STORE_H
#include "a7-fl-custom.h"
struct a7_custom_io {
 /* 0 present, 1 absent, negative error. Report complete length or overflow. */
 int (*read)(void*,unsigned,unsigned char*,unsigned,unsigned*);
 /* Compare old bytes/absence; persist complete replacement; zero on success. */
 int (*replace)(void*,unsigned,const unsigned char*,unsigned,int,const unsigned char*,unsigned);
 void *opaque;
};
struct a7_custom_store {struct a7_custom_io io; unsigned char bytes[2][A7_CUSTOM_RECORD_BYTES];unsigned sizes[2];int exists[2],selected,ready;};
int a7_custom_store_open(struct a7_custom_store*,const struct a7_custom_io*,struct a7_custom_catalog*);
int a7_custom_store_save(struct a7_custom_store*,const struct a7_custom_catalog*);
#endif
