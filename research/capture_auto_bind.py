"""Bind the exact auto-size kernel to its source and L/M/S JPEG evidence."""
import json
from pathlib import Path
from capture_vignette_bind import ROOT, LAB, sha, current


def bind(kernel, bridge_path, basis, out):
    k = json.loads((kernel/'proof.json').read_text())
    current(k)
    if k.get('route') != 'auto' or k.get('module_name') != 'a7capauto':
        raise ValueError('Expected auto-size kernel')
    blob = kernel/'a7capauto.ko'
    if sha(blob) != k['module_sha256']:
        raise ValueError('Auto-size kernel changed')
    if not any(r['action'] == 'selftest' and r['verified'] for r in k['live']):
        raise ValueError('Same-binary private kernel selftest missing')
    bridge = json.loads(bridge_path.read_text())
    current(bridge)
    if not bridge.get('passed') or not bridge.get('camera_run') or bridge['kernel_sha256'] != sha(blob):
        raise ValueError('Same-binary live parameter bridge missing')
    deps = {}
    for p in (kernel/'proof.json', bridge_path, LAB/'grain-backend/proof.json',
              LAB/'capture-auto-control/proof.json', LAB/'capture-auto-record/proof.json',
              LAB/'capture-auto-test/proof.json', LAB/'capture-auto-geometry/proof.json',
              LAB/'capture-dimensions-test/proof.json', LAB/'film-vignette/proof.json'):
        test = json.loads(p.read_text())
        current(test)
        if p.parent.name in ('grain-backend', 'capture-auto-control', 'capture-auto-record',
                            'capture-auto-geometry', 'capture-dimensions-test') and not test.get('passed'):
            raise ValueError('Required test failed: '+str(p))
        deps[str(p.relative_to(LAB))] = sha(p)
    ready = False
    evidence = dict(passed=False, kernel_sha256=sha(blob), firmware_written=False,
                    scope='Offline integration; exact-kernel L/M/S JPEG evidence required')
    if basis is not None:
        b = json.loads((basis/'proof.json').read_text())
        current(b)
        if b['module_sha256'] != k['module_sha256'] or not b.get('diagnostic'):
            raise ValueError('JPEG basis must use the exact diagnostic binary')
        jpeg = json.loads((basis/'jpeg-auto-proof.json').read_text())
        current(jpeg)
        for name, digest in jpeg['artifact_sha256'].items():
            path = (basis/name).resolve()
            if not path.is_relative_to(basis.resolve()) or sha(path) != digest:
                raise ValueError('Photo evidence changed: '+name)
        from capture_auto_fetch import decode
        samples = decode((basis/'auto-samples.bin').read_bytes())
        runs = [r for r in b['live'] if r['action'] == 'collect' and r['verified']]
        if not runs or runs[-1]['values'][355] != 3 or runs[-1]['values'][357]:
            raise ValueError('Three successful diagnostic captures required')
        ready = bool(jpeg.get('passed') and jpeg.get('sizes_verified') and
                     jpeg.get('kernel_sha256') == sha(blob) and all(s['verified'] for s in samples))
        evidence.update(passed=ready, jpeg_proof_sha256=sha(basis/'jpeg-auto-proof.json'),
                        sample_sha256=sha(basis/'auto-samples.bin'), basis_dir=str(basis),
                        scope='Same-binary full-frame 3:2 JPEG L/M/S; resident boot uses diagnostic=0. Cold-boot acceptance remains required.')
        for p in (basis/'proof.json', basis/'jpeg-auto-proof.json'):
            deps[str(p.relative_to(LAB))] = sha(p)
    (out/'grain.ko').write_bytes(blob.read_bytes())
    (out/'grain-sample-proof.json').write_text(json.dumps(evidence, indent=2)+'\n')
    (out/'a7-fl-grain-kernel.h').write_text('#define A7_GRAIN_KERNEL_NAME "a7capauto"\nstatic const unsigned a7_grain_kernel_source_id[]={'+','.join(map(str,k['source_id']))+'};\n')
    (out/'grain-blob.S').write_text('.section .rodata\n.balign 4\n.global a7_grain_kernel_start,a7_grain_kernel_end\na7_grain_kernel_start:\n.incbin "grain.ko"\na7_grain_kernel_end:\n.section .note.GNU-stack,"",%progbits\n')
    return k, deps, ready
