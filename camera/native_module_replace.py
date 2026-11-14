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
           2:dict(old_sha='e64867d24764725dfaf621e2ab9611f6d389f15b21cf6dad7daacd1c618492e1',old_size=42812,temporary='.a7fl-r2.new',backup='.a7fl-e64867d2.orig',journal='A7FLUP2.LOG'),
           3:dict(old_sha='f3e2d657a83569f19ddafcd843a40601f1d953da0a20a8f8617c5e299e73a063',old_size=43160,temporary='.a7fl-r3.new',backup='.a7fl-f3e2d657.orig',journal='A7FLUP3.LOG'),
           4:dict(old_sha='bd01f7b1a0b6594c118613ca2b6c87debdcb17032bccd6ef43be14ffa8aaf274',old_size=43356,temporary='.a7fl-r4.new',backup='.a7fl-bd01f7b1.orig',journal='A7FLUP4.LOG'),
           5:dict(old_sha='1216dda332c42c6378fd993ccb89781d6229150c00798191835232de3923b675',old_size=48912,temporary='.a7fl-r5.new',backup='.a7fl-1216dda3.orig',journal='A7FLUP5.LOG'),
           6:dict(old_sha='62c85626243e7009d78999ab16568163e9186934ccd820b70c7b3ea08ff7b5d0',old_size=55420,temporary='.a7fl-r6.new',backup='.a7fl-62c85626.orig',journal='A7FLUP6.LOG'),
           7:dict(old_sha='25d5f6f1f428cfbd92cae46be496b407eb746fbe06a4120215f5f2b87d508f31',old_size=60744,temporary='.a7fl-r7.new',backup='.a7fl-25d5f6f1.orig',journal='A7FLUP7.LOG'),
           8:dict(old_sha='74d1df6c73ebd7d056ce741a28e3f459fdf2e7c5ac29063527e18b7111a64703',old_size=63524,temporary='.a7fl-r8.new',backup='.a7fl-74d1df6c.orig',journal='A7FLUP8.LOG'),
           9:dict(old_sha='a332915e7cd4c5753df843480779f21b1d05941504f814a6cd438892ec86b865',old_size=65392,temporary='.a7fl-r9.new',backup='.a7fl-a332915e.orig',journal='A7FLUP9.LOG'),
           10:dict(old_sha='c2a8c2b9fc03b90c7695a775d6d14cd1813ebe38ca2f6924fef36dc9299fa5cc',old_size=67740,temporary='.a7fl-r10.new',backup='.a7fl-c2a8c2b9.orig',journal='A7FLUP10.LOG'),
           11:dict(old_sha='ff53734912f9a80a720de7105d4ef97a8166f5a1b9b70ab8009cb16b122396eb',old_size=74176,temporary='.a7fl-r11.new',backup='.a7fl-ff537349.orig',journal='A7FLUP11.LOG'),
           1101:dict(old_sha='980b77f7a7d08963976b724b958525d0b99e0f5e70a01552f3116dd3b1b014c1',old_size=350176,temporary='.a7fl2-zh.new',backup='.a7fl2-zh.orig',journal='A7FL2ZH.LOG',locale='string_simplifiedchinese.uxc'),
           1102:dict(old_sha='8b4772b88ad655c0b866924ce0876d79d8400d3fc558c9350c28c58a05adf196',old_size=392884,temporary='.a7fl2-en.new',backup='.a7fl2-en.orig',journal='A7FL2EN.LOG',locale='string_english.uxc'),
           12:dict(old_sha='70e12df533ecd928f3c9f48231622e112ac0acaae698a737ae93e314895372b2',old_size=75148,temporary='.a7fl-r12.new',backup='.a7fl-70e12df5.orig',journal='A7FLUP12.LOG'),
           1201:dict(old_sha='c992cd53f905df46f98d13800d4f899c93d9e4e50cf2e35135d8e6f557ec006b',old_size=350188,temporary='.a7fl3-zh.new',backup='.a7fl3-zh.orig',journal='A7FL3ZH.LOG',locale='string_simplifiedchinese.uxc',resource_set='fl3'),
           1202:dict(old_sha='d3c4bb0a71e4355d3bf394a14543abc850f76eccb0ec72e0c64f31f97f41f9ef',old_size=392896,temporary='.a7fl3-en.new',backup='.a7fl3-en.orig',journal='A7FL3EN.LOG',locale='string_english.uxc',resource_set='fl3')}
