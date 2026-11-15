"""Evidence gate for the six-look L/M/S spatial-backend update."""
import json
from local import LAB, file_sha, require


def require_auto_release(proof):
    from camera.native_module_replace import pin_sources
    flags = ('ready_for_staging','hardware_basis_verified','capture_auto_size',
             'capture_vignette_kernel','capture_vignette_menu','capture_halation_menu',
             'capture_grain_menu','all_look_curves','independent_look_banks',
             'save_confirmation_dialog','preview_timed_cycle','curve_release_verified',
             'confirmed_history_boot_recovery')
    require(all(proof.get(k) is True for k in flags) and
            proof.get('look_count') == 6 and proof.get('preference_schema') == 6,
            'Auto-size update requires all integrated controls and same-kernel JPEG evidence.')
    deps = proof.get('dependency_proof_sha256', {})
    for key in ('film-worklog-vignette/proof.json','film-controls-halation-vignette/proof.json',
                'native-fivepoint-capture-test/proof.json','native-resource-vignette/report.json',
                'native-adjust-film/integration-proof.json','grain-backend/proof.json',
                'capture-auto-control/proof.json','capture-auto-record/proof.json',
                'capture-auto-test/proof.json','capture-auto-geometry/proof.json',
                'capture-dimensions-test/proof.json','film-vignette/proof.json',
                'native-boot-recovery/proof.json','native-resource-classic/report.json',
                'native-fl-classic-strings/proof.json'):
        require(key in deps, 'Missing auto-size evidence: '+key)
    bases = [k for k in deps if k.startswith('capture-kernel/') and k.endswith('/jpeg-auto-proof.json')]
    require(len(bases) == 1 and any(k.startswith('auto-backend-live/') for k in deps),
            'Exact-kernel L/M/S JPEG and live bridge evidence required.')
    path = (LAB/bases[0]).resolve()
    require(path.is_relative_to(LAB) and file_sha(path) == deps[bases[0]], 'JPEG basis changed.')
    jpeg = json.loads(path.read_text())
    pin_sources(jpeg)
    require(jpeg.get('passed') is True and jpeg.get('sizes_verified') is True and
            jpeg.get('kernel_sha256') == proof['kernel_sha256'], 'L/M/S JPEG verification failed.')
    for name, digest in jpeg['artifact_sha256'].items():
        target = (path.parent/name).resolve()
        require(target.is_relative_to(path.parent) and file_sha(target) == digest, 'JPEG evidence changed.')
    from research.capture_auto_fetch import decode
    samples = decode((path.parent/'auto-samples.bin').read_bytes())
    require(all(s['verified'] for s in samples) and
            [s['output_size'] for s in samples] == [[6000,4000],[3936,2624],[3008,2000]],
            'Source geometry or pixels failed validation.')
    require(all(n in proof.get('artifact_sha256', {}) for n in
                ('six-boot.log','module-six-boot-test.elf','grain.ko','grain-blob.S',
                 'a7-fl-grain-kernel.h','grain-sample-proof.json')),
            'Embedded kernel or six-look cold-start fixtures missing.')
