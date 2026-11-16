#!/usr/bin/env python3
"""Install the custom-look popup names and confirmed deletion, preserving all four configuration slots."""
import argparse,json,subprocess,sys,tempfile,time
from pathlib import Path
from local import ROOT,LAB,require,file_sha
from camera import native_module_replace as updater
from camera.native_install import save_json,save
from deploy_auto_size import operate
BASE=LAB/'native-fl-releases/update-v001-custom-delete-n6h5xh_6/write-1794821118937025000/22'
ORDER=(23,)
def package():
 out=Path(tempfile.mkdtemp(prefix='update-v001-custom-text-',dir=LAB/'native-fl-releases'))
 for revision,name in ((23,None),):
  old=BASE/'new-module-readback.so'
  folder=LAB/('native-fl-custom-strings' if name else 'native-module-custom-candidate')
  new=folder/(name or 'liba7-fl-module.so')
  subprocess.run([sys.executable,'research/native_module_replace_bind.py','--revision',str(revision),'--old',str(old),'--module',str(new),'--proof',str(folder/'proof.json'),'--view',str(BASE/'view-after.so'),'--out',str(out/str(revision))],cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
  subprocess.run([sys.executable,'research/native_module_replace_host_test.py','--binding',str(out/str(revision))],cwd=ROOT,check=True)
 save_json(out/'package.json',dict(kind='custom-text-candidate',order=list(ORDER),bindings={str(r):file_sha(out/str(r)/'manifest.json') for r in ORDER},source_sha256={s:file_sha(ROOT/s) for s in ['deploy_custom_text.py','deploy_auto_size.py','research/six_look_settings.py']}))
 return out
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--package',type=Path);p.add_argument('--write-device',action='store_true');a=p.parse_args()
 out=a.package.resolve() if a.package else package();m=json.loads((out/'package.json').read_text());updater.pin_sources(m)
 require(m['kind']=='custom-text-candidate' and m['order']==list(ORDER),'Wrong sequence')
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
  catalogs=[f.read(f'/setting/A7CU{i}.CFG',maximum=4096) for i in range(2)]
  require(all(status in (f.missing,(0,0)) for status,raw in catalogs),'Catalog snapshot failed')
  for i,(status,raw) in enumerate(catalogs):
   if status==(0,0):require(len(raw)==2848,'Unexpected catalog length')
  snapshot=out/('catalog-backup-'+str(time.time_ns()));snapshot.mkdir(mode=0o700)
  for i,(status,raw) in enumerate(catalogs):
   if status==(0,0):save(snapshot/f'A7CU{i}.CFG',raw)
  save_json(snapshot/'status.json',dict(slots=[list(status) for status,raw in catalogs]))
  updater.syncdir(snapshot);updater.syncdir(out)
  device=camera.dev.driver.backend.dev;old=device.default_timeout;device.default_timeout=45000
  try:
   result=operate(camera,items,evidence)
   after=[f.read(f'/setting/A7CU{i}.CFG',maximum=4096) for i in range(2)]
   require(catalogs==after,'Independent catalogs changed during install')
   save_json(evidence/'catalog-preserved.json',dict(verified=True,unchanged=True,sizes=[len(raw) for status,raw in catalogs]))
   print(json.dumps(result,indent=2),flush=True)
  finally:device.default_timeout=old
 service.perform=perform;handoff.SWITCH+=' --host-identity-check';handoff.run('settings-snapshot')
if __name__=='__main__':main()