REVISIONS.update({13: {'old_sha': 'b83d38c9867d50b3345b72813879b73b6659e375c36625a6f68e90d64bb493f7', 'old_size': 79840, 'temporary': '.a7fl-r13.new', 'backup': '.a7fl-b83d38c9.orig', 'journal': 'A7FLUP13.LOG'}, 1301: {'old_sha': '97de64a708e20121c717d0e362b93215783461ec8d7e5213194f94b487ede245', 'old_size': 350220, 'temporary': '.a7curve-zh.new', 'backup': '.a7curve-zh.orig', 'journal': 'A7CURVEZH.LOG', 'locale': 'string_simplifiedchinese.uxc', 'resource_set': 'fl3-curves'}, 1302: {'old_sha': '83b77a48936f83163d3f9ec20d8dad0c7fbc1681e53096038e599681213c45ed', 'old_size': 392924, 'temporary': '.a7curve-en.new', 'backup': '.a7curve-en.orig', 'journal': 'A7CURVEEN.LOG', 'locale': 'string_english.uxc', 'resource_set': 'fl3-curves'}})
REVISIONS[14]=dict(old_sha='79772dfce51d90663de65fda7d54ed48bfcbe8c9fd46df7797ca9dcf5be53bbd',old_size=89692,temporary='.a7fl-r14.new',backup='.a7fl-79772dfc.orig',journal='A7FLUP14.LOG')
VIEW_SHA='a1c4d8e88f54f71786ff53bc15a59c32a2969a6ffc934ef77728123d8af172a7'
MODULE='/usr/lib/a7fl.so';VIEW='/usr/lib/viewUnified2.so'
FORWARD=((1,0,0,0),(2,0,0,0),(10,0,0,0),(20,1,0,0),(30,1,0,0),(31,1,1,0),(40,1,1,0),(41,0,1,1),(60,0,1,1),(100,0,1,1))
def require_capture_release(revision,proof):
 if revision in (13,14):
  if revision==14:require(proof.get("all_look_curves") is True,"All three look curves require integration evidence.")
  require(proof.get('preference_schema')==4 and proof.get('leica_look') is True and
          proof.get('independent_look_banks') is True and proof.get('save_confirmation_dialog') is True and
          proof.get('preview_timed_cycle') is True and proof.get('curve_release_verified') is True,
          'Curve release requires verified menu, schema migration and recovery.')
  for key in ('film-worklog/proof.json','film-controls/proof.json',
              'native-fivepoint-capture-test/proof.json','native-resource-fl3-curves/report.json',
              'native-adjust-film/integration-proof.json'):
   require(key in proof.get('dependency_proof_sha256',{}),'Missing curve evidence: '+key)
  return
 if revision not in (4,5,6,7,8,9,10,11,12):return
 c=proof.get('capture_look');deps=proof.get('dependency_proof_sha256')
 require(isinstance(c,dict) and isinstance(deps,dict) and proof.get('spatial_settings_only') is True and
         c.get('arm_transaction_verified') is True and c.get('fixed_capture_tables') is (revision==4) and
         c.get('property_ids')==[0x30005,0x30006],'Capture release requires the tested two-table module.')
 if revision>=5:
  require(c.get('dynamic_capture_controls') is True and c.get('control_count')==5 and
          c.get('base_delta_scale')==[3,2] and c.get('max_packed_delta')==[24,32,32] and
          c.get('controls_proof_sha256')==deps.get('native-capture-controls-test/proof.json'),
          'Revision 5 requires verified adjustable CAP controls.')
 if revision>=6:
  require(proof.get('save_confirmation_dialog') is True and
          isinstance(deps.get('native-save-dialog/proof.json'),str),
          'Revision 6 requires the tested native confirmation dialog.')
 if revision==8:
  require(proof.get('preview_refresh_request') is True and
          isinstance(deps.get('native-preview-request/proof.json'),str),
          'Revision 8 requires the guarded same-value preview replay tests.')
 if revision>=9:
  require(proof.get('preview_refresh_request') is True and proof.get('preview_timed_cycle') is True and
          isinstance(deps.get('native-preview-cycle/proof.json'),str),
          'Revision 9 requires the guarded native timer cycle tests.')
 if revision in (11,12):
  require(proof.get('independent_look_banks') is True and proof.get('fl2_resource')==0x0204fda8 and
          isinstance(deps.get('native-resource-fl2/report.json'),str) and
          all(x in proof.get('artifact_sha256',{}) for x in ('bank-boot.log','module-bank-boot-test.elf')),'Revision 11 requires separate banks and verified FL2 resource.')
 if revision==12:
  require(proof.get('leica_look') is True and proof.get('preference_schema')==3 and
          isinstance(deps.get('native-resource-fl3/report.json'),str) and
          all(x in proof.get('artifact_sha256',{}) for x in ('leica-boot.log','module-leica-boot-test.elf')),'Revision 12 requires tested FL3 and three-bank cold boot.')
 digest=c.get('source_qemu_proof_sha256')
 if revision>=10:
  require(proof.get('dual_look') is True and
          all(x in proof.get('artifact_sha256',{}) for x in ('qemu.log','cinema-boot.log','module-cinema-boot-test.elf')) and
          all(x in proof.get('source_sha256',{}) for x in ('payloads/a7-fl-fl2-model.inc','recipes/fl2-reference-srgb.json')),
          'Revision 10 requires the FL2 model and both-preset integration/boot evidence.')
 require(isinstance(digest,str) and len(digest)==64 and all(x in '0123456789abcdef' for x in digest) and
         digest in deps.values(),'Revision 4 requires its capture QEMU proof as a pinned dependency.')
