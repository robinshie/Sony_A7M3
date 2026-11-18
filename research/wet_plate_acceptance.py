"""Read installed files, wet catalog and capture state after cold boot; never save."""
import argparse,ctypes as C,json,struct,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from local import LAB,BUILD_ID,require,file_sha,sha
from research.six_look_settings import decoder,validate

class Look(C.Structure):
 _fields_=[('slot',C.c_uint32),('id',C.c_char*49),('name',C.c_char*64),('base',C.c_uint8),('values',C.c_int8*16),('wet',C.c_uint8)]
class Catalog(C.Structure):
 _fields_=[(x,C.c_uint32) for x in ('generation','next_slot','active','count','hidden_builtin','wet_builtin','wet_initialized')]+[('looks',Look*16)]
SOURCE=r'''
#include <stdint.h>
extern void*dlopen(const char*,int);extern void*dlsym(void*,const char*);extern int dlclose(void*);
static long sc(long n,long a,long b,long c){register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;__asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;}
static int readfile(const char*p,char*b,unsigned cap){long fd=sc(5,(long)p,0x8000,0);if(fd<0)return fd;unsigned pos=0;long n=0;while(pos<cap){n=sc(3,fd,(long)(b+pos),cap-pos);if(n<=0)break;pos+=n;}long closed=sc(6,fd,0,0);return n<0?(int)n:closed?(int)closed:(int)pos;}
static struct {uint32_t magic;int valid,status[17],lengths[4];char kernel[4096],selection[32],diagnostic[32],uptime[64];} r;
__attribute__((constructor))static void run(void){
 r.magic=0x57455431;void*h=dlopen("/usr/lib/a7fl.so",6);
 if(h){const int*(*get)(void)=(void*)dlsym(h,"a7_fl_status");if(get){const int*s=get();if(s){for(unsigned i=0;i<17;i++)r.status[i]=s[i];r.valid=1;}}dlclose(h);}
 r.lengths[0]=readfile("/sys/module/a7capwet/parameters/report",r.kernel,sizeof r.kernel);
 r.lengths[1]=readfile("/sys/module/a7capwet/parameters/selection",r.selection,sizeof r.selection);
 r.lengths[2]=readfile("/sys/module/a7capwet/parameters/diagnostic",r.diagnostic,sizeof r.diagnostic);
 r.lengths[3]=readfile("/proc/uptime",r.uptime,sizeof r.uptime);
 long f=sc(5,(long)"/tmp/jiritsu/wetaccept.bin",1|64|128,0600);if(f<0)return;unsigned pos=0;while(pos<sizeof r){long n=sc(4,f,(long)((char*)&r+pos),sizeof r-pos);if(n<=0)break;pos+=n;}long closed=sc(6,f,0,0);if(pos!=sizeof r||closed)sc(10,(long)"/tmp/jiritsu/wetaccept.bin",0,0);
}
'''
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path,required=True);p.add_argument('--before',type=Path,required=True);p.add_argument('--live',action='store_true');a=p.parse_args()
 package=a.package.resolve();before=a.before.resolve();mp=json.loads((package/'27/module-proof.json').read_text());kp=json.loads((Path(mp['kernel_bundle'])/'proof.json').read_text())
 out=LAB/'wet-plate-acceptance'/str(time.time_ns());out.mkdir(parents=True)
 (out/'read.c').write_text(SOURCE)
 subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os','-nostdlib','-shared','-Wall','-Wextra','-Werror','-Wl,-z,noexecstack',str(out/'read.c'),'-o',str(out/'read.so')],check=True)
 subprocess.run(['clang','-dynamiclib','-O2','-Wall','-Wextra','-Werror','payloads/a7-fl-custom.c','-o',str(out/'catalog.dylib')],cwd=ROOT,check=True)
 call=C.CDLL(str(out/'catalog.dylib')).a7_custom_decode;call.argtypes=[C.c_char_p,C.c_uint,C.POINTER(Catalog)];call.restype=C.c_int
 def decode(raw):
  c=Catalog();require(call(raw,len(raw),C.byref(c))==0,'Catalog rejected by firmware decoder')
  d={name:getattr(c,name) for name,_ in Catalog._fields_[:-1]};d['looks']=[dict(slot=l.slot,id=l.id.decode(),name=l.name.decode(),base=l.base,values=list(l.values),wet=l.wet) for l in list(c.looks)[:c.count]];return d
 dec=decoder();old=max([decode((before/f'A7CU{i}.CFG').read_bytes()) for i in range(2)],key=lambda c:c['generation'])
 oldprefs=max([validate(dec,(before/f'A7FL{i}.CFG').read_bytes()) for i in range(2)],key=lambda c:c['generation'])
 if not a.live:print('WET_READER_PREPARED',out);return
 from camera import service,handoff
 def collect(camera,action):
  require(action=='settings-snapshot','Unexpected action');f=service.Factory(camera)
  require(f.contents('/version.txt')==BUILD_ID and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Wrong camera')
  for rev,name in [(27,'/usr/lib/a7fl.so'),(2701,'/usr/share/app/string_simplifiedchinese.uxc'),(2702,'/usr/share/app/string_english.uxc')]:
   m=json.loads((package/str(rev)/'manifest.json').read_text());raw=f.contents(name,maximum=m['new']['size']+16);(out/f'installed-{rev}.bin').write_bytes(raw);require(len(raw)==m['new']['size'] and sha(raw)==m['new']['sha256'],'Installed file differs')
  prefs=[];cats=[]
  for i in range(2):
   for group in ('A7FL','A7FW','A7CU'):
    name=f'{group}{i}.CFG';raw=f.contents('/setting/'+name,maximum=4096);(out/name).write_bytes(raw)
    if group=='A7CU':cats.append(decode(raw))
    elif group=='A7FL':prefs.append(validate(dec,raw))
    else:validate(dec,raw,work=True)
  saved=max(prefs,key=lambda d:d['generation']);catalog=max(cats,key=lambda d:d['generation'])
  raw=f.run((out/'read.so').read_bytes(),'wetaccept.bin');(out/'read.bin').write_bytes(raw)
  require(len(raw)==4316,'Report length differs');head=struct.unpack_from('<23i',raw);require(head[0]==0x57455431 and head[1]==1,'Resident missing')
  rt=dict(zip('prepared installed fault parents dirty generation runtime_ready last_error mode'.split(),head[2:11]));rt['parameters']=list(head[11:19])
  parts=[];pos=92
  for n,cap in zip(head[19:23],(4096,32,32,64)):
   require(0<n<cap,'Missing live kernel field');parts.append(raw[pos:pos+n].decode().strip());pos+=cap
  v=[int(x) for x in parts[0].split(',')];require(len(v)==368 and v[12:16]==kp['source_id'],'Kernel identity differs')
  kernel=dict(armed=bool(v[1] and v[11] and not v[5]),selection=int(parts[1]),diagnostic=int(parts[2]),completed=v[355],failed=v[357])
  selected=next((l for l in catalog['looks'] if l['slot']==catalog['active']),None)
  mode=selected['base'] if selected else saved['mode'];values=selected['values'] if selected else saved['banks'][max(0,mode-1)]
  wet=bool(selected['wet'] or selected['id']=='wet-plate-hard-bw-v1') if selected else bool((catalog['wet_builtin']>>max(0,mode-1))&1)
  wire=1 if mode>=4 else mode;desired=(int(wet)<<16)|(wire<<14)|((values[15]+9)<<9)|((values[9]+9)<<4)|values[8] if mode else 0
  original={l['id']:l for l in old['looks']};now={l['id']:l for l in catalog['looks']}
  changes=[key for key,l in original.items() if key not in now or any(now[key][field]!=l[field] for field in ('slot','base','values','name'))]
  result=dict(runtime=rt,kernel=kernel,uptime=parts[3],catalog=catalog,saved=saved,original_look_changes=changes,old_builtin_banks_unchanged=saved['banks']==oldprefs['banks'],kernel_matches_saved=kernel['selection']==desired,persistent_writes=False)
  (out/'readback.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
  require(rt['installed']==1 and rt['prepared']==1 and not rt['fault'] and not rt['last_error'],'Runtime fault')
  require(kernel['armed'] and kernel['diagnostic']==0 and not kernel['failed'],'Kernel not healthy production mode')
  require(catalog['wet_initialized']==1 and catalog['count']==old['count']+1 and catalog['hidden_builtin']==old['hidden_builtin'] and not changes and result['old_builtin_banks_unchanged'],'Original settings or catalog migration differ')
  require('wet-plate-hard-bw-v1' in now and now['wet-plate-hard-bw-v1']['wet']==1,'FL7 missing')
  if not rt['dirty']:require(kernel['selection']==desired and rt['mode']==mode and rt['parameters']==values[:8],'Saved selection differs from runtime')
  result['verified']=True;(out/'verified.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print('WET_ACCEPTANCE',out,flush=True)
 service.perform=collect;handoff.SWITCH+=' --host-identity-check';handoff.run('settings-snapshot')
if __name__=='__main__':main()
