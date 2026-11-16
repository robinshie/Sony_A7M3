"""Differential JSON and independent catalog tests for the portable ARM implementation."""
import ctypes as C,json,subprocess,sys,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from custom_look_recipes import encode,FORMAT
from look_recipes import FIELDS
OUT=ROOT/'.lab/custom-look-native';OUT.mkdir(exist_ok=True)
subprocess.run(['cc','-dynamiclib','-Wall','-Wextra','-Werror','-O1',str(ROOT/'payloads/a7-fl-custom.c'),'-o',str(OUT/'custom.dylib')],check=True)
subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-Os','-Wall','-Wextra','-Werror','-ffreestanding','-fno-builtin','-c',str(ROOT/'payloads/a7-fl-custom.c'),'-o',str(OUT/'custom.o')],check=True)
class Look(C.Structure):_fields_=[('slot',C.c_uint32),('id',C.c_char*49),('name',C.c_char*64),('base',C.c_uint8),('values',C.c_int8*16)]
class Catalog(C.Structure):_fields_=[('generation',C.c_uint32),('next_slot',C.c_uint32),('active',C.c_uint32),('count',C.c_uint32),('looks',Look*16)]
a=C.CDLL(str(OUT/'custom.dylib'));a.a7_custom_parse.argtypes=[C.c_void_p,C.c_uint,C.POINTER(Look)]
item=dict(format=FORMAT,id='portrait-grain',name='人像颗粒',base='FL6',parameters=dict(zip(FIELDS,[0,0,0,0,0,0,3,0,1,0,0,0,0,0,0,0])))
raw=encode(item);look=Look();assert a.a7_custom_parse(raw,len(raw),C.byref(look))==0
assert look.name.decode()=='人像颗粒' and look.base==6 and look.values[8]==1
for i in range(len(raw.rstrip())):
 before=bytes(look);assert a.a7_custom_parse(raw,i,C.byref(look))<0 and bytes(look)==before
cat=Catalog();a.a7_custom_empty(C.byref(cat));old=bytes(cat);nextcat=Catalog()
assert a.a7_custom_append(C.byref(cat),C.byref(look),C.byref(nextcat))==0
assert bytes(cat)==old and nextcat.looks[0].slot==7 and nextcat.count==1
assert a.a7_custom_append(C.byref(nextcat),C.byref(look),C.byref(cat))==-2 and bytes(cat)==old
buf=C.create_string_buffer(2848);assert a.a7_custom_encode(C.byref(nextcat),buf)==0
restored=Catalog();assert a.a7_custom_decode(buf,2848,C.byref(restored))==0 and bytes(restored)==bytes(nextcat)
for index in range(2848):
 corrupted=bytearray(buf.raw);corrupted[index]^=1;before=bytes(restored)
 assert a.a7_custom_decode(bytes(corrupted),2848,C.byref(restored))<0 and bytes(restored)==before
for field,value in [('grain',10),('grain',True),('contrast',-10)]:
 bad=json.loads(raw);bad['parameters'][field]=value;data=json.dumps(bad).encode()
 assert a.a7_custom_parse(data,len(data),C.byref(look))<0
resolved=Look();assert a.a7_custom_resolve(C.byref(nextcat),7,C.byref(resolved))==0
assert a.a7_custom_resolve(C.byref(nextcat),6,C.byref(resolved))<0
report=dict(passed=True,scope='Host-executed portable C and ARM compilation; no camera integration',truncated_inputs=len(raw),corrupted_bytes=2848,source_sha256={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in ['payloads/a7-fl-custom.c','payloads/a7-fl-custom.h','research/custom_look_native_test.py']})
(OUT/'proof.json').write_text(json.dumps(report,indent=2)+'\n');print('CUSTOM_NATIVE_CATALOG_PASSED',report['truncated_inputs'],'truncations; 2848 corrupted byte cases')
