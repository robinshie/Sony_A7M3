/* Execute the original reverse mapper, Fn mapper and Fn node selector,
 * with only UI storage/vtable boundaries represented by recording fixtures. */
#include <stdint.h>
extern void *dlsym(void *,const char *);
static long sc(long n,long a,long b,long c) {
    register long r7 __asm__("r7")=n;
    register long r0 __asm__("r0")=a;
    register long r1 __asm__("r1")=b;
    register long r2 __asm__("r2")=c;
    __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");
    return r0;
}
static void say(const char *s){unsigned n=0;while(s[n])n++;sc(4,1,(long)s,n);}
static void fail(const char *s){say("FAIL ");say(s);say("\n");sc(1,77,0,0);}
#define CHECK(x,s) do{if(!(x))fail(s);}while(0)
static const uint32_t properties[91][30]={
#include "fn-properties.h"
};
typedef struct Node {void **vtable;int index;} Node;
static Node root,children[91];
static void *vtable[44];
static int count(Node *n,int *out){*out=n==&root?91:0;return 1;}
static int child(Node *n,int index,Node **out){*out=n==&root&&index>=1&&index<=91?&children[index-1]:0;return *out!=0;}
static int has_children(Node *n){return n==&root;}
static int property(Node *n,int key,int *out){
    if(n==&root){if(key==14){*out=40;return 1;}return 0;}
    for(unsigned i=0;i<30;i+=3)if(properties[n->index][i]==(unsigned)key){*out=properties[n->index][i+2];return 1;}
    return 0;
}
int main(void){
    int (*stock)(void*,int,int)=dlsym(0,"stock_reverse");
    int (*remember)(void*,int,int)=dlsym(0,"test_remember");
    int (*reopen)(void*,int,int)=dlsym(0,"test_reopen");
    void (*fnmap)(void*,int,int,int*)=dlsym(0,"original_fn_map");
    void *(*fnselect)(void*,void*,int)=dlsym(0,"original_fn_select");
    CHECK(stock&&remember&&reopen&&fnmap&&fnselect,"symbols");
    unsigned view[100]={0},cursor[2]={0};view[75]=(uintptr_t)cursor;
    int calls=0;
    for(int box=-2;box<=8;box++)for(int style=-2;style<=16;style++){
        cursor[0]=0;cursor[1]=999;
        int old=stock(view,style,box);unsigned oldcount=cursor[0],oldparent=cursor[1];
        for(int path=0;path<2;path++){
            cursor[0]=0;cursor[1]=999;
            int id=(path?remember:reopen)(view,style,box);
            if(style==3&&box==3)CHECK(id==98&&cursor[0]==1&&cursor[1]==97,"recipe reopens on top-level entry");
            else CHECK(id==old&&cursor[0]==oldcount&&cursor[1]==oldparent,"original cursor behavior retained");
            calls++;
        }
    }
    vtable[4]=count;vtable[9]=child;vtable[23]=property;vtable[43]=has_children;
    root.vtable=vtable;root.index=-1;
    for(int i=0;i<91;i++){children[i].vtable=vtable;children[i].index=i;}
    int names=0,custom=0;
    for(int box=0;box<=6;box++)for(int style=0;style<=13;style++){
        if(style==12)continue; /* Not an offered 4.04 style. */
        int value=-999;fnmap(view,style,box,&value);
        CHECK(value>=0&&value<98,"Fn mapping range");
        view[78]=0;fnselect(view,&root,value);
        Node *selected=(void*)(uintptr_t)view[78];
        CHECK(selected>=children&&selected<children+91,"original Fn selector resolves native node");
        int text=-1;CHECK(property(selected,0,&text),"selected node text property");
        if(style==2&&box==3){CHECK(value==48&&text==0x0204ed84,"Fn selected name is custom resource");custom++;}
        else CHECK(text!=0x0204ed84,"other native styles retain their names");
        names++;
    }
    CHECK(custom==1&&names==91&&calls==418,"coverage");
    say("QEMU_IDENTITY_PASSED 418 cursor paths; 91 original Fn selection/name paths\n");
    return 0;
}
