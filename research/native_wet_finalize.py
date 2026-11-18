"""Validate actual JPEG/kernel evidence and catalog preservation before binding."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from local import LAB,file_sha
from camera.native_wet_release import verify_wet_basis,require_wet_release

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--bridge',type=Path,required=True);p.add_argument('--catalog-snapshot',type=Path,required=True);a=p.parse_args()
 out=LAB/'native-module-wet-candidate';path=out/'proof.json';proof=json.loads(path.read_text())
 snapshot=a.catalog_snapshot.resolve()
 if not snapshot.is_relative_to(LAB):raise ValueError('Snapshot must be private lab evidence')
 sources=['payloads/a7-fl-custom'+s+'.c' for s in ('','-store','-effective','-session')]+['payloads/a7-fl-runtime-prefs.c','payloads/a7-fl-runtime.c']
 flags=['-DA7_FL_'+s for s in 'SIX_LOOKS FILM_CONTROLS CAPTURE_VIGNETTE CAPTURE_HALATION CAPTURE_GRAIN LOOK_BANKS LEICA_LOOK DUAL_LOOK'.split()]
 for name in ('wet_look_session','wet_catalog_migration'):
  test='research/'+name+'_test.c';exe=out/name
  subprocess.run(['cc','-O2','-Wall','-Wextra','-Werror','-Wno-missing-field-initializers',*flags,'-I'+str(ROOT/'payloads'),test,*sources,'-o',str(exe)],cwd=ROOT,check=True)
  args=[str(exe)]+([str(snapshot/f'A7CU{i}.CFG') for i in range(2)] if name=='wet_catalog_migration' else [])
  r=subprocess.run(args,capture_output=True,check=True);(out/(name+'.log')).write_bytes(r.stdout+r.stderr);print(r.stdout.decode(),end='')
  for x in (name,name+'.log'):proof['artifact_sha256'][x]=file_sha(out/x)
  proof['source_sha256'][test]=file_sha(ROOT/test)
 proof['source_sha256']['research/native_wet_finalize.py']=file_sha(Path(__file__))
 proof['catalog_snapshot']={str((snapshot/f'A7CU{i}.CFG').relative_to(LAB)):file_sha(snapshot/f'A7CU{i}.CFG') for i in range(2)}
 proof['wet_bridge_proof']=str(a.bridge.resolve())
 proof['dependency_proof_sha256']=verify_wet_basis(proof)
 proof.update(hardware_basis_verified=True,ready_for_staging=True,normal_mode_verified=False,flash_ready=False,scope='Exact kernel verified by real L/M/S JPEGs; integrated original ARM menu and boot tests passed. Physical complete-menu cold boot still requires trial after installation.')
 require_wet_release(proof)
 path.write_text(json.dumps(proof,indent=2)+'\n')
 print('WET_STAGING_VALIDATED',proof['module_sha256'])
if __name__=='__main__':main()
