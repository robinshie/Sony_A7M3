/* Read-only main-menu witness. Writes one bounded temporary report only. */
#define A7_RUNTIME_LIBRARY_ONLY
#include "../payloads/a7-runtime-probe.c"
#define MAX_PARENTS 64
#define MAX_CHILDREN 32
static struct {uint32_t lo,hi;} ranges[1024];
static unsigned range_count;
typedef struct { uint32_t pointer, vtable, title, process, exec; } Child;
static struct {
    uint32_t magic, version, bytes, status, view_base, caution_base;
    uint32_t manager[2], manager_vtable[28], root[10], count, overflow;
    struct {uint32_t address, words[10];Child children[MAX_CHILDREN];} parents[MAX_PARENTS];
    uint32_t ancestor_count;
    struct {uint32_t source,address,words[10],pages[32][11];} ancestors[8];
} witness;
static int span(uint32_t address,uint32_t bytes) {
    if(bytes>~address) return 0;
    uint32_t end=address+bytes;
    unsigned lo=0,hi=range_count;
    while(lo<hi) {unsigned mid=lo+(hi-lo)/2;if(ranges[mid].hi<=address)lo=mid+1;else hi=mid;}
    if(lo==range_count||ranges[lo].lo>address) return 0;
    while(ranges[lo].hi<end) {
        uint32_t next=ranges[lo].hi;
        if(++lo==range_count||ranges[lo].lo!=next)return 0;
    }
    return 1;
}
static int safe_copy(uint32_t address,uint32_t *to,unsigned words) {
    if((address&3)||words>256||!span(address,words*4)) return 0;
    const volatile uint32_t *p=(const volatile uint32_t *)(uintptr_t)address;
    for(unsigned i=0;i<words;++i)to[i]=p[i];
    return 1;
}
static int parse_maps(void) {
    if(report.maps_n<=0)return 0;
    for(const char *p=report.maps;*p;) {
        const char *end=p;uint32_t lo=hex(&end);
        if(*end++!='-')return 0;
        uint32_t hi=hex(&end);
        /* Exclude device/shared mappings and unrelated mapped files. Following
         * a false-positive pointer into a readable device mapping can SIGBUS. */
        const char *name=end;
        for(unsigned field=0;field<4;++field) {
            while(*name==' ')name++;
            while(*name&&*name!=' '&&*name!='\n')name++;
        }
        while(*name==' ')name++;
        int known=contains(p,"/usr/lib/viewUnified2.so")||contains(p,"/usr/lib/CautionConfig.so")||
                  contains(p,"/usr/lib/a7fl.so")||contains(p,"[heap]")||!*name||*name=='\n';
        if(end[0]==' '&&end[1]=='r'&&end[4]=='p'&&known) {
            if(range_count==1024)return 0;
            ranges[range_count].lo=lo;ranges[range_count++].hi=hi;
        }
        if(contains(p,"r-xp 00000000")) {
            if(contains(p,"/usr/lib/viewUnified2.so"))report.view_base=lo;
            if(contains(p,"/usr/lib/CautionConfig.so"))report.caution_base=lo;
        }
        while(*p&&*p!='\n')p++;if(*p)p++;
    }
    return 1;
}
static uint32_t property(uint32_t node,unsigned key) {
    uint32_t words[4],p[2],entry[3];
    if(!safe_copy(node,words,4)||!safe_copy(words[3],p,2)||p[1]>31||p[0]>~0u-12*(p[1]+1)) return ~0u;
    for(unsigned i=0;i<=p[1];++i) {
        if(!safe_copy(p[0]+12*i,entry,3)) return ~0u;
        if(entry[0]==key) return entry[2];
    }
    return ~0u;
}
static uint32_t ticks(void) {
#ifdef NATIVE_MENU_PROBE_TEST
    extern uint32_t native_menu_probe_test_time(void);
    return native_menu_probe_test_time();
#else
    uint32_t tv[2];
    if(sc3(78,(long)tv,0,0)<0)return 0;
    return tv[0]*1000+tv[1]/1000;
#endif
}
static void scan_nodes(void) {
    uint32_t started=ticks();
    witness.view_base=report.view_base;witness.caution_base=report.caution_base;
    if(!report.view_base||!report.caution_base)return;
    witness.status=1;
    safe_copy(report.caution_base+0xa75ff4,witness.root,10);
    if(safe_copy(report.view_base+0xa61c18,witness.manager,2))
        safe_copy(witness.manager[0]-8,witness.manager_vtable,28);
    if(!span(report.view_base+0xa61c10,0xa8df9c-0xa61c10)){witness.status=2;return;}
    for(uint32_t off=0xa61c10;off+40<=0xa8df9c;off+=4) {
        uint32_t node[10],children[MAX_CHILDREN];unsigned hit=0;
        if(!(off&0x3ff)&&ticks()-started>2000){witness.status=4;break;}
        const volatile uint32_t *p=(const volatile uint32_t *)(uintptr_t)(report.view_base+off);
        if(p[0]!=report.caution_base+0x918ec8) continue;
        for(unsigned i=0;i<10;++i)node[i]=p[i];
        if(!node[2]||node[2]>MAX_CHILDREN||!safe_copy(node[1],children,node[2])) continue;
        for(unsigned i=0;i<node[2];++i)
            if(children[i]==report.caution_base+0xa75ff4 ||
               (property(children[i],0xe)==40&&property(children[i],0)==0x0204e0fb)) ++hit;
        if(hit!=1) continue;
        if(witness.count==MAX_PARENTS) {witness.overflow=1;break;}
        unsigned at=witness.count++;
        witness.parents[at].address=report.view_base+off;
        for(unsigned i=0;i<10;++i) witness.parents[at].words[i]=node[i];
        for(unsigned i=0;i<node[2];++i) {
            Child *c=&witness.parents[at].children[i];c->pointer=children[i];
            safe_copy(children[i],&c->vtable,1);
            c->title=property(children[i],0);c->process=property(children[i],0xe);
            c->exec=property(children[i],0xc);
        }
        if(node[4]&&node[5]==3&&witness.ancestor_count<8) {
            unsigned duplicate=0;
            for(unsigned i=0;i<witness.ancestor_count;++i)duplicate|=witness.ancestors[i].address==node[4];
            uint32_t ancestor[10],pages[32];
            if(!duplicate&&safe_copy(node[4],ancestor,10)&&ancestor[0]==report.caution_base+0x918ec8&&
               ancestor[2]>0&&ancestor[2]<=32&&safe_copy(ancestor[1],pages,ancestor[2])) {
                unsigned n=witness.ancestor_count++;
                witness.ancestors[n].source=report.view_base+off;witness.ancestors[n].address=node[4];
                for(unsigned i=0;i<10;++i)witness.ancestors[n].words[i]=ancestor[i];
                for(unsigned i=0;i<ancestor[2];++i) {
                    witness.ancestors[n].pages[i][0]=pages[i];
                    safe_copy(pages[i],witness.ancestors[n].pages[i]+1,10);
                }
            }
        }
    }
    if(witness.status==1) witness.status=3;
}
__attribute__((constructor)) static void capture(void) {
    witness.magic=0x41374e4d;witness.version=2;witness.bytes=sizeof witness;
    report.maps_n=read_proc("/proc/self/maps",report.maps,sizeof report.maps);
    if(!parse_maps())goto finish;
    scan_nodes();
finish:
    sc3(10,(long)"/tmp/jiritsu/libJit.so",0,0);
    long fd=sc3(5,(long)"/tmp/jiritsu/a7flnodes.bin",1|64|128,0600);
    if(fd>=0) {
        long n=0;
        while(n<(long)sizeof witness) {
            long wrote=sc3(4,fd,(long)((char *)&witness+n),sizeof witness-n);
            if(wrote<=0) break;
            n+=wrote;
        }
        sc3(118,fd,0,0);sc3(6,fd,0,0);
    }
}
