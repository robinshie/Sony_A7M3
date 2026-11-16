"""Read-only post-boot independent-look candidate verification; never install or save."""
import sys,time,json,hashlib,subprocess,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from camera import service,handoff
from local import LAB,BUILD_ID,require
from research.six_look_settings import decoder,validate
BASE=LAB/'native-fl-releases/update-v001-custom-looks-gw1l8spw'
BEFORE=BASE/'write-1794819564533584000'
FIX=LAB/'native-fl-releases/update-v001-custom-selected-hfjp6yjd'
SOURCE=r'''
#include <stdint.h>
extern void *dlopen(const char*,int);
extern void *dlsym(void*,const char*);
extern int dlclose(void*);
static long sc(long n,long a,long b,long c){
 register long r7 __asm__("r7")=n,r0 __asm__("r0")=a,r1 __asm__("r1")=b,r2 __asm__("r2")=c;
 __asm__ volatile("svc #0":"+r"(r0):"r"(r7),"r"(r1),"r"(r2):"memory","cc");return r0;
}
static struct {uint32_t magic;int valid;int status[17];char uptime[64];} report;
__attribute__((constructor))static void run(void){
 report.magic=0x5344494d;
 void*h=dlopen("/usr/lib/a7fl.so",6);
 if(h){const int*(*get)(void)=(void*)dlsym(h,"a7_fl_status");
 if(get){const int*s=get();if(s){for(unsigned i=0;i<17;i++)report.status[i]=s[i];report.valid=1;}}
 dlclose(h);}
 long fd=sc(5,(long)"/proc/uptime",0,0);if(fd>=0){sc(3,fd,(long)report.uptime,63);sc(6,fd,0,0);}
 fd=sc(5,(long)"/tmp/jiritsu/sdaccept.bin",1|64|128,0600);if(fd<0)return;
 sc(4,fd,(long)&report,sizeof report);sc(6,fd,0,0);
}
'''
def main():
 out=LAB/'custom-selected-acceptance'/str(time.time_ns());out.mkdir(parents=True)
 (out/'read.c').write_text(SOURCE)
 subprocess.run(['arm-none-eabi-gcc','-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os','-nostdlib','-shared','-Wall','-Wextra','-Werror','-Wl,-z,noexecstack',str(out/'read.c'),'-o',str(out/'read.so')],check=True)
 dec=decoder()
 def collect(camera,action):
  require(action=='settings-snapshot','Unexpected action');f=service.Factory(camera)
  require(f.contents('/version.txt')==BUILD_ID and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Identity mismatch')
  hashes={}
  for rev,path in [(20,'/usr/lib/a7fl.so'),(2001,'/usr/share/app/string_simplifiedchinese.uxc'),(2002,'/usr/share/app/string_english.uxc')]:
   m=json.loads(((FIX/'24' if rev==20 else BASE/str(rev))/'manifest.json').read_text());data=f.contents(path,maximum=m['new']['size']+16)
   require(len(data)==m['new']['size'] and hashlib.sha256(data).hexdigest()==m['new']['sha256'],'Installed file mismatch')
   hashes[path]=m['new']['sha256']
  slots=[]
  for i in range(2):
   raw=f.contents(f'/setting/A7FL{i}.CFG',maximum=160);(out/f'preference-{i}.bin').write_bytes(raw);slots.append(validate(dec,raw))
   raw=f.contents(f'/setting/A7FW{i}.CFG',maximum=160);(out/f'work-{i}.bin').write_bytes(raw);validate(dec,raw,work=True)
  require(slots[0]['generation']!=slots[1]['generation'] or slots[0]==slots[1],'Conflicting generations')
  saved=max(slots,key=lambda p:p['generation'])
  before=validate(dec,(BEFORE/'preference-before-0.bin').read_bytes())
  before1=validate(dec,(BEFORE/'preference-before-1.bin').read_bytes())
  before=max([before,before1],key=lambda p:p['generation'])
  catalogs=[]
  import zlib
  for i in range(2):
   status,raw=f.read(f'/setting/A7CU{i}.CFG',maximum=4096)
   if status==f.missing:continue
   require(status==(0,0) and len(raw)==2848 and raw[:8]==b'A7CUSTOM','Invalid independent catalog')
   (out/f'custom-{i}.bin').write_bytes(raw)
   require(zlib.crc32(raw[:-4])==int.from_bytes(raw[-4:],'little'),'Catalog CRC failed')
   schema,generation,next_slot,active,count=struct.unpack_from('<5I',raw,8)
   require(schema==1 and 0<=count<=16 and next_slot==7+count,'Catalog header invalid')
   looks=[]
   for j in range(count):
    r=raw[28+j*176:28+(j+1)*176]
    looks.append(dict(slot=int.from_bytes(r[:4],'little'),base=r[4],id=r[8:57].split(b'\0')[0].decode(),name=r[57:121].split(b'\0')[0].decode(),values=list(struct.unpack_from('16b',r,121))))
   catalogs.append(dict(generation=generation,active=active,looks=looks))
  require(catalogs,'No imported independent catalog')
  catalog=max(catalogs,key=lambda p:p['generation'])
  require(catalog['active']==7 and len(catalog['looks'])==1,'Expected selected first independent look')
  look=catalog['looks'][0]
  require(look['slot']==7 and look['id']=='portrait-grain-1' and look['name']=='人像颗粒 1' and look['base']==6,'Unexpected imported look')
  expected=before['banks'][5][:];expected[8]=1
  require(look['values']==expected,'Imported controls differ from tested recipe')
  raw=f.run((out/'read.so').read_bytes(),'sdaccept.bin');(out/'runtime.bin').write_bytes(raw)
  require(len(raw)==140,'Wrong runtime length');v=struct.unpack_from('<19i',raw)
  require(v[0]==0x5344494d and v[1]==1,'Resident not found')
  names='prepared installed fault parents dirty generation runtime_ready last_error mode'.split()
  rt=dict(zip(names,v[2:11]));rt['parameters']=list(v[11:19]);uptime=raw[76:].split(b'\0')[0].decode().strip()
  changes=[{'look':b+1,'field':i,'before':before['banks'][b][i],'after':saved['banks'][b][i]} for b in range(6) for i in range(16) if before['banks'][b][i]!=saved['banks'][b][i]]
  result=dict(installed_sha256=hashes,before_generation=before['generation'],saved=saved,runtime=rt,uptime=uptime,changes=changes,persistent_writes=False,catalog=catalog,user_report='Pending correlation with user cold-boot/menu/photo report')
  (out/'readback.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2),flush=True)
  require(saved==before,'Built-in saved settings changed')
  require(saved['mode']==before['mode'] and not changes and saved['banks'][5][8]==1,'Unexpected parameter change')
  require(rt['prepared']==1 and rt['installed']==1 and not rt['fault'] and not rt['dirty'] and not rt['last_error'] and rt['mode']==look['base'],'Runtime differs from saved state')
  require(rt['parameters']==look['values'][:8],'Runtime parameter mismatch')
  result['verified']=True;(out/'acceptance.json').write_text(json.dumps(result,indent=2)+'\n');print('CUSTOM_LOOK_ACCEPTANCE',out,flush=True)
 service.perform=collect;handoff.SWITCH+=' --host-identity-check';handoff.run('settings-snapshot')
if __name__=='__main__':main()
