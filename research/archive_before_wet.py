"""Archive four pinned superseded locale backups; preserve current/recent files."""
import argparse,json,os,struct,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from camera import service,handoff
from camera.native_module_replace import REVISIONS,VIEW_SHA
from camera.native_install import save,save_json
from local import LAB,BUILD_ID,require,file_sha,sha
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True);p.add_argument('--write-device',action='store_true');args=p.parse_args()
out=args.archive.resolve();require(out.is_relative_to(LAB/'wet-old-locale-archive'),'Foreign archive')
m=json.loads((out/'manifest.json').read_text());require(not(out/'result.bin').exists() and not(out/'write-intent.json').exists(),'Prior attempt; inspect without replay')
expected=[]
for rev in (1701,1702,1901,1902):
 r=REVISIONS[rev];expected.append(dict(path='/usr/share/app/'+r['backup'],file=r['backup'],bytes=r['old_size'],sha256=r['old_sha'],current=r['locale']))
require(m['files']==expected and m['current_module']==REVISIONS[27]['old_sha'],'Foreign backup set')
for r in expected:require((out/r['file']).stat().st_size==r['bytes'] and file_sha(out/r['file'])==r['sha256'],'Archive incomplete')
a=lambda x:','.join(str(v) for v in bytes.fromhex(x))
s='''#define NMR_REVISION 27
#include "research/native_module_replace.c"
#include "research/native_module_replace_linux.c"
static const NMRBundle bound={.old_size=155840,.new_size=52,.view_size=10854816,.old_sha={%s},.view_sha={%s}};
static const struct Item{const char*path;unsigned size;unsigned char hash[32];} items[]={%s};
static const struct Item active[]={%s};
static NMRReport result;static Work w;static int model(void*p){(void)p;return 1;}
__attribute__((constructor))static void archive(void){
 w.b=&bound;w.call=nmr_linux_call;w.r=&result;w.lib=w.setting=w.log=-1;result.status=-1;
 if(!preflight(&w,model,0))goto done;
 for(unsigned i=0;i<2;i++)if(!file(&w,w.lib,active[i].path,active[i].size,active[i].hash,1,0,0))goto done;
 for(unsigned i=0;i<4;i++)if(!file(&w,w.lib,items[i].path,items[i].size,items[i].hash,1,0,0))goto done;
 int dir=(int)sc(&w,OPEN,(long)"/usr/share/app",DIRECTORY|NOFOLLOW,0,0,0,0);if(dir<0)goto done;
 if(!remount(&w,0)){closefd(&w,dir);goto done;}w.rw=1;
 if(!mount_is(&w,0)){closefd(&w,dir);goto done;}
 for(unsigned i=0;i<4;i++){
  if(!file(&w,w.lib,items[i].path,items[i].size,items[i].hash,1,0,0))break;
  if(sc(&w,UNLINKAT,w.lib,(long)items[i].path,0,0,0,0))break;
  result.published++;
  if(sc(&w,SYNC,dir,0,0,0,0,0)||!absent(&w,w.lib,items[i].path))break;
 }
 if(!closefd(&w,dir))goto done;
 if(result.published==4&&!result.first_error)result.status=0;
 done:if(w.rw){result.readonly_confirmed=remount(&w,1)&&mount_is(&w,1);if(!result.readonly_confirmed)result.status=-2;}
 if(w.lib>=0)closefd(&w,w.lib);if(w.setting>=0)closefd(&w,w.setting);
 long fd=sc(&w,OPEN,(long)"/tmp/jiritsu/archivewet.bin",1|64|128,0600,0,0,0);
 if(fd>=0){writeall(&w,fd,&result,sizeof result);closefd(&w,fd);}
}
'''%(a(REVISIONS[27]['old_sha']),a(VIEW_SHA),','.join('{"%s",%d,{%s}}'%(r['path'],r['bytes'],a(r['sha256'])) for r in expected),','.join('{"/usr/share/app/%s",%d,{%s}}'%(REVISIONS[v]['locale'],REVISIONS[v]['old_size'],a(REVISIONS[v]['old_sha'])) for v in (2701,2702)))
(out/'archive.c').write_text(s)
subprocess.run(['arm-none-eabi-gcc','-I',str(ROOT),'-mcpu=cortex-a9','-marm','-mfloat-abi=soft','-fPIC','-Os','-nostdlib','-shared','-Wl,-z,noexecstack',str(out/'archive.c'),'-o',str(out/'archive.so')],check=True)
print('PINNED_ARCHIVE_READY',out,flush=True)
if not args.write_device:sys.exit(0)
def run(camera,action):
 f=service.Factory(camera);require(f.contents('/version.txt')==BUILD_ID and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Wrong camera')
 require(sha(f.contents('/usr/lib/a7fl.so',maximum=200000))==REVISIONS[27]['old_sha'],'Current module changed')
 for r in expected:require(f.contents(r['path'],maximum=r['bytes']+16)==(out/r['file']).read_bytes(),'Remote backup changed')
 save_json(out/'write-intent.json',dict(operation='remove-exact-archived-old-locales',files=expected,payload_sha256=file_sha(out/'archive.so')))
 fd=os.open(out,os.O_RDONLY);os.fsync(fd);os.close(fd)
 reply=f.run((out/'archive.so').read_bytes(),'archivewet.bin');save(out/'result.bin',reply)
 v=struct.unpack('<6I4i32s',reply);print('ARCHIVE_RESULT',v[:10],flush=True)
 require(v[5]==4 and v[6]==0 and v[7]==0 and v[9]==1,'Archive removal failed; inspect without retry')
 for r in expected:require(f.read(r['path'])[0]==f.missing,'Archived backup still exists')
 require(sha(f.contents('/usr/lib/a7fl.so',maximum=200000))==REVISIONS[27]['old_sha'],'Current module changed')
 save_json(out/'verified.json',dict(archived=True,removed=expected,current_unchanged=True,readonly=True));print('ARCHIVE_VERIFIED',out,flush=True)
service.perform=run;handoff.SWITCH+=' --host-identity-check';handoff.run('settings-snapshot')
