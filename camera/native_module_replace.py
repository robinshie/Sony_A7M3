"""Preflight or explicitly replace a pinned native FL module revision.

No loader/locales/WBI/LUT writes, journal resumption, or automatic device retry.
The module already mapped in the running process stays unchanged until reboot.
"""
import argparse,hashlib,json,os,struct,time
from pathlib import Path
from local import ROOT,LAB,BUILD_ID,file_sha,require,sha
from camera.native_install import pin_sources,save,save_json
from camera.native_wbi import capture
OLD='2478cec27f88e838f03915da36ac09c66efff9d6a3bd53d59fc487f6cd345aac'
REVISIONS={1:dict(old_sha=OLD,old_size=42208,temporary='.a7fl-r1.new',backup='.a7fl-2478cec2.orig',journal='A7FLUP1.LOG'),
           2:dict(old_sha='e64867d24764725dfaf621e2ab9611f6d389f15b21cf6dad7daacd1c618492e1',old_size=42812,temporary='.a7fl-r2.new',backup='.a7fl-e64867d2.orig',journal='A7FLUP2.LOG')}
VIEW_SHA='a1c4d8e88f54f71786ff53bc15a59c32a2969a6ffc934ef77728123d8af172a7'
MODULE='/usr/lib/a7fl.so';VIEW='/usr/lib/viewUnified2.so'
FORWARD=((1,0,0,0),(2,0,0,0),(10,0,0,0),(20,1,0,0),(30,1,0,0),(31,1,1,0),(40,1,1,0),(41,0,1,1),(60,0,1,1),(100,0,1,1))
def syncdir(p):
 fd=os.open(p,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
class Bundle:
 def __init__(self,directory):
  self.directory=d=Path(directory).resolve();m=self.manifest=json.loads((d/'manifest.json').read_text());pin_sources(m)
  revision=m['version'];require(revision in REVISIONS and m['kind']==f'native-module-replace-r{revision}','Foreign module replacement binding.');r=REVISIONS[revision]
  self.temporary='/usr/lib/'+r['temporary'];self.backup='/usr/lib/'+r['backup'];self.journal='/setting/'+r['journal']
  require(m['old']==dict(sha256=r['old_sha'],size=r['old_size']) and m['view']==dict(sha256=VIEW_SHA,size=10854816),'Incorrect deployed baseline.')
  proof=d/'module-proof.json';require(file_sha(proof)==m['module_proof_sha256'],'Module proof changed.');p=json.loads(proof.read_text());pin_sources(p)
  require(p.get('ready_for_staging') is True and p.get('placeholder') is False and p['module_sha256']==m['new']['sha256'],'Unattested module.')
  for n,h in p['dependency_proof_sha256'].items():
   path=(LAB/n).resolve();require(path.is_relative_to(LAB) and file_sha(path)==h,'Dependency changed: '+n);pin_sources(json.loads(path.read_text()))
  core_dir='native-module-replace-test'+('' if revision==1 else f'-r{revision}')
  for n,key in [(core_dir+'/proof.json','core_proof_sha256'),('native-menu-action-tree/proof.json','action_proof_sha256')]:
   path=LAB/n;require(file_sha(path)==m[key],'Required proof changed: '+n);pin_sources(json.loads(path.read_text()))
  for name,key in [('entry.c','entry_sha256'),('data.S','data_sha256')]:require(file_sha(d/name)==m[key],'Bound source changed: '+name)
  for name,key in [('old-module.so','old'),('new-module.so','new')]:require(file_sha(d/name)==m[key]['sha256'] and (d/name).stat().st_size==m[key]['size'],'Bound module changed: '+name)
  b=b'A7M3-single-module-r1\0'+struct.pack('<4I',revision,m['old']['size'],m['new']['size'],m['view']['size'])+b''.join(bytes.fromhex(m[k]['sha256']) for k in ('old','new','view'))+bytes.fromhex(m['module_proof_sha256'])
  require(sha(b)==m['bundle_sha256'],'Binding digest differs.');self.payloads={}
  for mode in ('preflight','replace'):
   raw=(d/(mode+'.so')).read_bytes();r=m['payloads'][mode]
   require(len(raw)==r['size'] and 52<len(raw)<=1048576 and sha(raw)==r['sha256'] and raw[:7]==b'\x7fELF\1\1\1' and raw[16:20]==b'\x03\0(\0','Invalid ARM payload: '+mode);self.payloads[mode]=raw
def decode(raw,binding):
 require(len(raw)==72,'Unexpected module report length.')
 values=struct.unpack('<6I4i32s',raw);names='magic version phase created backed_up published status first_error rollback_ok readonly_confirmed'.split();r=dict(zip(names,values[:10]));r['binding']=values[10].hex()
 require(r['magic']==0x41374652 and r['version']==1 and r['binding']==binding,'Foreign module report.');return r
def journal(raw,binding):
 records=[];error=None
 for off in range(0,len(raw)//88*88,88):
  v=raw[off:off+88];magic,seq,phase,created,backed,published=struct.unpack_from('<6I',v)
  if magic!=0x41374655 or seq!=len(records)+1 or v[24:56].hex()!=binding or sha(v[:56])!=v[56:].hex():error='Foreign/torn journal record';break
  records.append(dict(sequence=seq,phase=phase,created=created,backed_up=backed,published=published))
 if len(raw)%88:error='Torn journal suffix'
 complete=not error and len(records)==len(FORWARD) and all((r['phase'],r['created'],r['backed_up'],r['published'])==expected for r,expected in zip(records,FORWARD))
 return dict(records=records,integrity_error=error,complete=complete,sha256=sha(raw))
def success(r,writing=False):return r['status']==0 and not r['first_error'] and r['phase']==(100 if writing else 1) and (r['created'],r['backed_up'],r['published'])==((0,1,1) if writing else (0,0,0)) and r['readonly_confirmed']==1
def native(factory,b,mode,e):
 raw=factory.run(b.payloads[mode],'a7modup.bin');save(e/(mode+'-report.bin'),raw);r=decode(raw,b.manifest['bundle_sha256']);save_json(e/(mode+'-report.json'),r);syncdir(e);return r
def require_file(factory,path,record,target):
 raw=factory.contents(path,maximum=record['size']+16);save(target,raw)
 require(len(raw)==record['size'] and sha(raw)==record['sha256'],'File readback mismatch: '+path);return raw
def zero_wbi(camera,e):
 r=capture(camera,e)
 require(r['status']==1 and r['phase']==2 and r['header_kind']==0 and not r['error'] and r['capacity_lo']==62914560 and r['capacity_hi']==0 and (e/'header.bin').read_bytes()==bytes(512),'WBI is not already invalidated; no automatic WBI write is performed.')
 return r
def operate(camera,b,operation,evidence,write_device=False):
 from camera.service import Factory
 require(operation in ('preflight','replace') and (operation=='preflight' or write_device),'Replacement requires explicit --write-device.')
 e=Path(evidence);e.mkdir(mode=0o700,parents=True,exist_ok=False);syncdir(e.parent);f=Factory(camera);m=b.manifest
 require(f.contents('/version.txt')==BUILD_ID and bytes(camera.readBackup(0x3e0005))==b'ILCE-7M3'+bytes(8),'Camera model/build mismatch.')
 save_json(e/'binding.json',m);zero_wbi(camera,e/'wbi-before')
 for path in (b.temporary,b.backup,b.journal):require(f.read(path)[0]==f.missing,'Existing transaction/backup is never resumed or overwritten: '+path)
 require_file(f,MODULE,m['old'],e/'old-module.so');require_file(f,VIEW,m['view'],e/'view-before.so')
 before=native(f,b,'preflight',e);require(success(before),'Native module preflight rejected; no replacement payload sent.')
 if operation=='preflight':
  result=dict(operation=operation,verified=True,device_firmware_written=False,native_report=before,evidence=str(e));save_json(e/'verified.json',result);syncdir(e);return result
 save_json(e/'write-intent.json',dict(operation='replace-a7fl-module-r'+str(m['version']),bundle=m['bundle_sha256'],old=m['old'],new=m['new'],no_auto_retry=True));syncdir(e);syncdir(e.parent)
 written=native(f,b,'replace',e)
 # On reported failure still preserve a readable transaction journal, but do
 # not declare success, resume, or send a second writer.
 status,raw=f.read(b.journal,maximum=65536)
 if status==(0,0):save(e/'device-journal.bin',raw);j=journal(raw,m['bundle_sha256']);save_json(e/'device-journal.json',j)
 else:j=None
 syncdir(e);require(success(written,True),'Replacement did not fully verify; inspect retained report/journal, no automatic retry.')
 require(j is not None and j['complete'],'Incomplete replacement transaction journal.')
 require_file(f,MODULE,m['new'],e/'new-module-readback.so');require_file(f,b.backup,m['old'],e/'old-backup-readback.so');require_file(f,VIEW,m['view'],e/'view-after.so')
 require(f.read(b.temporary)[0]==f.missing,'Temporary candidate remains after replacement.')
 after=zero_wbi(camera,e/'wbi-after')
 require((e/'wbi-before/neighbor.bin').read_bytes()==(e/'wbi-after/neighbor.bin').read_bytes(),'WBI neighbor unexpectedly differs.')
 result=dict(operation=operation,verified=True,old_sha256=m['old']['sha256'],new_sha256=m['new']['sha256'],view_unchanged=True,readonly_confirmed=True,wbi_unchanged=True,cold_boot_required=True,native_report=written,evidence=str(e));save_json(e/'verified.json',result);syncdir(e);return result
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=('preflight','replace'),nargs='?',default='preflight');p.add_argument('--binding',type=Path,default=LAB/'native-module-replace-bound-r1');p.add_argument('--offline',action='store_true');p.add_argument('--write-device',action='store_true');p.add_argument('--direct',action='store_true');a=p.parse_args();b=Bundle(a.binding)
 require(a.operation=='preflight' or a.write_device,'replace requires --write-device.');require(not(a.operation=='preflight' and a.write_device),'--write-device is not meaningful for preflight.')
 if a.offline:print(json.dumps(dict(binding_verified=True,camera_contacted=False,bundle=b.manifest['bundle_sha256'])));return
 from camera import service,handoff
 previous=service.perform;result=None;e=b.directory/(a.operation+'-'+str(time.time_ns()))
 def perform(camera,action):
  nonlocal result
  require(action=='settings-snapshot','Unexpected transport action.')
  device=camera.dev.driver.backend.dev;old_timeout=device.default_timeout;device.default_timeout=45000
  try:result=operate(camera,b,a.operation,e,a.write_device)
  finally:device.default_timeout=old_timeout
 service.perform=perform
 try:
  if a.direct:
   import fcntl
   with (LAB/'.usb-transport.lock').open('a') as lock:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);service.connect('settings-snapshot')
  else:handoff.run('settings-snapshot')
 finally:service.perform=previous
 require(result is not None,'No replacement result.');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
