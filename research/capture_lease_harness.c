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
#include "kernel_probe/capture_vignette_record.h"
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
    held_lock=lock_busy=atomic_context=opens=closes=0;
    bad_mapping=bad_cache=0;
#ifdef TEST_GRAIN
    barriers=corrupt_at=0;
#endif
    native_open=wrapped_open;native_close=wrapped_close;
}
void guest_main(void){
    (void)source_publish;(void)source_remove;(void)take_early_record;
#ifdef TEST_GRAIN
    unsigned i,changed=0;unsigned char *pixels=(void *)0x7a000000;
#endif
#ifdef TEST_FILM
    unsigned bank,c;
    (void)disarmed;
    (void)module;(void)sysfs_create_bin_file;(void)sysfs_remove_bin_file;
    check(!grain_publish()&&report[352]==1);
#ifdef TEST_VIGNETTE
    for(bank=0;bank<2;bank++)for(c=0;c<8;c++){
#else
    for(bank=0;bank<2;bank++)for(c=0;c<5;c++){
#endif
        test_physical=bank?0x24000000:0x1a000000;pixels=(void *)(test_physical+0x60000000);
        frame_grain=c<2?0:9;frame_halation=c==0||c==3?-9:c==1||c==4?9:0;
#ifdef TEST_VIGNETTE
        frame_vignette=c%3==0?-9:c%3==1?0:9;
        diagnostic=c>=5;completed=c-5;
        if(diagnostic){frame_grain=0;frame_halation=0;frame_vignette=c==5?-9:c==6?0:9;}
#endif
        for(i=0;i<12160*4000;i++)pixels[i]=(i%12160<160)?0xc7:(i&1)?((i%12160)/2<3080?105:250):128;
        reset();check(!take_lease_test()&&report[310]==1&&opens==1&&closes==1&&!held_lock);
        check(report[344]==3&&!report[345]&&report[349]==((frame_grain||frame_halation
#ifdef TEST_VIGNETTE
          ||frame_vignette
#endif
        )?24000000:0)&&!report[350]);
        check(report[359]==test_physical&&report[360]==test_physical+0x60000000&&report[361]==frame_grain);
        changed=0;
        for(i=0;i<12160*4000;i++){
            unsigned char before=(i%12160<160)?0xc7:(i&1)?((i%12160)/2<3080?105:250):128;
            if(pixels[i]!=before){check(i%12160>=160);if(frame_halation<=0)check(i&1);if(!frame_grain&&frame_halation<0
#ifdef TEST_VIGNETTE
        &&frame_vignette<=0
#endif
        ){check(pixels[i]<before);}
                changed++;
            }
        }
#ifdef TEST_VIGNETTE
        check((changed>0)==(frame_grain||frame_halation||frame_vignette));
        if(diagnostic){
            unsigned *sample=completed==0?vignette_sample0:completed==1?vignette_sample1:vignette_sample2;
            unsigned verify[160];sample_vignette(verify,pixels+160);
            check(sample[0]==0x41375647&&sample[1]==completed&&(int)sample[4]==frame_vignette);
            check(!memcmp(verify,sample+166,sizeof verify));
            check(!memcmp(sample+6+128,sample+166+128,32*sizeof(unsigned)));
            check((memcmp(sample+6,sample+166,128*sizeof(unsigned))!=0)==(frame_vignette!=0));
        }
        check(!unit[0x11]
#else
        check(changed>0&&!unit[0x11]
#endif
        &&*(unsigned short *)(unit+0x14)==1);
    }
#ifdef TEST_VIGNETTE
    diagnostic=0;reset();frame_vignette=10;check(take_lease_test()==-EINVAL&&closes==1&&!barriers);frame_vignette=0;
    reset();frame_grain=0;frame_halation=0;busy_attempts=3;
    check(!take_lease_test()&&report[363]==4&&opens==1&&closes==1&&!held_lock);
    reset();busy_attempts=64;
    check(take_lease_test()==-EBUSY&&report[363]==64&&!opens&&!closes&&!held_lock);
#endif
    reset();bad_mapping=1;check(take_lease_test()==-EINVAL&&closes==1&&!barriers);
    reset();bad_cache=1;check(take_lease_test()==-EINVAL&&closes==1&&!barriers);
    reset();frame_grain=10;check(take_lease_test()==-1&&closes==1&&!barriers);frame_grain=0;
    reset();report[257]^=4096;check(take_lease_test()==-EINVAL&&!opens&&!closes);
    test_physical=0x1a000000;
    grain_remove();
#elif defined(TEST_HALATION)
    {int err=grain_publish();if(err){print("HALO_INIT ");number((unsigned)err);print(" code ");number(report[359]);print(" values ");number(report[360]);print(" ");number(report[361]);print(" ");number(report[362]);print("\n");}check(!err&&report[352]==1);}
    unsigned bank;
    for(bank=0;bank<2;bank++)for(completed=0;completed<3;completed++){
        test_physical=bank?0x24000000:0x1a000000;
        pixels=(void *)(test_physical+0x60000000);
        frame_halation=completed==0?-9:completed==1?0:9;
        for(i=0;i<12160*4000;i++)pixels[i]=(i%12160<160)?0xc7:(i&1)?((i%12160)/2<3080?105:250):128;
        reset();check(!take_lease_test()&&report[310]==1&&opens==1&&closes==1&&!held_lock);
        check(!unit[0x11]&&*(unsigned short *)(unit+0x14)==1&&report[350]==0);
        check(!memcmp(halo[completed].actual,halo[completed].wanted,HBYTES));
        changed=0;
        for(i=0;i<12160*4000;i++){
            unsigned char before=(i%12160<160)?0xc7:(i&1)?((i%12160)/2<3080?105:250):128;
            if(pixels[i]!=before){check(i%12160>=160);check(frame_halation!=0);if(frame_halation<0)check((i&1)&&pixels[i]<before);changed++;}
        }
        check((changed>0)==(frame_halation!=0));
    }
    completed=0;frame_halation=-9;reset();corrupt_at=2;
    check(take_lease_test()==-EIO&&report[350]==2&&!unit[0x11]&&closes==1);
    reset();bad_mapping=1;check(take_lease_test()==-EINVAL&&closes==1&&!barriers);
    reset();bad_cache=1;check(take_lease_test()==-EINVAL&&closes==1&&!barriers);
    reset();report[257]^=4096;check(take_lease_test()==-EINVAL&&!opens&&!closes);
    reset();report[258]=1;check(take_lease_test()==-EINVAL&&!opens&&!closes);
    reset();ext[1]=0x1a000000;check(take_lease_test()==-EIO&&opens==1&&closes==1&&!barriers);
    test_physical=0x1a000000;
    grain_remove();
#else
#ifdef TEST_GRAIN
    for(i=0;i<12160*4000;i++)pixels[i]=(unsigned char)(i*37+53);
    check(!grain_publish()&&report[352]==1);
#endif
    reset();check(!take_lease_test());check(report[310]==1&&opens==1&&closes==1&&!held_lock);
    check(!unit[0x11]&&*(unsigned short *)(unit+0x14)==1);
#ifdef TEST_GRAIN
    check(report[344]==3&&report[345]==0&&report[346]>0&&report[350]==0);
#ifdef TEST_FULL
    check(report[349]==6000*4000);
#else
    check(report[349]==256*128);
#endif
    for(i=0;i<12160*4000;i++)if(pixels[i]!=(unsigned char)(i*37+53)){
        unsigned y=i/12160,x=(i%12160)/2;
#ifdef TEST_FULL
        check((i&1)&&y<4000&&x>=80&&x<6080);changed++;
#else
        check((i&1)&&y>=1936&&y<2064&&x>=2952&&x<3208);changed++;
#endif
    }
#ifdef TEST_FULL
    check(changed>1000000&&memcmp(grain.actual,grain.wanted,TB)==0);
    reset();corrupt_at=2;check(take_lease_test()==-EIO&&report[350]==2&&!unit[0x11]&&closes==1);
#else
    check(changed==report[346]);
    reset();corrupt_at=2;check(take_lease_test()==-EIO&&report[350]==1&&!unit[0x11]&&closes==1);
#endif
    grain_remove();
#endif
#endif
    reset();lock_busy=1;check(take_lease_test()==-EBUSY&&!opens&&!closes&&!held_lock);
    reset();atomic_context=1;check(take_lease_test()==-EWOULDBLOCK&&!opens&&!closes);
    reset();unit[0x11]=1;check(take_lease_test()==-ESTALE&&!opens&&!closes&&!held_lock);
    reset();unit[0x12]=1;check(take_lease_test()==-ESTALE&&!opens&&!closes&&!held_lock);
    reset();unit[0x13]=4;check(take_lease_test()==-ESTALE&&!opens&&!closes&&!held_lock);
    reset();report[184]=1;check(take_lease_test()==-EBUSY&&!opens&&!closes);
    reset();report[40+0xc0/4]=0;check(take_lease_test()==-EINVAL&&!opens&&!closes);
    reset();ext[3]=0x1000;check(take_lease_test()==-EIO&&opens==1&&closes==1&&!held_lock&&!unit[0x11]);
    print("LEASE_CALLBACK_PASSED checks=");number(checks);print("\n");stop();
}
