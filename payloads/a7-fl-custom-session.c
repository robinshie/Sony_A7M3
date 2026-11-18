#include "a7-fl-custom-session.h"
static int usable(const struct a7_custom_session*s){return s&&s->ready&&!s->fault&&s->engine.apply;}
static int engine_apply(struct a7_custom_session*s,const struct a7_fl_preference*before,struct a7_fl_preference*next,const struct a7_custom_catalog*c){
 return s->engine.apply_catalog?s->engine.apply_catalog(s->engine.opaque,before,next,c):s->engine.apply(s->engine.opaque,before,next);
}
static int apply(struct a7_custom_session*s,const struct a7_custom_catalog*c){
 struct a7_fl_preference next=s->builtin;
 if(!c->active&&next.enabled>0&&(c->hidden_builtin&(1u<<(next.enabled-1))))a7_fl_preference_switch(&next,0);
 if(c->active&&a7_custom_effective(c,c->active,&s->builtin,&next))return -1;
 if(engine_apply(s,&s->effective,&next,c))return -2;
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
 if(engine_apply(s,&before,&off,&next))return -3;
 if(a7_custom_store_save(&s->store,&next)){
  (void)engine_apply(s,&off,&before,&s->working);s->fault=1;return -4;
 }
 s->effective=off;s->saved=s->working=next;s->dirty=0;return 0;
}

/* Wet flags live in the independent catalog. The six original preference banks
 * retain their exact on-disk representation and values. */
static int wet_id(const char*s){const char*t="wet-plate-hard-bw-v1";while(*s&&*s==*t){s++;t++;}return *s==*t;}
int a7_custom_wet_value(const struct a7_custom_catalog*c,unsigned mode){
 if(!c||!mode||mode>6)return 0;
 if(c->active){for(unsigned i=0;i<c->count;i++)if(c->looks[i].slot==c->active)return wet_id(c->looks[i].id)||c->looks[i].wet;return 0;}
 return (c->wet_builtin>>(mode-1))&1;
}
int a7_custom_wet_edit(struct a7_custom_session*s,unsigned mode,int value){
 if(!usable(s)||mode<1||mode>6||(value!=0&&value!=1))return -1;
 struct a7_custom_catalog next=s->working;
 if(next.active){
  unsigned i=0;while(i<next.count&&next.looks[i].slot!=next.active)i++;
  if(i==next.count||(wet_id(next.looks[i].id)&&!value))return -2;
  next.looks[i].wet=(uint8_t)value;
 }else next.wet_builtin=(next.wet_builtin&~(1u<<(mode-1)))|((unsigned)value<<(mode-1));
 if(a7_custom_wet_value(&next,mode)==a7_custom_wet_value(&s->working,mode))return 0;
 /* The caller may have changed a built-in style since last catalog apply. */
 if(apply(s,&next))return -3;
 s->working=next;s->dirty=1;return 0;
}
int a7_custom_wet_install(struct a7_custom_session*s){
 if(!usable(s)||!s->store.ready||s->dirty)return -1;
 if(s->saved.wet_initialized)return 0;
 struct a7_custom_catalog next=s->saved;unsigned i=0;
 while(i<next.count&&!wet_id(next.looks[i].id))i++;
 if(i==next.count){
  struct a7_custom_look l={0};const char*id="wet-plate-hard-bw-v1",*name="FL7 湿版黑白";
  for(unsigned j=0;id[j];j++)l.id[j]=id[j];
  for(unsigned j=0;name[j];j++)l.name[j]=name[j];
  l.base=1;l.values[6]=3;l.wet=1;
  if(a7_custom_append(&s->saved,&l,&next))return -2;
 }else{if(next.generation>=0xfffffffeu)return -2;next.generation++;}
 next.wet_initialized=1;
 if(a7_custom_store_save(&s->store,&next)){s->fault=1;return -3;}
 s->saved=s->working=next;return 0;
}
