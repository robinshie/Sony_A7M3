#define A7_AUTO_SIZE 1
#ifdef TEST_WET
#define A7_WET_PLATE 1
static unsigned frame_wet;
#endif
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#ifdef TEST_GRAIN
#define A7_GRAIN 1
#define A7_GRAIN_FIXTURE 1
#ifdef TEST_FULL
#define A7_GRAIN_FULL 1
#endif
#include <stdbool.h>
#endif
#define A7_LEASE_FIXTURE 1
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
typedef struct {unsigned value,break_lock;} raw_spinlock_t;
static unsigned report[368],checks,held_lock,lock_busy,atomic_context,opens,closes;
#ifdef TEST_HALATION
#define A7_HALATION_TEST 1
static unsigned completed;
static int frame_halation,disarmed=1;
#endif
#ifdef TEST_FILM
static unsigned frame_grain,frame_seed=0x5a7f1203;
#endif
#ifdef TEST_VIGNETTE
#define A7_VIGNETTE_BANKS 1
static int frame_vignette;
static unsigned diagnostic;
static unsigned busy_attempts;
#define cpu_relax() ((void)0)
#define module_param_array(a,b,c,d)
#endif
static unsigned test_physical=0x1a000000;
static int bad_mapping,bad_cache;
static unsigned char *const unit=(void *)0x42095ab8;
static unsigned ext[12];
static void check(int ok);
void *memset(void *p,int c,size_t n){unsigned char *q=p;while(n--)*q++=(unsigned char)c;return p;}
static void *memcpy(void *d,const void *s,size_t n){unsigned char *a=d;const unsigned char *b=s;while(n--)*a++=*b++;return d;}
static int memcmp(const void *a,const void *b,size_t n){const unsigned char *x=a,*y=b;while(n--){if(*x!=*y)return *x-*y;x++;y++;}return 0;}
static int probe_kernel_read(void *d,const void *s,unsigned n){memcpy(d,s,n);return 0;}
static unsigned long kallsyms_lookup_name(const char *s){(void)s;return 0;}
static int raw_spin_trylock(raw_spinlock_t *p){(void)p;check(!held_lock);
#ifdef TEST_VIGNETTE
    if(busy_attempts){busy_attempts--;return 0;}
#endif
    if(lock_busy)return 0;
    held_lock=1;return 1;}