def syncdir(p):
 fd=os.open(p,os.O_RDONLY)
 try:os.fsync(fd)
 finally:os.close(fd)
class Bundle:
 def __init__(self,directory):
  self.directory=d=Path(directory).resolve();m=self.manifest=json.loads((d/'manifest.json').read_text());pin_sources(m)
  revision=m['version'];require(revision in REVISIONS and m['kind']==f'native-module-replace-r{revision}','Foreign module replacement binding.');r=REVISIONS[revision]
  self.locale=r.get('locale');parent='/usr/share/app/' if self.locale else '/usr/lib/'
  self.target=parent+(self.locale or 'a7fl.so')
  self.temporary=parent+r['temporary'];self.backup=parent+r['backup'];self.journal='/setting/'+r['journal']
  require(m['old']==dict(sha256=r['old_sha'],size=r['old_size']) and m['view']==dict(sha256=VIEW_SHA,size=10854816),'Incorrect deployed baseline.')
  proof=d/'module-proof.json';require(file_sha(proof)==m['module_proof_sha256'],'Module proof changed.');p=json.loads(proof.read_text());pin_sources(p)
  if self.locale:
   resource_set=r.get('resource_set','fl2')
   resource_path=LAB/f'native-resource-{resource_set}/report.json'
   require(file_sha(resource_path)==m['resource_proof_sha256'],'Locale parser evidence changed.')
   resource=json.loads(resource_path.read_text());pin_sources(resource)
   require(resource['input_proof_sha256']==m['module_proof_sha256'],'Locale parser input changed.')
   require(p.get('kind')==resource_set+'-additive-locales-v1' and p['files'][self.locale]['after_sha256']==m['new']['sha256'] and p['files'][self.locale]['before_sha256']==r['old_sha'],'Unattested additive locale.')
  else:
   require(p.get('ready_for_staging') is True and p.get('placeholder') is False and p['module_sha256']==m['new']['sha256'],'Unattested module.')
  require_capture_release(revision,p)
  for n,h in p.get('dependency_proof_sha256',{}).items():
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
 require_file(f,getattr(b,'target',MODULE),m['old'],e/'old-module.so');require_file(f,VIEW,m['view'],e/'view-before.so')
 if m['version'] in (11,12,13,14):
  resource_set='fl-curve' if m['version'] in (13,14) else 'fl3' if m['version']==12 else 'fl2'
  resource=json.loads((LAB/f'native-{resource_set}-strings/proof.json').read_text())
  for name,record in resource['files'].items():
   require_file(f,'/usr/share/app/'+name,dict(size=record['after_bytes'],sha256=record['after_sha256']),e/('required-'+name))
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
 require_file(f,getattr(b,'target',MODULE),m['new'],e/'new-module-readback.so');require_file(f,b.backup,m['old'],e/'old-backup-readback.so');require_file(f,VIEW,m['view'],e/'view-after.so')
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
