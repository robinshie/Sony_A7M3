#!/usr/bin/env python3
"""Install the independent look catalog candidate, preserving all four configuration slots."""
import argparse,json,subprocess,sys,tempfile,time
from pathlib import Path
from local import ROOT,LAB,require,file_sha
from camera import native_module_replace as updater
from camera.native_install import save_json
from deploy_auto_size import operate
BASE=LAB/'native-fl-releases/update-v001-sd-import-zgow4zto/write-1794816564912805000'
ORDER=(2001,2002,20)
def package():
 out=Path(tempfile.mkdtemp(prefix='update-v001-custom-looks-',dir=LAB/'native-fl-releases'))
 for revision,name in ((2001,'string_simplifiedchinese.uxc'),(2002,'string_english.uxc'),(20,None)):
  old=BASE/str({2001:1901,2002:1902,20:19}[revision])/'new-module-readback.so'
  folder=LAB/('native-fl-custom-strings' if name else 'native-module-custom-candidate')
  new=folder/(name or 'liba7-fl-module.so')
  subprocess.run([sys.executable,'research/native_module_replace_bind.py','--revision',str(revision),'--old',str(old),'--module',str(new),'--proof',str(folder/'proof.json'),'--view',str(BASE/'19/view-after.so'),'--out',str(out/str(revision))],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
  subprocess.run([sys.executable,'research/native_module_replace_host_test.py','--binding',str(out/str(revision))],cwd=ROOT,check=True)
 save_json(out/'package.json',dict(kind='custom-looks-candidate',order=list(ORDER),bindings={str(r):file_sha(out/str(r)/'manifest.json') for r in ORDER},source_sha256={s:file_sha(ROOT/s) for s in ['deploy_custom_looks.py','deploy_auto_size.py','research/six_look_settings.py']}))
 return out
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path);p.add_argument('--write-device',action='store_true');a=p.parse_args()
 out=a.package.resolve() if a.package else package();m=json.loads((out/'package.json').read_text());updater.pin_sources(m)
 require(m['kind']=='custom-looks-candidate' and m['order']==list(ORDER),'Wrong sequence')
 items=[]
 for r in ORDER:
  require(file_sha(out/str(r)/'manifest.json')==m['bindings'][str(r)],'Binding changed')
  items.append(updater.Bundle(out/str(r)))
 print('CUSTOM_LOOKS_PACKAGE',out,flush=True)
 if not a.write_device:return
 from camera import service,handoff
 evidence=out/('write-'+str(time.time_ns()))
 def perform(camera,action):
  require(action=='settings-snapshot','Unexpected action')
  f=service.Factory(camera)
  for i in range(2):require(f.read(f'/setting/A7CU{i}.CFG')[0]==f.missing,'Unexpected existing custom catalog; inspect before install')
  device=camera.dev.driver.backend.dev;old=device.default_timeout;device.default_timeout=45000
  try:print(json.dumps(operate(camera,items,evidence),indent=2),flush=True)
  finally:device.default_timeout=old
 service.perform=perform;handoff.SWITCH+=' --host-identity-check';handoff.run('settings-snapshot')
if __name__=='__main__':main()