static void raw_spin_unlock(raw_spinlock_t *p){(void)p;check(held_lock);held_lock=0;}
#define raw_spin_trylock_irqsave(p,f) ((f)=0,raw_spin_trylock(p))
#define raw_spin_unlock_irqrestore(p,f) ((void)(f),raw_spin_unlock(p))
#define raw_spin_lock_irqsave(p,f) do{check(!held_lock);held_lock=1;(f)=0;}while(0)
static int in_interrupt(void){return 0;}
static int irqs_disabled(void){return 0;}
static int in_atomic(void){return atomic_context;}
int arch_phys_to_cachetype2(unsigned long p,unsigned long s){check((p==0x1a000000||p==0x24000000)&&s==0x3000000);return bad_cache?0:0x12;}
#include "kernel_probe/capture_lease_record.h"
#ifdef TEST_GRAIN
typedef long long loff_t;typedef long ssize_t;
struct file{int unused;};struct kobject{int unused;};
struct bin_attribute{struct{const char *name;unsigned mode;}attr;size_t size;ssize_t (*read)(struct file *,struct kobject *,struct bin_attribute *,char *,loff_t,size_t);};
static struct{struct{struct kobject kobj;}mkobj;}module;
#define THIS_MODULE (&module)
static unsigned long jiffies;static unsigned barriers,corrupt_at;
static int sysfs_create_bin_file(struct kobject *k,struct bin_attribute *b){(void)k;(void)b;return 0;}
static void sysfs_remove_bin_file(struct kobject *k,struct bin_attribute *b){(void)k;(void)b;}
unsigned long arch_phys_to_va(unsigned long p){check(!held_lock&&(p==0x1a000000||p==0x24000000));return p+0x60000000+(bad_mapping?4096:0);}
int arch_va_to_cachetype(unsigned long v){check(v==0x7a000000||v==0x84000000);return bad_cache?0:0x12;}
#if defined(TEST_HALATION) && !defined(TEST_FILM)
static unsigned halo_corrupt_offset(void);
#endif
static void mb(void){check(!held_lock);barriers++;jiffies++;if(barriers==corrupt_at)
#if defined(TEST_HALATION) && !defined(TEST_FILM)
/* The diagnostic region is chosen from source highlights before the filter. */
*(volatile unsigned char *)(test_physical+0x60000000+halo_corrupt_offset())^=1;
#else
*(volatile unsigned char *)(0x7a000000+1936*12160+2952*2+1)^=1;
#endif
}
#ifdef TEST_VIGNETTE
#include "kernel_probe/capture_auto_record.h"
#elif defined(TEST_FILM)
#include "kernel_probe/capture_film_record.h"
#elif defined(TEST_HALATION)
#include "kernel_probe/capture_halation_record.h"
static unsigned halo_corrupt_offset(void){return (halo[completed].y+HB)*12160+(halo[completed].x+HB)*2+1;}
#else
#include "kernel_probe/capture_grain_record.h"
#endif
#endif
static int wrapped_open(unsigned h,unsigned mode,void *out,unsigned short *n){
    int (*fn)(unsigned,unsigned,void *,unsigned short *)=(void *)0x4100889c;
    check(held_lock&&mode==4);opens++;return fn(h,mode,out,n);
}
static int wrapped_close(unsigned h){int (*fn)(unsigned)=(void *)0x41008a28;check(held_lock);closes++;return fn(h);}
static void print(const char *s){volatile unsigned *u=(void *)0x09000000;while(*s){while(u[6]&32){}u[0]=*s++;}}
static void number(unsigned n){char s[12];unsigned i=11;s[i]=0;do{s[--i]='0'+n%10;n/=10;}while(n);print(s+i);}
static void stop(void){register unsigned r0 __asm__("r0")=0x18,r1 __asm__("r1")=0x20026;__asm__ volatile("svc 0x123456":"+r"(r0),"+r"(r1)::"memory");for(;;){}}
static void check(int ok){checks++;if(!ok){print("FAIL check=");number(checks);print("\n");stop();}}
static void reset(void){
    unsigned i;for(i=0;i<368;i++)report[i]=0;for(i=0;i<0x150;i++)unit[i]=0;for(i=0;i<12;i++)ext[i]=0;
    report[21]=(3<<10)|7;report[22]=(unsigned)unit;
    report[40+0x90/4]=0x0fa01770;report[40+0x94/4]=0x0fa017c0;report[40+0x98/4]=80;
    report[40+0xbc/4]=1;report[40+0xc0/4]=test_physical;report[40+0xc4/4]=0x3000000;
    report[257]=test_physical;report[259]=0x3000000;
    unit[0x13]=3;*(unsigned short *)(unit+0x14)=1;*(unsigned short *)(unit+0x16)=1;
    *(unsigned *)(unit+0x18)=(unsigned)ext;ext[1]=test_physical;ext[3]=0x3000000;
    report[40+0x7c/4]=1;report[40+0x90/4]=report[40+0x9c/4]=report[40+0xa4/4]=0x0fa01770;
    report[40+0xa8/4]=0x10000;report[40+0xac/4]=0x20101;
    report[40+0xb4/4]=0x1010001;report[40+0xb8/4]=0x400;
    report[40+0x74/4]=report[40+0x78/4]=4000;
    held_lock=lock_busy=atomic_context=opens=closes=0;
    bad_mapping=bad_cache=0;
#ifdef TEST_GRAIN
    barriers=corrupt_at=0;
#endif
    native_open=wrapped_open;native_close=wrapped_close;
}

