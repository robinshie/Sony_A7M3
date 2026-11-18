"""Fail-closed release gate for the exact wet-plate kernel and real L/M/S JPEGs."""
import json
from pathlib import Path
from local import ROOT,LAB,require,file_sha

def check_current(proof):
 require(bool(proof.get('source_sha256')),'Missing source proof')
 for name,digest in proof['source_sha256'].items():
  path=(ROOT/name).resolve();require(path.is_relative_to(ROOT) and file_sha(path)==digest,'Source changed: '+name)

def verify_wet_basis(proof):
 directory=LAB/'native-module-wet-candidate'
 require(proof.get('passed') is True and proof.get('kernel_bound') is True and proof.get('placeholder') is False,'Wet menu/kernel integration missing')
 check_current(proof)
 require(file_sha(directory/'liba7-fl-module.so')==proof['module_sha256'],'Wet module changed')
 for name,digest in proof['artifact_sha256'].items():require(file_sha(directory/name)==digest,'Wet artifact changed: '+name)
 for name,digest in proof['fixture_sha256'].items():require(file_sha(ROOT/name)==digest,'Wet native fixture changed: '+name)
 for name,marker in [('qemu.log',b'NATIVE_WET_FLOW_PASSED'),('qemu-boot.log',b'NATIVE_WET_BOOT_PASSED'),('dialog.log',b'SD_FILE_DIALOG_PASSED')]:
  raw=(directory/name).read_bytes();require(marker in raw and b'FAIL' not in raw,'Wet integration failed: '+name)
 for name,marker in [('wet_look_session.log',b'WET_SESSION_PASSED'),('wet_catalog_migration.log',b'WET_ACTUAL_CATALOG_MIGRATION_PASSED')]:
  raw=(directory/name).read_bytes();require(marker in raw and b'FAIL' not in raw,'Catalog preservation failed: '+name)
 require(len(proof.get('catalog_snapshot',{}))==2,'Current catalog evidence missing')
 for name,digest in proof['catalog_snapshot'].items():
  path=(LAB/name).resolve();require(path.is_relative_to(LAB) and file_sha(path)==digest,'Catalog snapshot changed')
 kernel=Path(proof['kernel_bundle']).resolve();require(kernel.is_relative_to(LAB/'capture-kernel'),'Foreign kernel folder')
 kp=json.loads((kernel/'proof.json').read_text());check_current(kp)
 require(kp['route']=='wet' and kp['module_name']=='a7capwet' and file_sha(kernel/'a7capwet.ko')==proof['kernel_sha256']==kp['module_sha256']==file_sha(directory/'grain.ko'),'Kernel identity mismatch')
 require(any(r['action']=='selftest' and r['verified'] for r in kp['live']),'Real kernel selftest missing')
 runs=[r for r in kp['live'] if r['action']=='collect' and r['verified']]
 require(runs and runs[-1]['values'][353]==86672 and runs[-1]['values'][355]==3 and runs[-1]['values'][357]==0,'Three wet captures without errors required')
 from research.capture_wet_fetch import decode
 frames=decode((kernel/'wet-samples.bin').read_bytes())
 require(all(f['verified'] for f in frames) and [f['output_size'] for f in frames]==[[6000,4000],[3936,2624],[3008,2000]],'Wet source/size evidence failed')
 jpeg=json.loads((kernel/'jpeg-wet-proof.json').read_text());check_current(jpeg)
 require(jpeg.get('passed') is True and jpeg.get('sizes_verified') is True and jpeg['kernel_sha256']==proof['kernel_sha256'],'Real wet JPEG verification failed')
 for name,digest in jpeg['artifact_sha256'].items():
  path=(kernel/name).resolve();require(path.is_relative_to(kernel) and file_sha(path)==digest,'JPEG evidence changed: '+name)
 bridge=Path(proof['wet_bridge_proof']).resolve();require(bridge.is_relative_to(LAB/'wet-backend-live'),'Foreign bridge folder')
 bp=json.loads(bridge.read_text());check_current(bp)
 require(bp.get('passed') is True and bp.get('camera_run') is True and bp['kernel_sha256']==proof['kernel_sha256'],'Real wet control bridge failed')
 paths=[kernel/'proof.json',kernel/'jpeg-wet-proof.json',bridge]
 for name in ('capture-wet-control','capture-wet-record','grain-backend'):
  path=LAB/name/'proof.json';d=json.loads(path.read_text());check_current(d);require(d.get('passed') is True,'Wet test failed: '+name);paths.append(path)
 for name in ('native-resource-wet/report.json','native-fl-wet-strings/proof.json'):
  path=LAB/name;check_current(json.loads(path.read_text()));paths.append(path)
 return {str(p.relative_to(LAB)):file_sha(p) for p in paths}

def require_wet_release(proof):
 require(proof.get('ready_for_staging') is True and proof.get('hardware_basis_verified') is True,'Wet candidate has not passed real-photo validation')
 for name,digest in verify_wet_basis(proof).items():
  require(proof.get('dependency_proof_sha256',{}).get(name)==digest,'Wet dependency missing or changed: '+name)
