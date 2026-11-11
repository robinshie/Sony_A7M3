#include "sha256.h"
#include "vectors.h"
static void put(const char *s){volatile unsigned *u=(volatile unsigned *)0x10009000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void done(void){register unsigned r0 __asm__("r0")=0x18;register unsigned r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0xab":"+r"(r0),"+r"(r1)::"memory");while(1){}}
void guest_main(void){
    unsigned char input[8200],digest[32];for(unsigned i=0;i<sizeof input;i++)input[i]=(i*37+11)&255;
    for(unsigned v=0;v<sizeof sizes/sizeof sizes[0];v++)for(unsigned stride=1;stride<=4096;stride*=8){
        Sha256 s;sha_init(&s);
        for(unsigned at=0;at<sizes[v];){unsigned n=sizes[v]-at;if(n>stride)n=stride;sha_update(&s,input+at,n);at+=n;}
        sha_finish(&s,digest);
        for(unsigned i=0;i<32;i++)if(digest[i]!=expected[v][i]){put("FAIL SHA256 vector\n");done();}
    }
    put("QEMU_IMAGE_SHA256_PASSED 75 streaming and padding boundary vectors\n");done();
}
