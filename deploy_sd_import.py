#!/usr/bin/env python3
"""Install the SD recipe menu candidate, preserving all four configuration slots."""
import argparse,json,subprocess,sys,tempfile,time
from pathlib import Path
from local import ROOT,LAB,require,file_sha
from camera import native_module_replace as updater
from camera.native_install import save_json
from deploy_auto_size import operate
BASE=LAB/'native-fl-releases/update-v001-auto-size-xd7cs4kh/write-1794742237131275000/18'
ORDER=(1901,1902,19)
def package():
 out=Path(tempfile.mkdtemp(prefix='update-v001-sd-import-',dir=LAB/'native-fl-releases'))
 for revision,name in ((1901,'string_simplifiedchinese.uxc'),(1902,'string_english.uxc'),(19,None)):
  old=BASE/('required-'+name if name else 'new-module-readback.so')
  folder=LAB/('native-fl-sd-strings' if name else 'native-module-sd-candidate')
  new=folder/(name or 'liba7-fl-module.so')
  subprocess.run([sys.executable,'research/native_module_replace_bind.py','--revision',str(revision),'--old',str(old),'--module',str(new),'--proof',str(folder/'proof.json'),'--view',str(BASE/'view-after.so'),'--out',str(out/str(revision))],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
  subprocess.run([sys.executable,'research/native_module_replace_host_test.py','--binding',str(out/str(revision))],cwd=ROOT,check=True)
 save_json(out/'package.json',dict(kind='sd-import-candidate',order=list(ORDER),bindings={str(r):file_sha(out/str(r)/'manifest.json') for r in ORDER},source_sha256={s:file_sha(ROOT/s) for s in ['deploy_sd_import.py','deploy_auto_size.py','research/six_look_settings.py']}))
 return out
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path);p.add_argument('--write-device',action='store_true');a=p.parse_args()
 out=a.package.resolve() if a.package else package();m=json.loads((out/'package.json').read_text());updater.pin_sources(m)
 require(m['kind']=='sd-import-candidate' and m['order']==list(ORDER),'Wrong sequence')
 items=[]
 for r in ORDER:
  require(file_sha(out/str(r)/'manifest.json')==m['bindings'][str(r)],'Binding changed')
  items.append(updater.Bundle(out/str(r)))
 print('SD_IMPORT_PACKAGE',out,flush=True)
 if not a.write_device:return
 from camera import service,handoff
 evidence=out/('write-'+str(time.time_ns()))
 def perform(camera,action):
  require(action=='settings-snapshot','Unexpected action')
  device=camera.dev.driver.backend.dev;old=device.default_timeout;device.default_timeout=45000
  try:print(json.dumps(operate(camera,items,evidence),indent=2),flush=True)
  finally:device.default_timeout=old
 service.perform=perform;handoff.SWITCH+=' --host-identity-check';handoff.run('settings-snapshot')
if __name__=='__main__':main()
