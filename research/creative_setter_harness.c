/* Recording dependencies for one original Sony routine. Never a device payload. */
#include <stdint.h>
typedef int (*Setter)(void *,int,int,int,int,int);
static unsigned arena[128], used;
static unsigned write_id[8], write_value[8], writes;
static int parameter_id[8], parameter_value[8], parameters;
static int requests, request_result, bad;
static void put(const char *s) {
    volatile unsigned *u=(volatile unsigned *)0x10009000;
    while(*s) { while(u[6]&32) {} u[0]=*s++; }
}
static void number(int n) {
    char b[12]; int i=0;
    if(n<0) {put("-");n=-n;}
    do {b[i++]='0'+n%10;n/=10;} while(n);
    while(i) {char c[2]={b[--i],0};put(c);}
}
static void finish(void) {
    register unsigned r0 __asm__("r0")=0x18;
    register unsigned r1 __asm__("r1")=0x20026;
    __asm__ volatile("svc 0xab" : "+r"(r0), "+r"(r1) : : "memory");
    while(1) {}
}
void unexpected(void) {put("FAIL unexpected dependency\n");finish();}
void *allocate(unsigned n) {
    unsigned words=(n+3)/4;
    if(used+words>128) unexpected();
    void *p=arena+used;used+=words;return p;
}
void *copy_bytes(void *d,const void *s,unsigned n) {
    for(unsigned i=0;i<n;i++) ((char *)d)[i]=((const char *)s)[i];
    return d;
}
void no_op(void) {}
void *param_init(unsigned *p,int value) {p[4]=(unsigned)value;return p;}
int param_value(unsigned *p) {return (int)p[4];}
int backup_write(unsigned id,const unsigned char *value) {
    if(writes>=8) unexpected();
    write_id[writes]=id;write_value[writes++]=*value;return 1;
}
void *list_init(void *p,unsigned unused) {(void)unused;return p;}
void list_add(void *p,unsigned id,unsigned *value) {
    (void)p;
    if(parameters>=8) unexpected();
    parameter_id[parameters]=(int)id;parameter_value[parameters++]=(int)value[4];
}
int model_execute(const char *name,unsigned command,void *list) {
    (void)list;static const char expected[]="@M00B";
    for(unsigned i=0;i<sizeof expected;i++) if(name[i]!=expected[i]) bad++;
    if(command!=38) bad++;
    requests++;return request_result;
}
static int check(int style,int box,int c,int s,int h) {
    const int model_style[14]={1,2,3,7,8,9,4,5,10,11,12,6,0,14};
    const unsigned contrast[14]={0x01070735,0x01070736,0x0107073a,0x0107073b,
        0x0107073c,0x0107073d,0x0107073e,0x0107073f,0x01070740,0x01070741,
        0x01070737,0x01070738,0,0x01070739};
    used=writes=0;parameters=requests=bad=0;
    int rc=((Setter)(uintptr_t)0x420d19)(0,style,box,c,s,h);
    if(style<0||style>13||style==12) return rc==0 && writes==0 && requests==0;
    if(rc!=1||bad||requests!=1||parameters!=5||writes!=(box?5u:4u)) return 0;
    int vals[5]={model_style[style],c,(style==11||style==13)?0:s,h,model_style[style]};
    const int ids[5]={383,386,389,392,383};
    for(int i=0;i<5;i++) if(parameter_id[i]!=ids[i]||parameter_value[i]!=vals[i]) return 0;
    if(write_id[0]!=0x01070762||write_value[0]!=(box?(unsigned)(box-1):255)) return 0;
    unsigned k=1, cid=contrast[style], sid=cid+13, hid=cid+26;
    if(box) {
        if(write_id[k]!=0x0107075b+(unsigned)box||write_value[k]!=(unsigned)model_style[style]) return 0;
        k++;cid=0x01070a0e + box;sid=cid+6;hid=cid+12;
    }
    return write_id[k]==cid&&write_id[k+1]==sid&&write_id[k+2]==hid&&
        write_value[k]==(unsigned char)c&&write_value[k+1]==(unsigned char)s&&write_value[k+2]==(unsigned char)h;
}
void guest_main(void) {
    unsigned cases=0;
    request_result=1;
    for(int style=-1;style<=14;style++) for(int box=0;box<=6;box++)
        for(int c=-3;c<=3;c++) for(int s=-3;s<=3;s++) for(int h=-3;h<=3;h++) {
            if(!check(style,box,c,s,h)) {
                put("FAIL style=");number(style);put(" box=");number(box);
                put(" c=");number(c);put(" s=");number(s);put(" h=");number(h);put("\n");finish();
            }
            cases++;
        }
    put("SETTER_CASES ");number(cases);put("\n");
    request_result=0;
    if(!check(2,3,1,-1,-1)) {put("FAIL downstream rejection case\n");finish();}
    put("REQUEST_FAILURE_IS_NOT_PROPAGATED\n");
    put("RECIPE_SLOT3_WRITES_MATCH_OBSERVED_SNAPSHOT_IDS\n");
    put("NATIVE_SETTER_TESTS_PASSED\n");finish();
}
