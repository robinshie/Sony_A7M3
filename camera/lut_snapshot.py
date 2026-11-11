"""Read known native LUT properties and cross-check a complete BK4 snapshot."""
import io
import json
import os
import time

from pmca.backup import BackupFile
from local import LAB, require, sha

IDS = (0x30004, 0x30005, 0x30006, 0x30007)


def perform(camera):
    raw = camera.getBackupPresetData(True)
    backup = BackupFile(io.BytesIO(raw))
    require(backup.revision == 4 and backup.size == len(raw),
            'LUT 检查需要完整、校验通过的 BK4 快照。')
    records = []
    values = []
    for key in IDS:
        prop = backup.getProperty(key)
        require(len(prop.data) == 1280, f'LUT 属性 {key:#x} 长度不符。')
        direct = bytes(camera.readBackup(key))
        require(direct == prop.data, f'LUT 属性 {key:#x} 的直接读取与完整快照不一致。')
        values.append(direct)
        records.append({'id': hex(key), 'bytes': len(direct), 'attributes': prop.attr,
                        'sha256': sha(direct), 'direct_read_matches_snapshot': True})
    directory = LAB / 'lut-snapshots' / str(time.time_ns())
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    artifacts = {'settings.bin': raw}
    artifacts.update({f'{key:08x}.bin': value for key, value in zip(IDS, values)})
    report = {'settings_sha256': sha(raw), 'properties': records,
              'camera_write_performed': False, 'pixel_effect_verified': False}
    artifacts['report.json'] = (json.dumps(report, indent=2)+'\n').encode()
    for name, data in artifacts.items():
        with (directory/name).open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        require((directory/name).read_bytes() == data, '本地 LUT 快照写后检查失败。')
    print(f'LIVE_LUT_SNAPSHOT_VERIFIED {directory} properties=4 bytes=1280 each', flush=True)
    print('READ_ONLY_NATIVE_LUT_DATA; NO_PIXEL_OR_FLASH_VALIDATION', flush=True)
