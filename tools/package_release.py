#!/usr/bin/env python3
"""Package the read-back, user-accepted r15 module without camera-private files."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = '33d103c891660cf9521a7661a31c114252070bd2c49c92f930079bc10c15c49d'
def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    module = args.module.read_bytes()
    if sha(module) != EXPECTED:
        raise ValueError('Only the accepted r15 readback is permitted')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    files = {
        'a7fl.so': module,
        'README-中文.md': (
            '# Sony A7M3 v0.01 / r15\n\n'
            'FL、FL2、FL3 各有独立五点曲线：黑位、暗部、中间调、亮部、白位。'
            '用户已确认三个风格曲线独立、保存及重启后保留。曲线的取景与 JPEG 视觉效果尚待独立验收。\n\n'
            '此附件提供含拍后颗粒内核的模块；更新需项目 r14 精确基线、既有加载器，并先生成安装 r15 中英文菜单资源。'
            '不含原厂固件、个人设置、私有绑定包或通用初装器，不能用 Sony 官方更新器安装。'
            '本次实验机已经写入并验收 r15，不要重复刷入。\n\n'
            '新增颗粒（拍后）0–9 档，三个 FL 独立保存。FL3 真机冷启动、拍摄回放与重启保留验收通过。'
            '已验证全画幅 3:2 JPEG L（6000×4000），强度 9 每张约增加 9 秒；不作用于实时取景或 RAW。'
            '光晕未接入，锐度、锐度范围、清晰度仍只保存参数。\n\n'
            '解压后运行 shasum -a 256 -c SHA256SUMS 核对。'
            '构建、依赖与流程见同目录流程说明；源码见 '
            f'https://github.com/robinshie/Sony_A7M3/tree/{commit} 。\n'
        ).encode(),
        'docs/release-workflow.md': (ROOT/'docs/release-workflow.md').read_bytes(),
        'docs/grain-research.md': (ROOT/'docs/grain-research.md').read_bytes(),
        'docs/fl3-film-controls.md': (ROOT/'docs/fl3-film-controls.md').read_bytes(),
        'docs/updater.md': (ROOT/'docs/updater.md').read_bytes(),
        'docs/ui.md': (ROOT/'docs/ui.md').read_bytes(),
        'release-manifest.json': (json.dumps({
            'release': 'v0.01', 'module_revision': 'r15', 'source_commit': commit,
            'module': {'file': 'a7fl.so', 'size': len(module), 'sha256': EXPECTED},
            'required_baseline': 'project r14 exact baseline and existing loader; generate/install r15 grain locales using local original resources and camera-bound updater',
            'device_write_and_full_readback_verified': True,
            'user_verified': ['FL/FL2/FL3 independent curve settings', 'Save and power-cycle persistence', 'FL3 capture grain menu, shooting/playback and cold-boot persistence'],
            'curve_visual_effects_hardware_verified': False,
            'capture_grain_installed': True, 'halation_installed': False,
            'grain_scope': {'format': 'full-frame 3:2 JPEG L 6000x4000', 'strength': [0, 9], 'hardware_tested_strength': 9, 'extra_seconds_approx': 9, 'live_view': False, 'raw': False},
            'locales_included': False, 'universal_installer': False,
        }, ensure_ascii=False, indent=2)+'\n').encode(),
    }
    files['SHA256SUMS'] = ''.join(f'{sha(data)}  {name}\n' for name,data in sorted(files.items())).encode()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo('Sony_A7M3-v0.01/'+name, (2026,11,15,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644 << 16
            z.writestr(info,data)
    with zipfile.ZipFile(args.out) as z:
        assert not z.testzip()
        for name,data in files.items():
            assert z.read('Sony_A7M3-v0.01/'+name) == data
    print(json.dumps({'archive':str(args.out),'sha256':sha(args.out.read_bytes()),'module_size':len(module),'source_commit':commit},indent=2))

if __name__ == '__main__':
    main()
