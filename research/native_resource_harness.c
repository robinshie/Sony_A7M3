/* Test the original ARM resource parser; no rewritten index-lookup algorithm. */
#include <stdint.h>
#include "resource_data.h"
static unsigned checks;
typedef unsigned (*ReadWord)(const void *);
typedef const unsigned char *(*ReadPointer)(const void *);
typedef const unsigned char *(*Lookup)(const void *,unsigned);
static void put(const char *s) {
    volatile unsigned *uart=(volatile unsigned *)0x10009000;
    while(*s){while(uart[6]&32){}uart[0]=*s++;}
}
static void number(unsigned n){char b[12];unsigned i=0;do{b[i++]='0'+n%10;n/=10;}while(n);while(i){char c[2]={b[--i],0};put(c);}}
static void finish(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}}
void unexpected_log(void){put("FAIL native parser warning\n");finish();}
static void check(int ok,const char *name){checks++;if(!ok){put("FAIL ");put(name);put("\n");finish();}}
static int same_text(const unsigned char *a,const unsigned char *a_end,const unsigned char *b,const unsigned char *b_end){
    while(a<a_end&&b<b_end){unsigned av=*a++,bv=*b++;if(av!=bv)return 0;if(!av)return 1;}return 0;
}
static void locale(unsigned char *before,unsigned char *after,const unsigned sizes[2],const char **labels){
    ReadWord valid=(ReadWord)0x816119,count=(ReadWord)0x8159cf,
             record_id=(ReadWord)0x8207c7,record_type=(ReadWord)0x5f4451;
    ReadPointer data_start=(ReadPointer)0x8159e9;
    Lookup lookup=(Lookup)0x815a7d;
    check(valid(before)&&valid(after),"original header accepts both files");
    check(count(before+8)==RESOURCE_OLD_COUNT&&count(after+8)==(RESOURCE_OLD_COUNT+RESOURCE_ADDED),"native count expands RESOURCE_OLD_COUNT to (RESOURCE_OLD_COUNT+RESOURCE_ADDED)");
    const unsigned char *old_start=data_start(before+8),*new_start=data_start(after+8);
    check((unsigned)(new_start-after)==(unsigned)(old_start-before)+4*RESOURCE_ADDED,"native data start advances exactly 40 bytes");
    unsigned assigned=0,unassigned=0;
    for(unsigned i=0;i<RESOURCE_OLD_COUNT;i++){
        const unsigned char *old=lookup(before+8,i),*next=lookup(after+8,i);
        check((old==0)==(next==0),"native unassigned state preserved");
        if(!old){unassigned++;continue;}
        assigned++;
        check(old>=old_start&&old+4<before+sizes[0]&&next>=new_start&&next+4<after+sizes[1],"native record pointer inside file");
        check(record_id(old)==0x0204e000+i&&record_id(next)==0x0204e000+i,"native record IDs unchanged");
        check(record_type(old)==7&&record_type(next)==7,"native record type remains text");
        check((unsigned)(next-after)==(unsigned)(old-before)+4*RESOURCE_ADDED,"native old-record location moves with data body");
        check(same_text(old+4,before+sizes[0],next+4,after+sizes[1]),"old UTF-8 text exact via native lookups");
    }
    for(unsigned i=0;i<RESOURCE_ADDED;i++){
        const unsigned char *record=lookup(after+8,RESOURCE_OLD_COUNT+i);
        check(lookup(before+8,RESOURCE_OLD_COUNT+i)==0,"native old count excludes appended IDs");
        check(record&&record>=new_start&&record+4<after+sizes[1],"native appended lookup resolves inside file");
        check(record_id(record)==0x0204e000u+RESOURCE_OLD_COUNT+i&&record_type(record)==7,"native appended record ID/type accepted");
        unsigned n=0;while(labels[i][n])n++;
        check(same_text(record+4,after+sizes[1],(const unsigned char *)labels[i],(const unsigned char *)labels[i]+n+1),"native appended lookup returns exact label");
    }
    check(lookup(after+8,(RESOURCE_OLD_COUNT+RESOURCE_ADDED))==0&&lookup(after+8,8191)==0&&lookup(after+8,0xffffffffu)==0,"native out-of-range IDs rejected");
    unsigned char old_magic=after[0];after[0]^=1;
    check(!valid(after),"native validator rejects wrong magic");after[0]=old_magic;
    check(valid(after),"native validator accepts restored magic");
    put("NATIVE_RESOURCE_LOCALE old_assigned=");number(assigned);put(" old_unassigned=");number(unassigned);put(" new_labels=");number(RESOURCE_ADDED);put("\n");
}
void guest_main(void){
    locale(resource_before_0,resource_after_0,resource_sizes_0,resource_labels_0);
    locale(resource_before_1,resource_after_1,resource_sizes_1,resource_labels_1);
    put("NATIVE_RESOURCE_CHECKS ");number(checks);put("\nNATIVE_RESOURCE_TESTS_PASSED\n");finish();
}
