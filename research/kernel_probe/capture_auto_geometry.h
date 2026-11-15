/* Observed L/M/S source metadata. The native RC stage consumes source height
 * at +0xa6 and canvas/stride at +0x94. +0x74 is destination height: never
 * substitute it for source height before the native vertical resize. */
#include "a7-capture-geometry.h"
static int auto_geometry(struct a7_capture_geometry *out)
{
    const unsigned *o=report+40;
    if(o[0x7c/4]!=1 || o[0xa8/4]!=0x00010000 || o[0xac/4]!=0x00020101 ||
       o[0xb0/4] || o[0xb4/4]!=0x01010001 || o[0xb8/4]!=0x400 ||
       o[0x90/4]!=o[0x9c/4] || o[0x90/4]!=o[0xa4/4] || o[0xa0/4] ||
       o[0x74/4]<1 || o[0x74/4]>4000 || o[0x78/4]<o[0x74/4] ||
       o[0x78/4]-o[0x74/4]>7 || (o[0x78/4]&7))return -1;
    return a7_capture_geometry_decode(o[0xa4/4],o[0x94/4],o[0x98/4],o[0xc4/4],out);
}
