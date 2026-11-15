"""Validate the installed settings and migrate a copy, without camera writes."""
import ctypes as C
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SOURCE=r'''
#include "a7-fl-runtime-prefs.h"
int inspect(const uint8_t *raw,const uint8_t *hash,const char *build,int *out) {
 struct a7_fl_preference p;
 uint8_t check[128];
 if(a7_fl_preference_decode(&p,raw,128,hash,build))return -1;
 if(a7_fl_preference_encode(check,&p,hash,build))return -2;
 for(unsigned i=0;i<128;i++)if(check[i]!=raw[i])return -3;
 out[0]=p.schema;out[1]=p.generation;out[2]=p.enabled;
 int old[3][16];
 for(int b=0;b<3;b++){
  struct a7_fl_preference v=p;a7_fl_preference_switch(&v,b+1);
  for(int f=0;f<8;f++)old[b][f]=v.parameters[f];
  for(int f=0;f<7;f++)old[b][f+8]=v.film[b][f];
  old[b][15]=v.vignette[b];
 }
 if(a7_fl_preference_migrate_film(&p)<0)return -4;
 if(a7_fl_preference_encode(check,&p,hash,build))return -5;
 struct a7_fl_preference round;
 if(a7_fl_preference_decode(&round,check,128,hash,build))return -6;
 for(int b=0;b<6;b++){
  a7_fl_preference_switch(&round,b+1);
  for(int f=0;f<16;f++){
   int value=f<8?round.parameters[f]:f==15?round.vignette[b]:round.film[b][f-8];
   out[3+b*16+f]=value;
   if(b<3 && value!=old[b][f])return -7;
   if(out[0]<6&&b>=3&&value!=(f==6?3:0))return -8;
  }
 }
 return 0;
}
'''

def decoder():
    out=ROOT/'.lab/six-look-settings'
    out.mkdir(exist_ok=True)
    source=out/'decode.c';source.write_text(SOURCE)
    library=out/'decode.dylib'
    flags=['SIX_LOOKS','FILM_CONTROLS','CAPTURE_HALATION','CAPTURE_VIGNETTE','DUAL_LOOK','LEICA_LOOK','LOOK_BANKS']
    subprocess.run(['clang','-dynamiclib','-O2','-Wall','-Wextra','-Werror',
                    *('-DA7_FL_'+f for f in flags),'-I'+str(ROOT/'payloads'),str(source),
                    str(ROOT/'payloads/a7-fl-runtime-prefs.c'),str(ROOT/'payloads/a7-fl-runtime.c'),
                    '-o',str(library)],check=True)
    call=C.CDLL(str(library)).inspect
    call.argtypes=[C.c_char_p,C.c_char_p,C.c_char_p,C.POINTER(C.c_int)]
    call.restype=C.c_int
    return call

def validate(call,raw,work=False):
    import zlib
    if len(raw)!=128:raise ValueError('Expected complete 128-byte settings')
    if work:
        if raw[:8]!=b'A7FLW001':raise ValueError('Unknown work record magic')
        if zlib.crc32(raw[:124])!=int.from_bytes(raw[124:],'little'):raise ValueError('Work record CRC')
        raw=b'A7FLP001'+raw[8:124]
        raw+=zlib.crc32(raw).to_bytes(4,'little')
    h=hashlib.sha256((ROOT/'.lab/native-fl-01/00030004.bin').read_bytes()).digest()
    out=(C.c_int*99)()
    code=call(raw,h,b'37114_13.2026020901'.ljust(24,b'\0'),out)
    if code:raise ValueError(f'Installed settings migration failed: {code}')
    return dict(schema=out[0],generation=out[1],mode=out[2],
                banks=[list(out)[3+b*16:3+(b+1)*16] for b in range(6)])
