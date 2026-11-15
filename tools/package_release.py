#!/usr/bin/env python3
"""Package the accepted r16 vignette readback without camera-private files."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = '9fcaf13e5bcc5914d5721d797f16c3b059dc6f9b0cb99c94eda7632176306fe8'
KERNEL = '69213b30f04f6a9d97ae92cbc3d1b4e9da8c24a6192d84b1dc8435e468ca6277'
def sha(data):
    return hashlib.sha256(data).hexdigest()

def validate_acceptance(path, module):
    proof = json.loads(path.read_text())
    if (sha(module) != EXPECTED or len(module) != 120468 or
            proof.get('accepted') is not True or proof.get('revision') != 'r16-vignette' or
            proof.get('module_sha256') != EXPECTED or
            proof.get('installed_files', {}).get('16') != {'sha256': EXPECTED, 'size': len(module)} or
            proof.get('kernel_sha256') != KERNEL or
            proof.get('resident_state') != 'resident-ready' or proof.get('diagnostic') != 0 or
            proof.get('captures_completed_since_boot', 0) < 2 or proof.get('captures_failed_since_boot') != 0 or
            proof.get('kernel_matches_saved') is not True or
            proof.get('runtime_matches_saved') is not True):
        raise ValueError('Only the accepted r16 vignette readback is permitted')
    confirmation = proof.get('user_confirmation', {})
    if not all(confirmation.get(k) is True for k in
               ('cold_boot_menu_and_three_looks', 'vignette_negative_and_positive_jpeg_effect', 'plus9_survived_restart')):
        raise ValueError('Cold-boot menu, JPEG effects and saved-value acceptance are required')
    if not proof.get('artifact_sha256') or not proof.get('inspection_source_sha256'):
        raise ValueError('Acceptance evidence and reader identity are required')
    for name, digest in proof['artifact_sha256'].items():
        target = (ROOT/name).resolve()
        if not target.is_relative_to(ROOT/'.lab') or sha(target.read_bytes()) != digest:
            raise ValueError('Acceptance artifact changed: '+name)
    for name, digest in proof['inspection_source_sha256'].items():
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
            '# Sony A7M3 v0.01 / r16 正负暗角\n\n'
            'FL、FL2、FL3 各有独立五点曲线：黑位、暗部、中间调、亮部、白位。'
            '用户已确认三个风格曲线独立、保存及重启后保留。曲线的取景与 JPEG 视觉效果尚待独立验收。\n\n'
            '此附件提供含拍后颗粒／光晕／暗角内核的模块；更新需 r15 光晕升级版精确基线、既有加载器，并先生成安装暗角中英文菜单资源。'
            '不含原厂固件、个人设置、私有绑定包或通用初装器，不能用 Sony 官方更新器安装。'
            '本次实验机已经写入并验收 r16，不要重复刷入。\n\n'
            '新增暗角（拍后）−9…+9，负值压暗四角、正值提亮、0关闭，中心保持；与高光周围的光晕独立。'
            '三个FL独立保存，沿用保存确认／取消／完成流程。−9／0／+9同一内核实拍已验证进入JPEG；'
            '持久版菜单、正负效果与+9重启保留验收通过，内核处理2张、失败0张。'
            '同时修复已确认的上一代色表保留时启动失败、创意外观入口消失的问题。'
            'schema 5兼容读取旧配置，新增暗角默认0；旧版不识别schema 5，回退须匹配升级前设置备份。\n\n'
            '已验证全画幅3:2 JPEG L（6000×4000），三项均为拍后处理，不作用于实时取景或RAW。'
            '保留颗粒0–9和光晕−9…+9；既有光晕−9／+9约增加23／25秒，旧颗粒版强度9约9秒。'
            '组合效果尚未实拍计时；每张保存完成再拍下一张。锐度、锐度范围、清晰度仍只保存参数。\n\n'
            '解压后运行 shasum -a 256 -c SHA256SUMS 核对。'
            '构建、依赖与流程见同目录流程说明；源码见 '
            f'https://github.com/robinshie/Sony_A7M3/tree/{commit} 。\n'
        ).encode(),
        'docs/release-workflow.md': (ROOT/'docs/release-workflow.md').read_bytes(),
        'docs/grain-research.md': (ROOT/'docs/grain-research.md').read_bytes(),
        'docs/fl3-film-controls.md': (ROOT/'docs/fl3-film-controls.md').read_bytes(),
        'docs/vignette.md': (ROOT/'docs/vignette.md').read_bytes(),
        'docs/updater.md': (ROOT/'docs/updater.md').read_bytes(),
        'docs/ui.md': (ROOT/'docs/ui.md').read_bytes(),
        'release-manifest.json': (json.dumps({
            'release': 'v0.01', 'module_revision': 'r16', 'source_commit': commit,
            'feature_revision': 'r16-vignette', 'preference_schema': 5,
            'module': {'file': 'a7fl.so', 'size': len(module), 'sha256': EXPECTED},
            'kernel_sha256': KERNEL,
            'required_baseline': 'project r15-halation exact baseline and existing loader; generate/install vignette locales using local original resources and camera-bound updater',
            'required_module_sha256': 'a44876fb9136b4fe31c9d82ad143bf87d9b10c3d05fc8b0ba77f0348a6c3324d',
            'device_write_and_full_readback_verified': True,
            'user_verified': ['FL/FL2/FL3 independent curve settings', 'Save and power-cycle persistence', 'FL3 capture grain menu, shooting/playback and cold-boot persistence', 'FL3 halation menu, shooting/playback and negative-value cold-boot persistence', 'r16 menu and all three looks after cold boot', 'FL3 signed vignette JPEG effect and +9 power-cycle persistence'],
            'curve_visual_effects_hardware_verified': False,
            'capture_grain_installed': True, 'halation_installed': True, 'vignette_installed': True,
            'confirmed_history_boot_recovery': True,
            'grain_scope': {'format': 'full-frame 3:2 JPEG L 6000x4000', 'strength': [0, 9], 'hardware_tested_strength': 9, 'extra_seconds_approx': 9, 'timing_basis': 'previous accepted grain r15', 'live_view': False, 'raw': False},
            'halation_scope': {'format': 'full-frame 3:2 JPEG L 6000x4000', 'strength': [-9, 9], 'diagnostic_hardware_tested_strengths': [-9, 0, 9], 'resident_hardware_tested_strength': -9, 'extra_seconds_approx': {'-9': 23, '9': 25}, 'grain_combination_hardware_timing_verified': False, 'live_view': False, 'raw': False},
            'vignette_scope': {'format': 'full-frame 3:2 JPEG L 6000x4000', 'strength': [-9, 9], 'same_binary_diagnostic_hardware_tested_strengths': [-9, 0, 9], 'user_verified_resident_strengths': [-9, 9], 'negative': 'darken corners', 'positive': 'brighten corners', 'zero': 'off', 'center': 'unchanged', 'combined_effects_hardware_timing_verified': False, 'live_view': False, 'raw': False},
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
