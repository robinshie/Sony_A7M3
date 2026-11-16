"""Publish tool-only artifacts after all three platform jobs have succeeded."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile


def main():
    if os.environ.get('GITHUB_EVENT_NAME') != 'workflow_dispatch':
        raise SystemExit('Run through the manual GUI-tool publish workflow.')
    artifacts = Path(sys.argv[1])
    selected = []
    for job in ('windows-latest','macos-15','ubuntu-22.04'):
        folder = artifacts/('A7M3-Tool-'+job)
        candidates = list(folder.glob('Sony_A7M3-Tool-*-*.zip'))
        if len(candidates) != 1:
            raise ValueError('Expected one tested native tool per platform: '+job)
        selected.extend(candidates)
    selected.append(artifacts/'A7M3-Tool-ubuntu-22.04'/'Sony_A7M3-Tool.zip')
    repo = os.environ['GITHUB_REPOSITORY']
    with tempfile.TemporaryDirectory(prefix='tool-publish-') as tmp:
        out = Path(tmp)
        hashes = []
        for source in selected:
            checksum, name = source.with_suffix('.zip.sha256').read_text().strip().split('  ',1)
            actual = hashlib.sha256(source.read_bytes()).hexdigest()
            if name != source.name or checksum != actual:
                raise ValueError('Artifact checksum mismatch: '+source.name)
            with zipfile.ZipFile(source) as z:
                if z.testzip(): raise ValueError('Broken artifact ZIP')
            shutil.copyfile(source,out/source.name)
            hashes.append(f'{actual}  {source.name}\n')
        sums = out/'Sony_A7M3-Tool-SHA256SUMS.txt'
        sums.write_text(''.join(hashes),encoding='utf-8')
        assets = [str(out/p.name) for p in selected]+[str(sums)]
        subprocess.run(['gh','release','upload','v0.01',*assets,'--clobber','--repo',repo],check=True)
        body = subprocess.check_output(['gh','release','view','v0.01','--repo',repo,'--json','body','--jq','.body'],text=True)
        marker = '<!-- A7M3 GUI TOOL -->'
        body = body.split(marker,1)[0].rstrip()
        commit = os.environ['GITHUB_SHA']
        run = os.environ['GITHUB_RUN_ID']
        note = f'''\n\n{marker}
## 跨平台中文 GUI 工具

新增 Windows x64、macOS Apple Silicon、Linux x64 独立工具包（含 Python），以及三平台共用的源码运行包。解压全部文件后按包内 README 启动。

功能：12 份配方、16 参数编辑与另存、SD 卡复制及完整回读、完整功能 ZIP 校验、中文操作指南。**GUI 未接入固件刷写后端，不是原厂 4.04 首次安装器。** 复制配方需机身已有「从 SD 卡导入」入口。

[README](https://github.com/{repo}/blob/{commit}/tool/README.md) · [三平台构建和启动／复制／回读测试](https://github.com/{repo}/actions/runs/{run})

工具源码：`{commit}`。这里只追加电脑工具附件；上述固件附件、固件源码提交和 v0.01 标签保持原状。工具校验值见 `Sony_A7M3-Tool-SHA256SUMS.txt`。
'''
        notes = out/'notes.md'; notes.write_text(body+note,encoding='utf-8')
        subprocess.run(['gh','release','edit','v0.01','--repo',repo,'--notes-file',str(notes)],check=True)


if __name__ == '__main__': main()
