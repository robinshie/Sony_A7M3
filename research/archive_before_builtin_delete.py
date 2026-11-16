"""Archive exactly the superseded earlier candidate; preserve current and latest rollback."""
import sys,json,hashlib,subprocess,time,struct,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from camera import service,handoff
from camera.native_install import save,save_json
from local import LAB,BUILD_ID,require
B=LAB/'native-fl-releases/update-v001-builtin-delete-det1551f/25'
m=json.loads((B/'manifest.json').read_text())
out=LAB/'custom-old-backup-archive'/str(time.time_ns());out.mkdir(parents=True)
name='.a7fl-2e13c731.orig';digest='2e13c731322960f5e46bd46f7112396ea5fa1ae78cff7e82d94819e5ea17c5c2'
a=lambda s:','.join(str(x) for x in bytes.fromhex(s))
s='''#define NMR_REVISION 25
#include "research/native_module_replace.c"
#include "research/native_module_replace_linux.c"
static const NMRBundle bound={.old_size=%d,.new_size=52,.view_size=%d,.old_sha={%s},.view_sha={%s}};
static const unsigned char archived[32]={%s};
static NMRReport result;static Work w;static int model(void*p){(void)p;return 1;}
__attribute__((constructor))static void archive(void){
 w.b=&bound;w.call=nmr_linux_call;w.r=&result;w.lib=w.setting=w.log=-1;result.status=-1;
 if(!preflight(&w,model,0))goto done;
 if(!file(&w,w.lib,".a7fl-2e13c731.orig",153104,archived,1,0,0))goto done;
 if(!remount(&w,0))goto done;w.rw=1;
 if(!mount_is(&w,0)||!file(&w,w.lib,".a7fl-2e13c731.orig",153104,archived,1,0,0))goto done;
 if(sc(&w,UNLINKAT,w.lib,(long)".a7fl-2e13c731.orig",0,0,0,0))goto done;
 result.published=1;
 if(sc(&w,SYNC,w.lib,0,0,0,0,0)||!absent(&w,w.lib,".a7fl-2e13c731.orig"))goto done;
 result.status=0;
 done:if(w.rw){result.readonly_confirmed=remount(&w,1)&&mount_is(&w,1);if(!result.readonly_confirmed)result.status=-2;}
 if(w.lib>=0)closefd(&w,w.lib);if(w.setting>=0)closefd(&w,w.setting);
 long fd=sc(&w,OPEN,(long)"/tmp/jiritsu/archive.bin",1|64|128,0600,0,0,0);
 if(fd>=0){writeall(&w,fd,&result,sizeof result);closefd(&w,fd);}
}
'''%(m['old']['size'],m['view']['size'],a(m['old']['sha256']),a(m['view']['sha256']),a(digest))
(out/'archive.c').write_text(s)
subprocess.run(['arm-none-eabi-gcc','-I',str(ROOT),'-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os','-nostdlib','-shared','-Wl,-z,noexecstack',str(out/'archive.c'),'-o',str(out/'archive.so')],check=True)
def collect(camera,action):
 f=service.Factory(camera)
 require(f.contents('/version.txt')==BUILD_ID and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Wrong camera')
 require(hashlib.sha256(f.contents('/usr/lib/a7fl.so',maximum=200000)).hexdigest()==m['old']['sha256'],'Current module mismatch')
 raw=f.contents('/usr/lib/'+name,maximum=160000)
 require(len(raw)==153104 and hashlib.sha256(raw).hexdigest()==digest,'Obsolete backup mismatch')
 save(out/name,raw)
 require((out/name).read_bytes()==raw,'Local archive mismatch')
 d=os.open(out,os.O_RDONLY);os.fsync(d);os.close(d)
 save_json(out/'archive.json',dict(source='/usr/lib/'+name,sha256=digest,size=len(raw),local_verified=True))
 reply=f.run((out/'archive.so').read_bytes(),'archive.bin');save(out/'result.bin',reply)
 v=struct.unpack('<6I4i32s',reply);print('ARCHIVE_RESULT',v[:10],flush=True)
 require(v[5]==1 and v[6]==0 and v[9]==1,'Archive removal or readonly restore failed; do not retry')
 require(f.read('/usr/lib/'+name)[0]==f.missing,'Old backup still present')
 require(hashlib.sha256(f.contents('/usr/lib/a7fl.so',maximum=200000)).hexdigest()==m['old']['sha256'],'Current module changed')
 save_json(out/'verified.json',dict(archived=True,current_unchanged=True,readonly=True));print('ARCHIVE_VERIFIED',out,flush=True)
service.perform=collect;handoff.SWITCH+=' --host-identity-check';handoff.run('settings-snapshot')
