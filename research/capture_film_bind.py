"""Bind the integrated kernel to its tests and separately identified real-shot basis.

The resident candidate and the three-shot diagnostic are different modules.
Only a passed real JPEG basis can mark the final menu candidate stageable.
"""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
LAB=ROOT/'.lab'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def current(proof):
 for n,h in proof.get('source_sha256',{}).items():
  if sha(ROOT/n)!=h:raise ValueError('Stale film source: '+n)
def bind(kernel,bridge_path,basis,out):
 k=json.loads((kernel/'proof.json').read_text());current(k)
 if k.get('route')!='film' or k.get('module_name')!='a7capfilm':raise ValueError('Expected resident film module')
 blob=kernel/'a7capfilm.ko'
 if sha(blob)!=k['module_sha256']:raise ValueError('Film kernel changed')
 if not any(r['action']=='selftest' and r['verified'] for r in k['live']):raise ValueError('Same-module kernel selftest missing')
 bridge=json.loads(bridge_path.read_text());current(bridge)
 if not bridge.get('passed') or not bridge.get('camera_run') or bridge['kernel_sha256']!=sha(blob):raise ValueError('Same-module live film bridge required')
 deps={}
 for p in (kernel/'proof.json',bridge_path,LAB/'grain-backend/proof.json',LAB/'capture-film-control/proof.json',LAB/'capture-film-record/proof.json',LAB/'capture-film-test/proof.json'):
  proof=json.loads(p.read_text());current(proof)
  if p.name=='proof.json' and p.parent.name in ('grain-backend','capture-film-control','capture-film-record') and not proof.get('passed'):
   raise ValueError('Required film test did not pass')
  deps[str(p.relative_to(LAB))]=sha(p)
 b=json.loads((basis/'proof.json').read_text());jpeg=json.loads((basis/'jpeg-halation-proof.json').read_text());current(jpeg)
 for n in ('payloads/a7-film-frame.c','payloads/a7-film-frame.h','research/kernel_probe/capture_lease_record.h','research/kernel_probe/capture_early_record.h'):
  if b['source_sha256'].get(n)!=sha(ROOT/n) or k['source_sha256'].get(n)!=sha(ROOT/n):
   raise ValueError('Resident filter/lease differs from real-shot basis: '+n)
 for n,h in jpeg['artifact_sha256'].items():
  if sha(basis/n)!=h:raise ValueError('Real photo evidence changed: '+n)
 if jpeg['kernel_sha256']!=b['module_sha256'] or jpeg['algorithm_sha256']!=sha(ROOT/'payloads/a7-film-frame.c'):
  raise ValueError('JPEG experiment identity differs')
 from capture_halation_fetch import decode
 samples=decode((basis/'halation-samples.bin').read_bytes())
 ready=bool(jpeg.get('passed') and jpeg.get('exposure_consistent') and all(s['verified'] for s in samples))
 basis_proof=dict(passed=ready,diagnostic_kernel_sha256=b['module_sha256'],resident_kernel_sha256=k['module_sha256'],
                  scope='Resident selftest/config verified; identical pixel filter and exclusive lease were tested by a separate three-shot module. Final firmware still needs cold-boot acceptance.',
                  source_sha256={n:sha(ROOT/n) for n in ('research/capture_film_bind.py','research/capture_halation_fetch.py','payloads/a7-film-frame.c','payloads/a7-film-frame.h','research/kernel_probe/capture_lease_record.h','research/kernel_probe/capture_early_record.h')},
                  basis_dir=str(basis),jpeg_proof_sha256=sha(basis/'jpeg-halation-proof.json'),
                  basis_proof_sha256=sha(basis/'proof.json'),sample_sha256=sha(basis/'halation-samples.bin'),
                  evidence_sha256=jpeg['artifact_sha256'],firmware_written=False)
 directory=LAB/'film-hardware-basis'/k['module_sha256'];directory.mkdir(parents=True,exist_ok=True)
 p=directory/'proof.json';p.write_text(json.dumps(basis_proof,indent=2)+'\n');deps[str(p.relative_to(LAB))]=sha(p)
 (out/'grain.ko').write_bytes(blob.read_bytes())
 (out/'grain-sample-proof.json').write_bytes(p.read_bytes())
 (out/'a7-fl-grain-kernel.h').write_text('#define A7_GRAIN_KERNEL_NAME "a7capfilm"\nstatic const unsigned a7_grain_kernel_source_id[]={'+','.join(map(str,k['source_id']))+'};\n')
 (out/'grain-blob.S').write_text('.section .rodata\n.balign 4\n.global a7_grain_kernel_start,a7_grain_kernel_end\na7_grain_kernel_start:\n.incbin "grain.ko"\na7_grain_kernel_end:\n.section .note.GNU-stack,"",%progbits\n')
 return k,deps,ready
