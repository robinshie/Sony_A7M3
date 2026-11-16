#include "a7-fl-custom-session.h"
static int usable(const struct a7_custom_session*s){return s&&s->ready&&!s->fault&&s->engine.apply;}
static int apply(struct a7_custom_session*s,const struct a7_custom_catalog*c){
 struct a7_fl_preference next=s->builtin;
 if(!c->active&&next.enabled>0&&(c->hidden_builtin&(1u<<(next.enabled-1))))a7_fl_preference_switch(&next,0);
 if(c->active&&a7_custom_effective(c,c->active,&s->builtin,&next))return -1;
 if(s->engine.apply(s->engine.opaque,&s->effective,&next))return -2;
 s->effective=next;return 0;
}
int a7_custom_session_open(struct a7_custom_session*s,const struct a7_custom_io*io,const struct a7_custom_engine*engine,const struct a7_fl_preference*builtin){
 if(!s||!io||!engine||!engine->apply||!builtin||builtin->schema!=6)return -1;
 s->ready=s->dirty=s->fault=0;s->engine=*engine;s->builtin=s->effective=*builtin;
 int rc=a7_custom_store_open(&s->store,io,&s->saved);
 if(rc<0)return rc;
 s->working=s->saved;
 if(apply(s,&s->saved)){s->fault=1;return -2;}
 s->ready=1;return rc;
}
int a7_custom_session_import(struct a7_custom_session*s,const unsigned char*raw,unsigned n){
 if(!usable(s)||s->dirty||!s->store.ready)return -1;
 struct a7_custom_look l;struct a7_custom_catalog next;
 if(a7_custom_parse(raw,n,&l)||a7_custom_append(&s->saved,&l,&next))return -2;
 /* Import adds an entry without silently switching the currently active look. */
 if(a7_custom_store_save(&s->store,&next)){s->fault=1;return -3;}
 s->working=s->saved=next;return 0;
}
int a7_custom_session_select(struct a7_custom_session*s,uint32_t slot){
 if(!usable(s))return -1;
 struct a7_custom_catalog next=s->working;struct a7_custom_look l;
 if(slot&&a7_custom_resolve(&next,slot,&l))return -2;
 if(slot==next.active)return 0;
 next.active=slot;
 if(apply(s,&next))return -3;
 s->working=next;s->dirty=1;return 0;
}
int a7_custom_session_edit(struct a7_custom_session*s,unsigned field,int value){
 if(!usable(s)||!s->working.active||field>=16||value<-15||value>15)return -1;
 struct a7_custom_catalog next=s->working;unsigned i=0;
 while(i<next.count&&next.looks[i].slot!=next.active)i++;
 if(i==next.count)return -2;
 if(next.looks[i].values[field]==value)return 0;
 next.looks[i].values[field]=(int8_t)value;
 unsigned char bytes[A7_CUSTOM_RECORD_BYTES];
 if(a7_custom_encode(&next,bytes)||apply(s,&next))return -3;
 s->working=next;s->dirty=1;return 0;
}
int a7_custom_session_save(struct a7_custom_session*s){
 if(!usable(s)||!s->store.ready)return -1;
 if(!s->dirty)return 0;
 if(s->saved.generation>=0xfffffffeu)return -2;
 struct a7_custom_catalog next=s->working;next.generation=s->saved.generation+1;
 if(a7_custom_store_save(&s->store,&next)){s->fault=1;return -3;}
 s->saved=s->working=next;s->dirty=0;return 0;
}
int a7_custom_session_cancel(struct a7_custom_session*s){
 if(!usable(s))return -1;
 if(!s->dirty)return 0;
 if(apply(s,&s->saved)){s->fault=1;return -2;}
 s->working=s->saved;s->dirty=0;return 0;
}
const char *a7_custom_session_name(const struct a7_custom_session*s,unsigned index,uint32_t*slot){
 if(!usable(s)||!slot||index>=s->working.count)return 0;
 *slot=s->working.looks[index].slot;return s->working.looks[index].name;
}

int a7_custom_session_delete(struct a7_custom_session*s,uint32_t slot){
 if(!usable(s)||!s->store.ready||slot<7||s->working.active!=slot||s->saved.generation>=0xfffffffeu)return -1;
 struct a7_custom_catalog next=s->saved;
 unsigned index=slot-7;if(index>=next.count||next.looks[index].slot!=slot)return -2;
 for(unsigned i=index;i+1<next.count;i++){next.looks[i]=next.looks[i+1];next.looks[i].slot=7+i;}
 next.count--;next.next_slot=7+next.count;next.active=0;next.generation++;
 /* Confirmed deletion of selected look returns to the unchanged built-in bank.
  * Unsaved edits to the deleted look are discarded only after confirmation. */
 if(apply(s,&next))return -3;
 if(a7_custom_store_save(&s->store,&next)){
  if(apply(s,&s->working))s->fault=1;
  s->fault=1;return -4;
 }
 s->saved=s->working=next;s->dirty=0;return 0;
}

int a7_custom_session_delete_builtin(struct a7_custom_session*s,unsigned mode){
 if(!usable(s)||!s->store.ready||mode<1||mode>6||s->working.active||s->effective.enabled!=(int)mode||s->saved.generation>=0xfffffffeu)return -1;
 struct a7_custom_catalog next=s->saved;
 if(next.hidden_builtin&(1u<<(mode-1)))return -2;
 next.hidden_builtin|=1u<<(mode-1);next.active=0;next.generation++;
 struct a7_fl_preference before=s->effective,off=before;
 a7_fl_preference_switch(&off,0);
 if(s->engine.apply(s->engine.opaque,&before,&off))return -3;
 if(a7_custom_store_save(&s->store,&next)){
  (void)s->engine.apply(s->engine.opaque,&off,&before);s->fault=1;return -4;
 }
 s->effective=off;s->saved=s->working=next;s->dirty=0;return 0;
}
