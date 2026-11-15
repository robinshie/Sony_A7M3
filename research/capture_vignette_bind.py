"""Bind the vignette kernel; allow staging only after same-binary JPEG evidence."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT/'.lab'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def current(proof):
    for name, digest in proof.get('source_sha256', {}).items():
        if sha(ROOT/name) != digest:
            raise ValueError('Stale vignette source: '+name)


def bind(kernel, bridge_path, basis, out):
    k = json.loads((kernel/'proof.json').read_text())
    current(k)
    if k.get('route') != 'vignette' or k.get('module_name') != 'a7capvig':
        raise ValueError('Expected vignette kernel')
    blob = kernel/'a7capvig.ko'
    if sha(blob) != k['module_sha256']:
        raise ValueError('Vignette kernel changed')
    if not any(r['action'] == 'selftest' and r['verified'] for r in k['live']):
        raise ValueError('Same-module private kernel selftest missing')
    bridge = json.loads(bridge_path.read_text())
    current(bridge)
    if not bridge.get('passed') or not bridge.get('camera_run') or bridge['kernel_sha256'] != sha(blob):
        raise ValueError('Same-module live parameter bridge missing')
    deps = {}
    for p in (kernel/'proof.json', bridge_path, LAB/'grain-backend/proof.json',
              LAB/'capture-vignette-control/proof.json', LAB/'capture-vignette-record/proof.json',
              LAB/'capture-vignette-test/proof.json', LAB/'film-vignette/proof.json'):
        test = json.loads(p.read_text())
        current(test)
        if p.parent.name in ('grain-backend', 'capture-vignette-control', 'capture-vignette-record') and not test.get('passed'):
            raise ValueError('Required test failed: '+str(p))
        deps[str(p.relative_to(LAB))] = sha(p)
    ready = False
    evidence = dict(passed=False, kernel_sha256=sha(blob), firmware_written=False,
                    scope='Offline integration only; same-binary three-shot JPEG evidence required')
    if basis is not None:
        b = json.loads((basis/'proof.json').read_text())
        current(b)
        if b['module_sha256'] != k['module_sha256'] or not b.get('diagnostic'):
            raise ValueError('JPEG basis must be the exact diagnostic binary')
        jpeg = json.loads((basis/'jpeg-vignette-proof.json').read_text())
        current(jpeg)
        for name, digest in jpeg['artifact_sha256'].items():
            if sha(basis/name) != digest:
                raise ValueError('Photo evidence changed: '+name)
        from capture_vignette_fetch import decode
        samples = decode((basis/'vignette-samples.bin').read_bytes())
        runs = [r for r in b['live'] if r['action'] == 'collect' and r['verified']]
        if not runs or runs[-1]['values'][355] != 3 or runs[-1]['values'][357]:
            raise ValueError('Three successful diagnostic captures required')
        ready = bool(jpeg.get('passed') and jpeg.get('exposure_consistent') and
                     jpeg.get('kernel_sha256') == sha(blob) and all(s['verified'] for s in samples))
        evidence.update(passed=ready, jpeg_proof_sha256=sha(basis/'jpeg-vignette-proof.json'),
                        sample_sha256=sha(basis/'vignette-samples.bin'), basis_dir=str(basis),
                        scope='Same-binary JPEG L three-shot vignette test; resident boot uses diagnostic=0. Firmware still requires cold-boot acceptance.')
        for p in (basis/'proof.json', basis/'jpeg-vignette-proof.json'):
            deps[str(p.relative_to(LAB))] = sha(p)
    (out/'grain.ko').write_bytes(blob.read_bytes())
    (out/'grain-sample-proof.json').write_text(json.dumps(evidence, indent=2)+'\n')
    (out/'a7-fl-grain-kernel.h').write_text('#define A7_GRAIN_KERNEL_NAME "a7capvig"\nstatic const unsigned a7_grain_kernel_source_id[]={'+','.join(map(str,k['source_id']))+'};\n')
    (out/'grain-blob.S').write_text('.section .rodata\n.balign 4\n.global a7_grain_kernel_start,a7_grain_kernel_end\na7_grain_kernel_start:\n.incbin "grain.ko"\na7_grain_kernel_end:\n.section .note.GNU-stack,"",%progbits\n')
    return k, deps, ready
