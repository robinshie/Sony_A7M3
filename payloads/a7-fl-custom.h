#ifndef A7_FL_CUSTOM_H
#define A7_FL_CUSTOM_H
#include <stdint.h>
#define A7_CUSTOM_MAX 16
#define A7_CUSTOM_RECORD_BYTES (32+176*A7_CUSTOM_MAX)
struct a7_custom_look { uint32_t slot; char id[49],name[64]; uint8_t base; int8_t values[16]; };
struct a7_custom_catalog { uint32_t generation,next_slot,active,count; struct a7_custom_look looks[A7_CUSTOM_MAX]; };
/* Prototype capacity; hardware menu capacity remains to be validated. */
int a7_custom_parse(const unsigned char*,unsigned,struct a7_custom_look*);
void a7_custom_empty(struct a7_custom_catalog*);
int a7_custom_append(const struct a7_custom_catalog*,const struct a7_custom_look*,struct a7_custom_catalog*);
int a7_custom_encode(const struct a7_custom_catalog*,unsigned char[A7_CUSTOM_RECORD_BYTES]);
int a7_custom_decode(const unsigned char*,unsigned,struct a7_custom_catalog*);
/* An exact base ID and independent controls for the existing color/capture engine. */
int a7_custom_resolve(const struct a7_custom_catalog*,uint32_t,struct a7_custom_look*);
#endif
