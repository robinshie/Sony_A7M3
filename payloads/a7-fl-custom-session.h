#ifndef A7_FL_CUSTOM_SESSION_H
#define A7_FL_CUSTOM_SESSION_H
#include "a7-fl-custom-store.h"
#include "a7-fl-custom-effective.h"
struct a7_custom_engine {
 /* Prepare CRC and atomically reconcile preview/CAP tables plus capture controls.
  * Must leave the old state intact on failure or explicitly fault the caller. */
 int (*apply)(void*,const struct a7_fl_preference*,struct a7_fl_preference*);
 void *opaque;
};
struct a7_custom_session {
 struct a7_custom_store store;
 struct a7_custom_catalog saved,working;
 struct a7_fl_preference builtin,effective;
 struct a7_custom_engine engine;
 unsigned ready,dirty,fault;
};
int a7_custom_session_open(struct a7_custom_session*,const struct a7_custom_io*,const struct a7_custom_engine*,const struct a7_fl_preference*);
int a7_custom_session_import(struct a7_custom_session*,const unsigned char*,unsigned);
int a7_custom_session_select(struct a7_custom_session*,uint32_t);
int a7_custom_session_edit(struct a7_custom_session*,unsigned,int);
int a7_custom_session_delete(struct a7_custom_session*,uint32_t);
int a7_custom_session_save(struct a7_custom_session*);
int a7_custom_session_cancel(struct a7_custom_session*);
const char *a7_custom_session_name(const struct a7_custom_session*,unsigned,uint32_t*);
#endif
