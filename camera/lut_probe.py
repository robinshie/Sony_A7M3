"""Journaled, single-property LUT diagnostic and recovery. Never reports FL ready."""
import io
import json
import os
from pathlib import Path
import time

from local import BUILD_ID, LAB, ROOT, require, sha
from research.lut_probe import IDS, TARGET, candidate


def durable(path, data):
    with path.open('xb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    require(path.read_bytes() == data, 'Local recovery artifact failed readback')


class Bundle:
    kind = 'diagnostic'
    prefix = 'LIVE_LUT_PROBE_'

    def build_candidate(self, original):
        return candidate(original)

    def __init__(self, path, apply=False):
        self.path = path
        m = json.loads((path/'manifest.json').read_text())
        require(m['schema'] == 1 and m['property'] == TARGET and m['build'] == BUILD_ID.decode() and
                m.get('kind', 'diagnostic') == self.kind,
                'Wrong LUT experiment target')
        self.original = {key: (path/f'{key:08x}.bin').read_bytes() for key in IDS}
        self.changed = (path/'candidate.bin').read_bytes()
        for name, digest in m['files'].items():
            require(Path(name).name == name and sha((path/name).read_bytes()) == digest,
                    'Recovery artifact changed: '+name)
        require(all(len(v) == 1280 for v in self.original.values()) and
                self.changed == self.build_candidate(self.original[TARGET]), 'Unexpected LUT candidate')
        if apply:
            for source, digest in m['source_sha256'].items():
                require(sha((ROOT/source).read_bytes()) == digest, 'Probe source changed: '+source)
            p = path/'qemu/proof.json'
            require(sha(p.read_bytes()) == m['qemu_proof_sha256'], 'Native proof changed')
            proof = json.loads(p.read_text())
            for source, digest in proof['source_sha256'].items():
                require(sha((ROOT/source).read_bytes()) == digest, 'Native source changed: '+source)
            for name, key in (('lut3d.elf', 'elf_sha256'), ('qemu.log', 'qemu_log_sha256'),
                              ('table_inputs.bin', 'table_input_sha256')):
                require(sha((p.parent/name).read_bytes()) == proof[key], 'Native artifact changed')
            require(proof['private_backup']['settings_sha256'] == m['files']['candidate-settings.bin'] and
                    b'QEMU_NATIVE_3DLUT_PASSED' in (p.parent/'qemu.log').read_bytes(),
                    'Candidate was not executed by the native test')

    def snapshot(self, camera, expected=None):
        from pmca.backup import BackupFile
        raw = bytes(camera.getBackupPresetData(True))
        bk = BackupFile(io.BytesIO(raw))
        require(bk.revision == 4 and bk.size == len(raw), 'Invalid live backup')
        values = {}
        for key in IDS:
            prop = bk.getProperty(key)
            value = bytes(camera.readBackup(key))
            require(prop.attr == 8 and len(value) == 1280 and value == prop.data,
                    f'Live LUT disagreement: {key:#x}')
            want = expected if key == TARGET and expected is not None else self.original[key]
            require(value == want, f'Live LUT preimage mismatch: {key:#x}; no blind overwrite')
            values[key] = value
        return raw

    def event(self, directory, name, **values):
        record = {'time_ns': time.time_ns(), 'event': name, **values}
        durable(directory/f"{record['time_ns']}-{name}.json",
                (json.dumps(record, indent=2)+'\n').encode())

    def operate(self, camera, operation):
        require(operation in ('apply', 'restore', 'status'), 'Unknown LUT action')
        current = bytes(camera.readBackup(TARGET))
        recoverable = len(current) == len(self.changed) and all(
            got in (old, new) for got, old, new in zip(current, self.original[TARGET], self.changed))
        require(current in (self.original[TARGET], self.changed) or
                (operation == 'restore' and recoverable),
                'Unknown target state; refusing blind overwrite')
        before = self.snapshot(camera, current)
        state = ('original' if current == self.original[TARGET] else
                 'diagnostic' if current == self.changed else 'partial-diagnostic')
        if operation == 'status':
            print(self.prefix+'STATE', state, self.kind, flush=True)
            return
        directory = self.path/f'{operation}-{time.time_ns()}'
        directory.mkdir(mode=0o700)
        durable(directory/'before-settings.bin', before)
        self.event(directory, 'prepared', state=state, property=TARGET,
                   original_sha256=sha(self.original[TARGET]), candidate_sha256=sha(self.changed))
        target = self.changed if operation == 'apply' else self.original[TARGET]
        if current == target:
            self.event(directory, 'already-matched')
            print(self.prefix+'ALREADY', state, flush=True)
            return
        # The journal exists before entering the write. An exception may follow
        # a partially accepted USB command, so a failed apply restores the
        # original even if the call itself did not acknowledge success.
        self.event(directory, 'write-started', operation=operation)
        try:
            camera.writeBackup(TARGET, target)
            after = self.snapshot(camera, target)
            durable(directory/'after-settings.bin', after)
        except BaseException as failure:
            self.event(directory, 'write-or-readback-failed', error=str(failure))
            if operation == 'apply':
                try:
                    camera.writeBackup(TARGET, self.original[TARGET])
                    restored = self.snapshot(camera, self.original[TARGET])
                    durable(directory/'recovered-settings.bin', restored)
                    self.event(directory, 'automatic-restore-verified')
                    print(self.prefix+'AUTO_RESTORED', flush=True)
                except BaseException as recovery:
                    self.event(directory, 'restore-required', error=str(recovery))
                    print('LUT_RESTORE_REQUIRED', self.path, flush=True)
            raise
        self.event(directory, 'readback-verified', operation=operation)
        print(self.prefix+operation.upper()+'_VERIFIED', directory, flush=True)
        changed = sum(a != b for a, b in zip(self.original[TARGET], self.changed))
        print(f'{changed}_TABLE_BYTES; NO_SAVE_COMMAND; PERSISTENCE_UNKNOWN; {self.kind}', flush=True)


def configured(apply=False):
    value = os.environ.get('A7M3_LUT_EXPERIMENT')
    require(bool(value), 'Set A7M3_LUT_EXPERIMENT to the prepared private bundle')
    return Bundle(Path(value).expanduser().resolve(), apply=apply)


def perform(camera, operation):
    configured(apply=operation == 'apply').operate(camera, operation)
