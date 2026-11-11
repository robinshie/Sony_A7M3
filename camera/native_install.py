"""Verify or explicitly stage the attested native FL module/locales.

Default operation is verify. This CLI never activates the loader, deletes an
installation journal, resumes an interrupted transaction, or performs an automatic
rollback. rollback-review records the exact device state for a separate reviewed
recovery. --offline performs local proof validation without importing USB tools.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import time

from local import BUILD_ID, LAB, ROOT, file_sha, require, sha

FINAL = ('/usr/lib/a7fl.so', '/usr/share/app/string_simplifiedchinese.uxc',
         '/usr/share/app/string_english.uxc')
STAGE = ('/usr/lib/.a7fl.new', '/usr/share/app/.a7fl-zh.new', '/usr/share/app/.a7fl-en.new')
BACKUPS = ('/usr/share/app/.a7fl-zh.orig', '/usr/share/app/.a7fl-en.orig')
JOURNAL = '/setting/A7FL.INSTALL'
VIEW = '/usr/lib/viewUnified2.so'
PHASES = {1, 2, 10, 11, 12, 20, 21, 22, 30, 31, 40, 41, 42, 44, 45, 46, 60, 90, 99, 100}
FORWARD = ((1, 0, 0, 0), (2, 0, 0, 0), (10, 0, 0, 0), (20, 1, 0, 0),
           (11, 1, 0, 0), (21, 3, 0, 0), (12, 3, 0, 0), (22, 7, 0, 0),
           (30, 7, 0, 0), (31, 6, 1, 0), (40, 6, 1, 0), (41, 6, 1, 1),
           (42, 4, 3, 1), (44, 4, 3, 1), (45, 4, 3, 3), (46, 0, 7, 3),
           (60, 0, 7, 3), (100, 0, 7, 3))
FORWARD_STATE = {phase: (created, published, backed) for phase, created, published, backed in FORWARD}
FORWARD_NEXT = {old[0]: new[0] for old, new in zip(FORWARD, FORWARD[1:])}


def save(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def save_json(path, value):
    save(path, (json.dumps(value, indent=2, ensure_ascii=False)+'\n').encode())


def pin_sources(proof, prefix=''):
    require(bool(proof.get('source_sha256')), 'Missing source attestation.')
    for name, digest in proof['source_sha256'].items():
        path = (ROOT/prefix/name).resolve()
        require(path.is_relative_to(ROOT), 'Source attestation escaped repository.')
        require(path.is_file() and file_sha(path) == digest, 'Source changed after verification: '+name)


def journal_records(raw, binding):
    """Retain a valid prefix for recovery review; never treat a torn suffix as success."""
    records = []
    error = None
    for offset in range(0, len(raw)//88*88, 88):
        record = raw[offset:offset+88]
        magic, sequence, phase, created, published, backed = struct.unpack_from('<6I', record)
        if (magic != 0x4137464a or sequence != len(records)+1 or phase not in PHASES or
                created & ~7 or published & ~7 or backed & ~3 or record[24:56].hex() != binding or
                hashlib.sha256(record[:56]).digest() != record[56:]):
            error = 'Invalid or foreign record at byte '+str(offset)
            break
        previous = records[-1]['phase'] if records else None
        forward = (phase in FORWARD_STATE and
                   phase == (1 if previous is None else FORWARD_NEXT.get(previous)) and
                   (created, published, backed) == FORWARD_STATE[phase])
        failure = ((phase == 90 and previous in FORWARD_NEXT) or
                   (phase == 99 and previous in (60, 90)))
        if not (forward or failure):
            error = 'Invalid transaction transition at byte '+str(offset)
            break
        records.append(dict(sequence=sequence, phase=phase, created=created,
                            published=published, backed_up=backed))
    if error is None and len(raw) % 88:
        error = 'Torn trailing journal record'
    if error is None and not records:
        error = 'Empty journal'
    return dict(records=records, last=records[-1] if records else None,
                integrity_error=error, bytes=len(raw), sha256=sha(raw))


def install_report(raw, binding):
    require(len(raw) == 72, 'Unexpected installer report length.')
    values = struct.unpack('<6I4i32s', raw)
    names = ('magic', 'version', 'phase', 'created', 'published', 'backed_up',
             'status', 'first_error', 'rollback_ok', 'readonly_confirmed')
    result = dict(zip(names, values[:10]))
    result['bundle_sha256'] = values[10].hex()
    require(result['magic'] == 0x41374649 and result['version'] == 1 and
            result['bundle_sha256'] == binding, 'Foreign installer report.')
    return result


class Bundle:
    def __init__(self, directory, module_proof, base, strings):
        self.directory = directory
        self.manifest_path = directory/'manifest.json'
        self.manifest = json.loads(self.manifest_path.read_text())
        m = self.manifest
        require(m.get('package_kind') == 'native-filesystem-module-locales-only-v1' and
                m.get('module_placeholder') is False and m.get('loader_activated') is False,
                'This is not an attested filesystem-only installation bundle.')
        pin_sources(m)
        require(file_sha(module_proof) == m['module_proof_sha256'], 'Module proof changed.')
        module = json.loads(module_proof.read_text())
        require(module.get('placeholder') is False and module.get('ready_for_staging') is True,
                'Module is not ready for staging.')
        pin_sources(module)
        require(bool(module.get('dependency_proof_sha256')), 'Missing bootstrap/loader evidence.')
        for name, digest in module['dependency_proof_sha256'].items():
            path = (LAB/name).resolve()
            require(path.is_relative_to(LAB) and file_sha(path) == digest, 'Dependency proof changed: '+name)
            pin_sources(json.loads(path.read_text()))
        fault_path = LAB/'native-install-test/proof.json'
        require(file_sha(fault_path) == m['fault_proof_sha256'], 'Installer fault proof changed.')
        pin_sources(json.loads(fault_path.read_text()))
        resource_path = LAB/'native-resource/report.json'
        require(file_sha(resource_path) == m['resource_proof_sha256'], 'Resource lookup proof changed.')
        resource = json.loads(resource_path.read_text())
        pin_sources(resource, 'research')
        strings_proof_path = strings/'proof.json'
        require(file_sha(strings_proof_path) == resource['input_proof_sha256'], 'Locale proof changed.')
        locale = json.loads(strings_proof_path.read_text())
        pin_sources(locale)
        self.base = json.loads((base/'manifest.json').read_text())
        self.files = m['files']
        require(len(self.files) == 3 and [f['name'] for f in self.files] ==
                ['liba7-fl-module.so', 'string_simplifiedchinese.uxc', 'string_english.uxc'],
                'Unexpected installation targets.')
        for index, record in enumerate(self.files):
            path = directory/f'input{index}.bin'
            require(0 < record['size'] <= 1024*1024 and path.stat().st_size == record['size'] and
                    file_sha(path) == record['sha256'], 'Bound input changed: '+record['name'])
        require(self.files[0]['sha256'] == module['module_sha256'], 'Module input/proof differ.')
        self.old = []
        for record in self.files[1:]:
            entry = locale['files'][record['name']]
            require(entry['after_sha256'] == record['sha256'] and entry['after_bytes'] == record['size'],
                    'Bound locale differs from native lookup proof.')
            previous = self.base['files']['/share/app/'+record['name']]
            require(entry['before_sha256'] == previous['after_sha256'] and
                    entry['before_bytes'] == previous['after_bytes'], 'Locale baseline differs.')
            self.old.append(dict(size=entry['before_bytes'], sha256=entry['before_sha256']))
        self.view = self.base['files']['/lib/viewUnified2.so']
        require(file_sha(base/'viewUnified2.so') == self.view['after_sha256'], 'Original view baseline changed.')
        binding = hashlib.sha256(b'A7M3-4.04-filesystem-stage-v1\0'+struct.pack('<II', 1, 0)+bytes.fromhex(m['module_proof_sha256']))
        for record in self.files+self.old:
            binding.update(struct.pack('<I', record['size'])+bytes.fromhex(record['sha256']))
        binding.update(struct.pack('<I', self.view['after_bytes'])+bytes.fromhex(self.view['after_sha256']))
        require(binding.hexdigest() == m['bundle_sha256'], 'Bundle binding mismatch.')
        self.payload = (directory/'install.so').read_bytes()
        require(52 < len(self.payload) <= 1024*1024 and sha(self.payload) == m['payload_sha256'] and
                self.payload[:7] == b'\x7fELF\x01\x01\x01' and self.payload[16:20] == b'\x03\0(\0',
                'Installer is not the bound ARM shared object.')
        self.loader = None
        loader_path = LAB/'native-menu-boot-loader/proof.json'
        if loader_path.is_file():
            loader = json.loads(loader_path.read_text())
            pin_sources(loader)
            require(loader['before_sha256'] == self.view['after_sha256'], 'Loader baseline differs.')
            self.loader = loader


def mount_payload(output):
    """Use the existing read-only stream probe: maintenance stat(/proc) is zero."""
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    source = ROOT/'payloads/a7-mount-probe.c'
    obj, target = output/'mount.o', output/'mount.so'
    subprocess.run(['arm-none-eabi-gcc', '-mcpu=cortex-a9', '-marm', '-mfloat-abi=soft',
                    '-mno-unaligned-access', '-Os', '-fPIC', '-ffreestanding', '-fno-builtin',
                    '-fno-stack-protector', '-fno-unwind-tables', '-fno-asynchronous-unwind-tables',
                    '-Wall', '-Wextra', '-Werror', '-c', str(source), '-o', str(obj)], check=True)
    subprocess.run(['arm-none-eabi-ld', '-shared', '--no-undefined', '-z', 'noexecstack',
                    str(obj), '-o', str(target)], check=True)
    raw = target.read_bytes()
    require(len(raw) <= 16384 and raw[:7] == b'\x7fELF\x01\x01\x01', 'Invalid mount probe.')
    save_json(output/'mount-proof.json', dict(source_sha256=file_sha(source), payload_sha256=sha(raw)))
    return raw


def read_mounts(factory, probe, evidence):
    raw = factory.run(probe, 'a7mount.bin')
    save(evidence/'mount-report.bin', raw)
    require(len(raw) == 16392, 'Mount report length mismatch.')
    magic, length = struct.unpack_from('<Ii', raw)
    require(magic == 0x41374d50 and 0 < length < 16384, 'Mount stream probe failed.')
    data = raw[8:8+length]
    save(evidence/'mounts.txt', data)
    rows = [line.split() for line in data.decode('ascii').splitlines()]
    rows = [row for row in rows if len(row) == 6 and row[1] == '/usr']
    require(len(rows) == 1 and rows[0][0] == '/dev/nflasha15' and rows[0][2] == 'ext2', 'Unexpected /usr mount.')
    options = rows[0][3].split(',')
    return dict(line=' '.join(rows[0]), readonly='ro' in options and 'rw' not in options)


def file_state(factory, path, expected, evidence, index):
    limit = max([record['size'] for record in expected.values()]+[65536])+16
    status, raw = factory.read(path, maximum=min(limit, 32*1024*1024))
    if status == factory.missing:
        return dict(path=path, state='absent')
    require(status == (0, 0), 'Unable to inspect '+path+': '+repr(status))
    digest = sha(raw)
    state = next((label for label, r in expected.items() if len(raw) == r['size'] and digest == r['sha256']), 'foreign')
    save(evidence/f'file-{index:02d}.bin', raw)
    return dict(path=path, state=state, size=len(raw), sha256=digest)


def inspect(factory, bundle, evidence, probe):
    m = bundle.manifest
    status, raw = factory.read(JOURNAL, maximum=65536)
    journal = None
    if status == (0, 0):
        save(evidence/'journal.bin', raw)
        journal = journal_records(raw, m['bundle_sha256'])
    else:
        require(status == factory.missing, 'Unable to read installation journal.')
    files = []
    for i, path in enumerate(FINAL):
        expected = dict(installed=bundle.files[i])
        if i:
            expected['original'] = bundle.old[i-1]
        files.append(file_state(factory, path, expected, evidence, len(files)))
    for i, path in enumerate(BACKUPS):
        files.append(file_state(factory, path, dict(original=bundle.old[i]), evidence, len(files)))
    for i, path in enumerate(STAGE):
        files.append(file_state(factory, path, dict(staged=bundle.files[i]), evidence, len(files)))
    view_expected = dict(original=dict(size=bundle.view['after_bytes'], sha256=bundle.view['after_sha256']))
    if bundle.loader:
        view_expected['loader-installed'] = dict(size=bundle.view['after_bytes'], sha256=bundle.loader['after_sha256'])
    view = file_state(factory, VIEW, view_expected, evidence, len(files))
    mount = read_mounts(factory, probe, evidence)
    current = [f['state'] for f in files]
    last = journal['last'] if journal else None
    staged = (current == ['installed']*3+['original']*2+['absent']*3 and journal is not None and
              journal['integrity_error'] is None and last == dict(sequence=last['sequence'], phase=100,
              created=0, published=7, backed_up=3) and view['state'] in ('original', 'loader-installed') and mount['readonly'])
    clean = (journal is None and current == ['absent', 'original', 'original']+['absent']*5 and
             view['state'] == 'original' and mount['readonly'])
    rolled_back = (journal is not None and journal['integrity_error'] is None and last['phase'] in (90, 99) and
                   current[:3] == ['absent', 'original', 'original'] and current[5:] == ['absent']*3 and
                   all(s in ('absent', 'original') for s in current[3:5]) and view['state'] == 'original' and mount['readonly'])
    state = 'staged' if staged else 'clean-original' if clean else 'rollback-files-match' if rolled_back else 'review-required'
    result = dict(state=state, journal=journal, files=files, view=view, mount=mount,
                  loader_file_active=view['state'] == 'loader-installed', runtime_or_cold_boot_verified=False)
    save_json(evidence/'inspection.json', result)
    return result


def operate(camera, bundle, operation, evidence, probe):
    from camera.service import Factory, settings_ok
    factory = Factory(camera)
    require(factory.contents('/version.txt') == BUILD_ID and
            bytes(camera.readBackup(0x3e0005)) == b'ILCE-7M3'+bytes(8), 'Camera model/build mismatch.')
    before_dir = evidence/'before'; before_dir.mkdir(mode=0o700)
    before = inspect(factory, bundle, before_dir, probe)
    if operation == 'rollback-review':
        result = dict(operation=operation, review=before, device_mutated=False,
                      instruction='No journal or device file was overwritten. Loader deactivation and a separately reviewed rollback are required before recovery writes.')
        save_json(evidence/'result.json', result)
        return result
    if operation == 'verify':
        require(before['state'] in ('staged', 'clean-original', 'rollback-files-match'),
                'Partial/foreign installation state; use rollback-review. Evidence: '+str(before_dir))
        result = dict(operation=operation, verified=True, state=before['state'],
                      readonly_confirmed=True, loader_file_active=before['loader_file_active'],
                      hardware_validation='pending: inspect runtime and cold boot separately')
        save_json(evidence/'result.json', result)
        return result
    require(operation == 'stage', 'Unknown operation.')
    require(before['state'] == 'clean-original',
            'Staging requires original files and no journal; existing journal is never resumed or overwritten.')
    settings = bytes(camera.getBackupPresetData(True)); settings_ok(settings)
    save(evidence/'before-settings.bin', settings)
    luts = {key: bytes(camera.readBackup(key)) for key in range(0x30004, 0x30008)}
    require(all(len(raw) == 1280 for raw in luts.values()), 'Unexpected calibration table sizes.')
    save_json(evidence/'write-started.json', dict(bundle_sha256=bundle.manifest['bundle_sha256'],
              payload_sha256=sha(bundle.payload), loader_activated=False))
    raw = factory.run(bundle.payload, 'a7install.bin')
    save(evidence/'report.bin', raw)
    report = install_report(raw, bundle.manifest['bundle_sha256'])
    save_json(evidence/'report.json', report)
    after_dir = evidence/'after'; after_dir.mkdir(mode=0o700)
    after = inspect(factory, bundle, after_dir, probe)
    require(report['status'] == 0 and report['first_error'] == 0 and report['phase'] == 100 and
            report['created'] == 0 and report['published'] == 7 and report['backed_up'] == 3 and
            report['readonly_confirmed'] == 1 and after['state'] == 'staged' and not after['loader_file_active'],
            'Filesystem staging did not fully verify. Evidence retained; do not rerun blindly.')
    require(all(bytes(camera.readBackup(key)) == raw for key, raw in luts.items()), 'Calibration changed during filesystem staging.')
    result = dict(operation='stage', verified=True, readonly_confirmed=True, retained_locale_backups_verified=True,
                  loader_activated=False, all_four_luts_unchanged=True,
                  hardware_validation='pending: loader activation and cold-power/physical-menu validation are separate')
    save_json(evidence/'result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', nargs='?', choices=('verify', 'stage', 'rollback-review'), default='verify')
    parser.add_argument('--write-device', action='store_true', help='Required only for stage; never enables automatic rollback')
    parser.add_argument('--offline', action='store_true', help='Verify local bundle/proofs only; no USB or camera operation')
    parser.add_argument('--direct', action='store_true', help='Connect to an already enumerated Sony maintenance device')
    parser.add_argument('--bundle', type=Path, default=LAB/'native-install-bound')
    parser.add_argument('--module-proof', type=Path, default=LAB/'native-module/proof.json')
    parser.add_argument('--base', type=Path, default=LAB/'creative-icons-belt')
    parser.add_argument('--strings', type=Path, default=LAB/'native-fl-strings')
    args = parser.parse_args()
    require(args.operation != 'stage' or args.write_device, 'stage requires explicit --write-device.')
    require(not args.write_device or args.operation == 'stage', '--write-device is only meaningful with stage.')
    bundle = Bundle(args.bundle.resolve(), args.module_proof.resolve(), args.base.resolve(), args.strings.resolve())
    if args.offline:
        print(json.dumps(dict(local_proofs_verified=True, ready_for_staging=True,
                              bundle_sha256=bundle.manifest['bundle_sha256'], camera_contacted=False,
                              hardware_validation='pending'), indent=2))
        return 0
    evidence = args.bundle.resolve()/f'{args.operation}-{time.time_ns()}'
    evidence.mkdir(mode=0o700)
    save(evidence/'bound-manifest.json', bundle.manifest_path.read_bytes())
    probe = mount_payload(evidence/'probe')
    from camera import handoff, service
    previous = service.perform
    result = None
    def perform(camera, action):
        nonlocal result
        require(action == 'settings-snapshot', 'Unexpected transport action.')
        result = operate(camera, bundle, args.operation, evidence, probe)
    service.perform = perform
    try:
        if args.direct:
            import fcntl
            with (LAB/'.usb-transport.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                service.connect('settings-snapshot')
        else:
            handoff.run('settings-snapshot')
    finally:
        service.perform = previous
    require(result is not None, 'Transport returned without a result.')
    print('LIVE_NATIVE_FILESYSTEM_'+args.operation.upper().replace('-', '_')+' '+json.dumps(result, ensure_ascii=False), flush=True)
    print('EVIDENCE '+str(evidence), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