void guest_main(void){
    (void)source_publish;(void)source_remove;(void)take_early_record;
    (void)sysfs_create_bin_file;(void)sysfs_remove_bin_file;(void)disarmed;(void)module;
    check(!grain_publish());
    reset();report[40+0xac/4]^=1;check(take_lease_test()<0&&!opens&&!closes&&!barriers);
    reset();report[40+0x94/4]=0xffffffff;check(take_lease_test()<0&&!opens&&!closes&&!barriers);
    reset();report[40+0x98/4]=81;check(take_lease_test()<0&&!opens&&!closes&&!barriers);
    reset();lock_busy=1;check(take_lease_test()==-EBUSY&&!opens&&!closes&&!barriers);
    reset();unit[0x11]=1;check(take_lease_test()==-ESTALE&&!opens&&!closes&&!barriers);
    reset();bad_mapping=1;check(take_lease_test()<0&&opens==1&&closes==1&&!barriers);
    reset();atomic_context=1;check(take_lease_test()==-EWOULDBLOCK&&!opens);
    static const unsigned widths[]={6000,3936,3008},canvas[]={6080,6000,6000},dest[]={4000,2624,2000};
    for(unsigned i=0;i<3;i++){
        reset();completed=i;diagnostic=1;frame_grain=9;frame_halation=9;frame_vignette=-9;
        unsigned w=widths[i],stride=canvas[i]*2;
        report[40+0x90/4]=report[40+0x9c/4]=report[40+0xa4/4]=(4000u<<16)|w;
        report[40+0x94/4]=(4000u<<16)|canvas[i];
        report[40+0x74/4]=report[40+0x78/4]=dest[i];
        unsigned char *pixels=(void *)0x7a000000;
        memset(pixels,0xc7,0x3000000);
        for(unsigned y=0;y<4000;y++)for(unsigned x=0;x<w;x++){
            pixels[y*stride+160+2*x]=128;
            pixels[y*stride+161+2*x]=x<w/2?105:250;
        }
        unsigned before[32];memcpy(before,unit,32);
        check(!take_lease_test());
        check(opens==1&&closes==1&&!held_lock&&!memcmp(before,unit,32));
        check(report[349]==w*4000&&report[364]==w&&report[365]==4000&&report[366]==stride&&report[367]==160);
        check(report[344]==3&&!report[345]&&report[310]==1);
        unsigned *sample=i==0?auto_sample0:i==1?auto_sample1:auto_sample2;
        check(sample[326]==w&&sample[327]==4000&&sample[331]==dest[i]);
        check(memcmp(sample+6,sample+166,160*4)!=0);
        for(unsigned y=0;y<4000;y++){
            for(unsigned x=0;x<160;x++)check(pixels[y*stride+x]==0xc7);
            for(unsigned x=160+w*2;x<stride;x++)check(pixels[y*stride+x]==0xc7);
        }
        for(unsigned at=stride*4000;at<0x3000000;at++)check(pixels[at]==0xc7);
        print("AUTO_SIZE_FRAME ");number(w);print("x4000 output_height=");number(dest[i]);print(" passed\n");
    }
#ifdef TEST_WET
    for(unsigned i=0;i<3;i++){
        reset();completed=i;diagnostic=1;frame_grain=0;frame_halation=0;frame_vignette=0;frame_wet=1;
        unsigned w=widths[i],stride=canvas[i]*2;
        report[40+0x90/4]=report[40+0x9c/4]=report[40+0xa4/4]=(4000u<<16)|w;
        report[40+0x94/4]=(4000u<<16)|canvas[i];
        report[40+0x74/4]=report[40+0x78/4]=dest[i];
        unsigned char*pixels=(void*)0x7a000000;
        memset(pixels,0xc7,0x3000000);
        for(unsigned y=0;y<4000;y++)for(unsigned x=0;x<w;x++){
            pixels[y*stride+160+2*x]=(x&1)?180:80;
            pixels[y*stride+161+2*x]=x<w/2?50:200;
        }
        check(!take_lease_test());
        check(opens==1&&closes==1&&!held_lock&&!report[345]&&report[349]==w*4000);
        for(unsigned y=0;y<4000;y++){
            for(unsigned x=0;x<160;x++)check(pixels[y*stride+x]==0xc7);
            for(unsigned x=0;x<w;x++)check(pixels[y*stride+160+2*x]==128);
            for(unsigned x=160+w*2;x<stride;x++)check(pixels[y*stride+x]==0xc7);
        }
        check(pixels[161]<60&&pixels[161+w]>pixels[161]+100);
    }
    print("WET_AUTO_LMS_PIXELS_PASSED\n");
#endif
    grain_remove();print("AUTO_LEASE_PASSED checks=");number(checks);print("\n");stop();
}
