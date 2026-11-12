#include "a7-fl-capture-controls.h"
#include "a7-fl-module-data.h"
extern void cc_check(int,const char *);
extern void cc_pack(const uint8_t *,unsigned);
static struct a7_capture_controls ctx;
static uint8_t live[2][1280];
static unsigned writes,fail_at,fail_mode;
static void copy_bytes(uint8_t *d,const uint8_t *s,unsigned n){for(unsigned i=0;i<n;i++)d[i]=s[i];}
static int eq(const uint8_t *a,const uint8_t *b,unsigned n){for(unsigned i=0;i<n;i++)if(a[i]!=b[i])return 0;return 1;}
static int size(uint32_t id){return id==0x30005||id==0x30006?1280:-1;}
static int attr(uint32_t id){return size(id)==1280?8:-1;}
static int read_lut(uint32_t id,void *out){if(size(id)!=1280)return -1;copy_bytes(out,live[id-0x30005],1280);return 1280;}
static int write_lut(uint16_t mode,uint32_t id,const void *data){
    cc_check(mode==3&&size(id)==1280,"CAP API identity");writes++;
    if(writes==fail_at&&fail_mode==1)return -1;
    copy_bytes(live[id-0x30005],data,1280);
    if(writes==fail_at){if(fail_mode==3)live[id-0x30005][1215]^=1;return -1;}
    return 1280;
}
static int signed7(unsigned n){n&=127;return n<64?(int)n:(int)n-128;}
static int pack_code(unsigned n,unsigned level){int v=n<128?(int)n:(int)n-256;return signed7((unsigned)(level==8?v:a7_fl_floor_div(v*(int)level,8)));}
static void reset(void){
    uint8_t *p=(void *)&ctx;for(unsigned i=0;i<sizeof ctx;i++)p[i]=0;
    const uint8_t *stock[]={a7_pkg_original[1],a7_pkg_original[2]},*legacy[]={a7_pkg_capture1,a7_pkg_capture2};
    struct a7_fl_api api={size,attr,read_lut,write_lut};
    for(unsigned t=0;t<2;t++)copy_bytes(live[t],stock[t],1280);
    writes=fail_at=fail_mode=0;
    cc_check(a7_capture_prepare(&ctx,&api,stock,legacy,a7_pkg_expand,a7_pkg_compress)==0,"CAP control preparation");
}
static void validate(unsigned t,const A7FLColorParams *p,int pack){
    uint8_t out[1282];out[0]=0x5a;out[1281]=0xa5;
    cc_check(a7_capture_generate(&ctx,t,p,out+1)==0,"CAP generation");
    cc_check(out[0]==0x5a&&out[1281]==0xa5&&eq(out+1216,ctx.stock[t]+1215,65),"CAP output extent and calibration tail");
    for(unsigned i=0;i<1215;i++){
        unsigned v=out[i+1];
        cc_check(t?v<128:(v<64||v>=192),"CAP encoding");
        for(unsigned level=1;level<=8;level++){
            int d=pack_code(v,level)-pack_code(ctx.stock[t][i],level),limit=i<405?24:32;
            cc_check(d>=-limit&&d<=limit,"CAP bounded at all native levels");
        }
    }
    for(unsigned b=0;b<81;b++)for(unsigned a=1;a<5;a++)
        cc_check((int)(a*64)+signed7(out[1+a*81+b])>=(int)((a-1)*64)+signed7(out[1+(a-1)*81+b]),"CAP monotonic luminance");
    if(pack)for(unsigned level=1;level<=8;level++)cc_pack(out+1,level);
}
void a7_capture_controls_tests(void){
    reset();A7FLColorParams zero={0,0,0,0,0},p=zero;
    uint8_t neutral[1280],other[1280],before[2][1280];
    for(unsigned t=0;t<2;t++){
        cc_check(a7_capture_generate(&ctx,t,&zero,neutral)==0,"stronger default");
        unsigned old_sum=0,new_sum=0;
        for(unsigned i=0;i<1215;i++){
            int a=signed7(ctx.legacy[t][i])-signed7(ctx.stock[t][i]),b=signed7(neutral[i])-signed7(ctx.stock[t][i]);
            old_sum+=(unsigned)(a<0?-a:a);new_sum+=(unsigned)(b<0?-b:b);
        }
        cc_check(new_sum>old_sum*12/10,"default has materially stronger source deltas");
        validate(t,&zero,1);
        for(unsigned f=0;f<5;f++)for(int v=f==3?0:-9;v<=9;v++){
            p=zero;int values[5]={0,0,0,0,0};values[f]=v;
            p=(A7FLColorParams){values[0],values[1],values[2],values[3],values[4]};
            validate(t,&p,v==-9||v==9);
            cc_check(a7_capture_generate(&ctx,t,&p,other)==0,"slider table");
            cc_check(v==0||!eq(neutral,other,1215),"every nonzero slider changes capture source");
        }
        for(unsigned mask=0;mask<32;mask++){
            p=(A7FLColorParams){mask&1?9:-9,mask&2?9:-9,mask&4?9:-9,mask&8?9:0,mask&16?9:-9};
            validate(t,&p,1);
        }
        p=(A7FLColorParams){-7,8,-5,6,7};
        cc_check(a7_capture_generate(&ctx,t,&p,other)==0&&a7_capture_recognize(&ctx,t,other)==1,"unsaved CAP preview recognition");
        other[1215]^=1;cc_check(a7_capture_recognize(&ctx,t,other)==0,"foreign CAP tail refusal");
        p=zero;p.contrast=10;copy_bytes(other,neutral,1280);
        cc_check(a7_capture_generate(&ctx,t,&p,other)<0&&eq(other,neutral,1280),"invalid input leaves output untouched");
    }
    /* Exhaustive tone combinations on host; QEMU checks all single values and corners. */
#ifdef A7_CC_EXHAUSTIVE
    for(int a=-9;a<=9;a++)for(int b=-9;b<=9;b++)for(int d=-9;d<=9;d++)for(int f=0;f<=9;f++)
        for(unsigned t=0;t<2;t++){
            p=(A7FLColorParams){a,b,d,f,0};
            cc_check(a7_capture_generate(&ctx,t,&p,other)==0,"exhaustive tone generation");
            for(unsigned i=0;i<405;i++)cc_check(signed7(other[i])>=ctx.low[t][i]&&signed7(other[i])<=ctx.high[t][i],"exhaustive projected tone bounds");
            for(unsigned i=0;i<81;i++)for(unsigned j=1;j<5;j++)cc_check((int)(j*64)+signed7(other[j*81+i])>=(int)((j-1)*64)+signed7(other[(j-1)*81+i]),"exhaustive monotonicity");
        }
#endif
    reset();copy_bytes(live[0],a7_pkg_capture1,1280);
    p=(A7FLColorParams){-7,8,-5,6,7};cc_check(a7_capture_generate(&ctx,1,&p,live[1])==0,"mixed legacy and preview setup");
    cc_check(a7_capture_adopt(&ctx,&zero)==0&&writes==0,"read-only known preimage adoption");
    cc_check(a7_capture_apply(&ctx,1,&zero)==0&&a7_capture_verify(&ctx,1,&zero)==0,"mixed preimages upgraded to stronger default");
    unsigned saved=writes;cc_check(a7_capture_apply(&ctx,1,&zero)==0&&writes==saved,"unchanged capture no-op");
    cc_check(a7_capture_apply(&ctx,1,&p)==0&&a7_capture_verify(&ctx,1,&p)==0,"dynamic update");
    cc_check(a7_capture_apply(&ctx,0,&p)==0&&eq(live[0],a7_pkg_original[1],1280)&&eq(live[1],a7_pkg_original[2],1280),"Off byte-exact restoration");
    for(unsigned mode=1;mode<=3;mode++)for(unsigned at=1;at<=2;at++){
        reset();cc_check(a7_capture_adopt(&ctx,&zero)==0&&a7_capture_apply(&ctx,1,&zero)==0,"failure precondition");
        for(unsigned t=0;t<2;t++)copy_bytes(before[t],live[t],1280);
        writes=0;fail_at=at;fail_mode=mode;
        int rc=a7_capture_apply(&ctx,1,&p);
        cc_check(rc==(mode==3?A7_FL_RECOVERY:A7_FL_WRITE),"injected partial CAP failure classification");
        for(unsigned t=0;t<2;t++)cc_check(mode==3&&t==at-1?live[t][1215]!=before[t][1215]:eq(live[t],before[t],1280),"rollback exact known preimages; preserve foreign bytes");
    }
    reset();live[1][1215]^=1;cc_check(a7_capture_adopt(&ctx,&zero)==A7_FL_FOREIGN&&writes==0,"foreign startup no writes");
    reset();cc_check(a7_capture_adopt(&ctx,&zero)==0,"adopt original");live[1][1215]^=1;
    cc_check(a7_capture_apply(&ctx,1,&zero)==A7_FL_FOREIGN&&writes==0,"foreign concurrent state no writes");
}
