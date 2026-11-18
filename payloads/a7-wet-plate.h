/* Pure final-stage UYVY renderer. No camera I/O; full/studio BT.709. */
#ifndef A7_WET_PLATE_H
#define A7_WET_PLATE_H
static int a7_wet_clip(int x){return x<0?0:x>255?255:x;}
static int a7_wet_rnd(int x,int d){return x<0?-((-x+d/2)/d):(x+d/2)/d;}
static int a7_wet_gray(int y,int dr,int dg,int db,int limited){
 /* Preserve gamut clipping at each RGB channel before the blue-biased mix.
    Knots match the project's RGB .cube, in hundredths -> thousandths. */
 static const int in[]={0,10,25,50,75,91,100};
 static const int out[]={0,18,105,500,890,985,1000};
 int lum=10*a7_wet_clip(y+dr)+32*a7_wet_clip(y+dg)+58*a7_wet_clip(y+db);
 int k=0;while(k<5 && lum>255*in[k+1])++k;
 int step=in[k+1]-in[k];
 int value=a7_wet_rnd(255*step*out[k]+(lum-255*in[k])*(out[k+1]-out[k]),1000*step);
 return limited?16+a7_wet_rnd(value*219,255):value;
}
static int a7_wet_render(unsigned char *p,unsigned long size,unsigned long stride,unsigned w,unsigned h,unsigned limited){
 if(!p||!w||!h||(w&1)||w>16384||h>16384||limited>1)return -1;
 unsigned long row=(unsigned long)w*2;
 if(stride<row||size<row||h-1>(size-row)/stride)return -1;
 for(unsigned j=0;j<h;j++){
  unsigned char *q=p+(unsigned long)j*stride;
  for(unsigned i=0;i<w;i+=2,q+=4){
   int cb=q[0]-128,cr=q[2]-128, y0=q[1],y1=q[3];
   int d=limited?224:255;
   int dr=a7_wet_rnd(cr*40154,d*100), dg=a7_wet_rnd(-cb*4777-cr*11938,d*100), db=a7_wet_rnd(cb*47318,d*100);
   if(limited){y0=a7_wet_rnd((y0-16)*255,219);y1=a7_wet_rnd((y1-16)*255,219);}
   q[0]=q[2]=128;q[1]=(unsigned char)a7_wet_gray(y0,dr,dg,db,limited);q[3]=(unsigned char)a7_wet_gray(y1,dr,dg,db,limited);
  }
 }
 return 1;
}

#endif
