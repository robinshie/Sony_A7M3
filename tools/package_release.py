#!/usr/bin/env python3
"""Package the accepted r15 halation readback without camera-private files."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = 'a44876fb9136b4fe31c9d82ad143bf87d9b10c3d05fc8b0ba77f0348a6c3324d'
KERNEL = 'dfc954c8792f04b01744ee0d3bbc9e80d23af2f8b0fd6e5220caeb56bfa2e44c'
def sha(data):
    return hashlib.sha256(data).hexdigest()

def validate_acceptance(path, module):
    proof = json.loads(path.read_text())
    if (sha(module) != EXPECTED or len(module) != 115120 or
            proof.get('accepted') is not True or proof.get('revision') != 'r15-halation' or
            proof.get('module') != {'sha256': EXPECTED, 'size': len(module)} or
            proof.get('kernel_sha256') != KERNEL or
            proof.get('kernel_matches_saved') is not True or
            proof.get('runtime_matches_saved') is not True):
        raise ValueError('Only the accepted r15 halation readback is permitted')
    if not proof.get('artifact_sha256') or not proof.get('source_sha256'):
        raise ValueError('Acceptance evidence and reader identity are required')
    for name, digest in proof['artifact_sha256'].items():
        target = (ROOT/name).resolve()
        if not target.is_relative_to(ROOT/'.lab') or sha(target.read_bytes()) != digest:
            raise ValueError('Acceptance artifact changed: '+name)
    for name, digest in proof['source_sha256'].items():
        target = (ROOT/name).resolve()
        if not target.is_relative_to(ROOT) or sha(target.read_bytes()) != digest:
            raise ValueError('Acceptance reader changed: '+name)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module', type=Path, required=True)
    parser.add_argument('--acceptance', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    module = args.module.read_bytes()
    validate_acceptance(args.acceptance, module)
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise ValueError('Commit intended sources before creating a release tied to HEAD')
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    files = {
        'a7fl.so': module,
        'README-中文.md': (
            '# Sony A7M3 v0.01 / r15 光晕升级版\n\n'
            'FL、FL2、FL3 各有独立五点曲线：黑位、暗部、中间调、亮部、白位。'
            '用户已确认三个风格曲线独立、保存及重启后保留。曲线的取景与 JPEG 视觉效果尚待独立验收。\n\n'
            '此附件提供含拍后颗粒／光晕内核的模块；更新需旧颗粒 r15 精确基线、既有加载器，并先生成安装光晕中英文菜单资源。'
            '不含原厂固件、个人设置、私有绑定包或通用初装器，不能用 Sony 官方更新器安装。'
            '本次实验机已经写入并验收光晕升级版，不要重复刷入。\n\n'
            '新增光晕（拍后）−9…+9，负值压暗高光周围、正值为暖色亮晕、0关闭；保留颗粒0–9。'
            '三个FL独立保存，沿用保存确认／取消／完成流程。−9／0／+9临时真机实拍已验证进入JPEG；'
            '持久版FL3菜单、拍摄回放与负值重启保留验收通过，内核处理1张、失败0张。'
            '已验证全画幅3:2 JPEG L（6000×4000）；光晕−9／+9分别约增加23／25秒，旧颗粒版强度9约9秒。'
            '两项叠加尚未实拍计时；均不作用于实时取景或RAW。锐度、锐度范围、清晰度仍只保存参数。\n\n'
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
            'feature_revision': 'r15-halation',
            'module': {'file': 'a7fl.so', 'size': len(module), 'sha256': EXPECTED},
            'kernel_sha256': KERNEL,
            'required_baseline': 'project grain r15 exact baseline and existing loader; generate/install halation locales using local original resources and camera-bound updater',
            'required_module_sha256': '33d103c891660cf9521a7661a31c114252070bd2c49c92f930079bc10c15c49d',
            'device_write_and_full_readback_verified': True,
            'user_verified': ['FL/FL2/FL3 independent curve settings', 'Save and power-cycle persistence', 'FL3 capture grain menu, shooting/playback and cold-boot persistence', 'FL3 halation menu, shooting/playback and negative-value cold-boot persistence'],
            'curve_visual_effects_hardware_verified': False,
            'capture_grain_installed': True, 'halation_installed': True,
            'grain_scope': {'format': 'full-frame 3:2 JPEG L 6000x4000', 'strength': [0, 9], 'hardware_tested_strength': 9, 'extra_seconds_approx': 9, 'timing_basis': 'previous accepted grain r15', 'live_view': False, 'raw': False},
            'halation_scope': {'format': 'full-frame 3:2 JPEG L 6000x4000', 'strength': [-9, 9], 'diagnostic_hardware_tested_strengths': [-9, 0, 9], 'resident_hardware_tested_strength': -9, 'extra_seconds_approx': {'-9': 23, '9': 25}, 'grain_combination_hardware_timing_verified': False, 'live_view': False, 'raw': False},
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
