"""Validate or explicitly activate the attested native-menu loader.

Default: read-only preflight. Activation always runs a fresh native preflight in
that same maintenance connection. Writes require --write-device; recovery and
post-boot deactivation are distinct operations. Existing device/host journals are
never overwritten, deleted, resumed, or automatically recovered. --offline only
validates local build proofs and does not import USB libraries.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import time

from local import BUILD_ID, LAB, ROOT, file_sha, require, sha
from camera.native_install import Bundle as InstallBundle, pin_sources

MODES = ('preflight', 'activate', 'recover', 'deactivate', 'deactivate-recover')
VIEW = '/usr/lib/viewUnified2.so'
REPORT = 'a7activate.bin'
JOURNALS = {
    'activate': '/setting/A7FL.ACTIVATE',
    'recover': '/setting/A7FL.ACTIVATE.RECOVER',
    'deactivate': '/setting/A7FL.DEACTIVATE',
    'deactivate-recover': '/setting/A7FL.DEACTIVATE.RECOVER',
}
PATCHES = ((0x5b9a7c, 44), (0x5b9b1c, 80), (0x20d068, 4), (0x188aec, 4))
SETTING_PATCHES = ((0x5b9a7c, 44), (0x5b9b1c, 80), (0x20d068, 4), (0x21464a, 4))
SETTING_JOURNALS = {
    'activate': '/setting/A7FL.RETARGET',
    'recover': '/setting/A7FL.RETARGET.RECOVER',
    'deactivate': '/setting/A7FL.RETARGET.UNDO',
    'deactivate-recover': '/setting/A7FL.RETARGET.UNDO.RECOVER',
}
PHASES = {10, 20, 21, 22, 30, 40, 41, 42, 43, 44, 45, 46, 47, 90, 99, 100}


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def save(path, raw):
    with path.open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def save_json(path, value):
    save(path, (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode())


def activation_report(raw, binding):
    require(len(raw) == 80, 'Unexpected activation report length.')
    values = struct.unpack('<8I4i32s', raw)
    keys = ('magic', 'version', 'phase', 'pid', 'view_base', 'other_mappings',
            'cow_mask', 'written_mask', 'status', 'first_error', 'rollback_ok', 'readonly_confirmed')
    report = dict(zip(keys, values[:12]))
    report['bundle_sha256'] = values[12].hex()
    require(report['magic'] == 0x41374e41 and report['version'] == 1 and
            report['bundle_sha256'] == binding, 'Foreign activation report.')
    require(not (report['cow_mask'] & ~7 or report['written_mask'] & ~15), 'Invalid activation report masks.')
    return report


def journal_records(raw, binding):
    """Parse valid prefix for review only; never authorize resume from a journal."""
    records, error = [], None
    for offset in range(0, len(raw)//84*84, 84):
        record = raw[offset:offset+84]
        magic, seq, phase, cow, written = struct.unpack_from('<5I', record)
        if (magic != 0x41374641 or seq != len(records)+1 or phase not in PHASES or
                cow & ~7 or written & ~15 or record[20:52].hex() != binding or
                hashlib.sha256(record[:52]).digest() != record[52:]):
            error = 'Invalid or foreign record at byte '+str(offset)
            break
        records.append(dict(sequence=seq, phase=phase, cow_mask=cow, written_mask=written))
    if error is None and len(raw) % 84:
        error = 'Torn trailing record'
    if error is None and not records:
        error = 'Empty journal'
    return dict(records=records, last=records[-1] if records else None,
                integrity_error=error, bytes=len(raw), sha256=sha(raw))


class Bundle:
    def __init__(self, directory, stage, module_proof, base, strings, setting=False):
        self.directory = directory
        self.patches = SETTING_PATCHES if setting else PATCHES
        self.journals = SETTING_JOURNALS if setting else JOURNALS
        self.manifest_path = directory/'manifest.json'
        self.manifest = json.loads(self.manifest_path.read_text())
        m = self.manifest
        pin_sources(m)
        require(m.get('profile', 'global-menu') == ('setting-menu' if setting else 'global-menu'), 'Activation layout/profile mismatch.')
        proof_path = directory/'proof.json'
        proof = json.loads(proof_path.read_text())
        require(proof['manifest_sha256'] == file_sha(self.manifest_path), 'Activation test manifest is stale.')
        pin_sources(proof)
        require(proof['payloads'] == m['payloads'], 'Activation payload proof differs from manifest.')
        log = (directory/'qemu.log').read_bytes()
        require(sha(log) == proof['qemu_log_sha256'] and b'NMA_ALL_PASS' in log and
                b'NMA_LINUX_ARM_DONE' in log, 'Missing completed ARM/Linux activation test.')
        installation = InstallBundle(stage, module_proof, base, strings)
        require(m['files'] == installation.files, 'Activation/staging file hashes differ.')
        require(installation.loader is not None, 'Original loader proof is missing.')
        loader_dir = LAB/('native-setting-loader' if setting else 'native-menu-boot-loader')
        loader_proof = json.loads((loader_dir/'proof.json').read_text())
        pin_sources(loader_proof)
        require(m['before_sha256'] == (installation.loader['after_sha256'] if setting else installation.view['after_sha256']) and
                m['before_sha256'] == loader_proof['before_sha256'] and
                m['after_sha256'] == loader_proof['after_sha256'] and
                m.get('loader_proof_sha256', file_sha(loader_dir/'proof.json')) == file_sha(loader_dir/'proof.json'),
                'Activation view hashes differ from loader proof.')
        loader_log = (loader_dir/'qemu.log').read_bytes()
        marker = b'NATIVE_SETTING_LOADER_PASSED' if setting else b'NATIVE_MENU_BOOT_LOADER_PASSED'
        require(sha(loader_log) == loader_proof['qemu_log_sha256'] and marker in loader_log and b'FAIL ' not in loader_log, 'Loader test log differs.')
        if setting:
            lifecycle = loader_proof['lifecycle']
            pin_sources(lifecycle)
            lifecycle_log = (loader_dir/'lifecycle.log').read_bytes()
            require(sha(lifecycle_log) == lifecycle['qemu_log_sha256'] and b'NATIVE_SETTING_LIFECYCLE_PASSED' in lifecycle_log and
                    b'FAIL ' not in lifecycle_log, 'SettingMenu lifecycle test is incomplete.')
        self.old = ((LAB/'native-menu-boot-loader' if setting else base)/'viewUnified2.so').read_bytes()
        self.new = (loader_dir/'viewUnified2.so').read_bytes()
        require(len(self.old) == len(self.new) == 10854816 and sha(self.old) == m['before_sha256'] and
                sha(self.new) == m['after_sha256'], 'Bound view images changed.')
        require(tuple((p['offset'], p['size']) for p in m['patches']) == self.patches, 'Unexpected activation ranges.')
        blob = struct.pack('<II', 1, len(self.old))+bytes.fromhex(sha(self.old))+bytes.fromhex(sha(self.new))
        for record in m['files']:
            blob += struct.pack('<I', record['size'])+bytes.fromhex(record['sha256'])
        comparison = bytearray(self.old)
        for offset, size in self.patches:
            old, new = self.old[offset:offset+size], self.new[offset:offset+size]
            blob += struct.pack('<II', offset, size)+old.ljust(80, b'\0')+new.ljust(80, b'\0')
            comparison[offset:offset+size] = new
        require(comparison == self.new, 'New view changes bytes outside the four reviewed ranges.')
        for offset in ((0x214000, 0x20d000, 0x5b9000) if setting else (0x188000, 0x20d000, 0x5b9000)):
            blob += self.old[offset:offset+4096]
        require(len(blob) == 13140 and blob == (directory/'bundle.bin').read_bytes() and
                hashlib.sha256(b'A7M3-4.04-cow-activate-v1\0'+blob).hexdigest() == m['bundle_sha256'],
                'Activation bundle binding mismatch.')
        require(set(m['payloads']) == set(MODES), 'Unexpected activation helper set.')
        self.payloads = {}
        for mode in MODES:
            raw = (directory/(mode+'.so')).read_bytes()
            record = m['payloads'][mode]
            require(len(raw) == record['size'] and 52 < len(raw) <= 65536 and sha(raw) == record['sha256'] and
                    raw[:7] == b'\x7fELF\x01\x01\x01' and raw[16:20] == b'\x03\0(\0',
                    'Invalid bound ARM helper: '+mode)
            self.payloads[mode] = raw
        self.proof_path = proof_path

    def known_view(self, raw):
        if len(raw) != len(self.old):
            return 'foreign'
        digest = sha(raw)
        if digest == self.manifest['before_sha256']:
            return 'old'
        if digest == self.manifest['after_sha256']:
            return 'new'
        normalized = bytearray(raw)
        for offset, size in self.patches:
            for at in range(offset, offset+size):
                if raw[at] not in (self.old[at], self.new[at]):
                    return 'foreign'
                normalized[at] = self.old[at]
        return 'known-mixed' if sha(normalized) == self.manifest['before_sha256'] else 'foreign'


def read_journals(factory, bundle, evidence):
    result = {}
    for mode, path in bundle.journals.items():
        status, raw = factory.read(path, maximum=65536)
        if status == factory.missing:
            result[mode] = None
        else:
            require(status == (0, 0), 'Unable to read '+path+': '+repr(status))
            save(evidence/(mode+'-journal.bin'), raw)
            result[mode] = journal_records(raw, bundle.manifest['bundle_sha256'])
    save_json(evidence/'journals.json', result)
    return result


def read_view(factory, bundle, evidence):
    raw = factory.contents(VIEW, maximum=len(bundle.old)+16)
    save(evidence/'viewUnified2.so', raw)
    state = dict(size=len(raw), sha256=sha(raw), state=bundle.known_view(raw))
    save_json(evidence/'view.json', state)
    return state


def report_success(report, writing=False):
    return (report['status'] == 0 and report['phase'] == (100 if writing else 3) and
            report['pid'] > 1 and report['view_base'] > 0 and not report['view_base'] & 4095 and
            report['other_mappings'] == 0 and report['cow_mask'] == (7 if writing else 0) and
            report['written_mask'] == (15 if writing else 0) and report['readonly_confirmed'] == 1)


def native_run(factory, bundle, mode, evidence):
    raw = factory.run(bundle.payloads[mode], REPORT)
    save(evidence/(mode+'-report.bin'), raw)
    report = activation_report(raw, bundle.manifest['bundle_sha256'])
    save_json(evidence/(mode+'-report.json'), report)
    return report


def operate(camera, bundle, operation, evidence, write_device=False):
    from camera.service import Factory
    require(operation in MODES, 'Unknown activation operation.')
    require(operation == 'preflight' or write_device, 'Writing requires explicit --write-device.')
    factory = Factory(camera)
    require(factory.contents('/version.txt') == BUILD_ID and
            bytes(camera.readBackup(0x3e0005)) == b'ILCE-7M3'+bytes(8), 'Camera model/build mismatch.')
    save_json(evidence/'device.json', dict(model='ILCE-7M3', build=BUILD_ID.decode('ascii')))
    before_dir = evidence/'before'; before_dir.mkdir(mode=0o700)
    before_journals = read_journals(factory, bundle, before_dir)
    if operation != 'preflight':
        require(before_journals[operation] is None,
                'The selected transaction journal already exists; preserve/review it instead of resuming or overwriting.')
    preflight = None
    if operation in ('preflight', 'activate'):
        preflight = native_run(factory, bundle, 'preflight', before_dir)
    before_view = read_view(factory, bundle, before_dir)
    if preflight is not None:
        require(report_success(preflight) and before_view['state'] == 'old',
                'Read-only native preflight failed; no activation was attempted. Evidence: '+str(before_dir))
    if operation == 'preflight':
        result = dict(operation=operation, verified=True, readonly_confirmed=True,
                      activation_eligible=before_journals['activate'] is None,
                      native_report=preflight, view=before_view, device_firmware_written=False,
                      hardware_validation='Loader activation and cold-boot physical-menu validation remain separate.')
        save_json(evidence/'result.json', result)
        return result
    require(before_view['state'] == ('new' if operation == 'deactivate' else 'old')
            if operation in ('activate', 'deactivate') else before_view['state'] in ('old', 'new', 'known-mixed'),
            'View file state is incompatible with the requested operation.')
    intent = dict(operation=operation, bundle_sha256=bundle.manifest['bundle_sha256'],
                  payload_sha256=sha(bundle.payloads[operation]), before_view=before_view,
                  same_session_preflight=preflight, process_id=os.getpid(), started_ns=time.time_ns(),
                  automatically_resume=False)
    save_json(evidence/'write-started.json', intent)
    report = native_run(factory, bundle, operation, evidence)
    after_dir = evidence/'after'; after_dir.mkdir(mode=0o700)
    after_view = read_view(factory, bundle, after_dir)
    after_journals = read_journals(factory, bundle, after_dir)
    journal = after_journals[operation]
    expected = 'new' if operation == 'activate' else 'old'
    verified = (report_success(report, writing=True) and after_view['state'] == expected and
                journal is not None and journal['integrity_error'] is None and
                journal['last']['phase'] == 100 and journal['last']['cow_mask'] == 7 and
                journal['last']['written_mask'] == 15)
    if preflight is not None:
        verified = verified and all(report[key] == preflight[key] for key in ('pid', 'view_base', 'bundle_sha256'))
    result = dict(operation=operation, verified=verified, readonly_confirmed=report['readonly_confirmed'] == 1,
                  native_report=report, view=after_view, journal=journal,
                  cold_boot_required=True, module_and_locales_retained=True,
                  hardware_validation='Current instructions remain unchanged; verify next cold boot and physical menu separately.')
    save_json(evidence/'result.json', result)
    require(verified, 'Operation did not fully verify. Evidence retained; no automatic recovery or retry. '+str(evidence))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', nargs='?', choices=MODES, default='preflight')
    parser.add_argument('--write-device', action='store_true', help='Required for each non-preflight operation')
    parser.add_argument('--offline', action='store_true', help='Validate local proofs only; do not import USB libraries')
    parser.add_argument('--direct', action='store_true', help='Use already enumerated maintenance USB; otherwise UTM handoff')
    parser.add_argument('--setting-menu', action='store_true', help='Retarget the first deployed loader to the native paged SettingMenu; separate journals and proofs')
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--stage', type=Path, default=LAB/'native-install-bound')
    parser.add_argument('--module-proof', type=Path, default=LAB/'native-module/proof.json')
    parser.add_argument('--base', type=Path, default=LAB/'creative-icons-belt')
    parser.add_argument('--strings', type=Path, default=LAB/'native-fl-strings')
    args = parser.parse_args()
    if args.bundle is None:args.bundle = LAB/('native-setting-activate' if args.setting_menu else 'native-menu-activate')
    require(args.operation == 'preflight' or args.write_device, args.operation+' requires explicit --write-device.')
    require(not args.write_device or args.operation != 'preflight', '--write-device is not meaningful for preflight.')
    bundle = Bundle(*(getattr(args, name).resolve() for name in ('bundle', 'stage', 'module_proof', 'base', 'strings')), setting=args.setting_menu)
    if args.offline:
        print(json.dumps(dict(local_proofs_verified=True, camera_contacted=False,
                              bundle_sha256=bundle.manifest['bundle_sha256'], operation=args.operation), indent=2))
        return 0
    evidence = bundle.directory/f'{args.operation}-{time.time_ns()}'
    evidence.mkdir(mode=0o700); sync_directory(evidence.parent)
    save(evidence/'bound-manifest.json', bundle.manifest_path.read_bytes())
    save(evidence/'bound-proof.json', bundle.proof_path.read_bytes())
    from camera import handoff, service
    previous, result = service.perform, None
    def perform(camera, action):
        nonlocal result
        require(action == 'settings-snapshot', 'Unexpected transport action.')
        result = operate(camera, bundle, args.operation, evidence, args.write_device)
    service.perform = perform
    try:
        if args.direct:
            import fcntl
            with (LAB/'.usb-transport.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                service.connect('settings-snapshot')
        else:
            handoff.run('settings-snapshot')
        require(result is not None, 'Transport returned without a result.')
    except Exception as exc:
        save_json(evidence/'error.json', dict(error=type(exc).__name__, message=str(exc),
                  write_intent_created=(evidence/'write-started.json').exists(), automatic_retry=False,
                  instruction='Preserve evidence. Inspect state before a separate explicitly requested recovery.'))
        raise
    finally:
        service.perform = previous
        print('EVIDENCE '+str(evidence), flush=True)
    print('LIVE_NATIVE_ACTIVATION_'+args.operation.upper().replace('-', '_')+' '+json.dumps(result, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
