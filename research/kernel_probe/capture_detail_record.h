/* 176 words per snapshot, bounded metadata only; no physical pixel reads. */
#ifndef DETAIL_BARRIER
#define DETAIL_BARRIER() __asm__ volatile("" ::: "memory")
#endif
static void detail_snapshot(unsigned *out, const unsigned *regs, unsigned sequence)
{
    unsigned i, input=0,node=0,child0=0,child8=0;
    int status[5];
    out[0]=2;out[1]=sequence;
    for(i=0;i<8;i++)out[2+i]=regs[(const unsigned[]){0,1,2,3,4,5,6,13}[i]];
    /* params 240B, source object 32B, node 32B, first child 32B, geometry child 288B */
    status[0]=DETAIL_READ(out+10,regs[1],240);
    input=regs[5];status[1]=DETAIL_READ(out+70,input,32);
    if(!status[1])node=out[74];
    status[2]=DETAIL_READ(out+78,node,32);
    if(!status[2]){child0=out[78];child8=out[80];}
    status[3]=DETAIL_READ(out+86,child0,32);
    status[4]=DETAIL_READ(out+94,child8,288);
    for(i=0;i<5;i++)out[166+i]=status[i];
    out[171]=input;out[172]=node;out[173]=child0;out[174]=child8;
    out[175]=sequence;DETAIL_BARRIER();out[0]=3;
}
