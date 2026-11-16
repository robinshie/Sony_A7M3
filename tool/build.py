#!/usr/bin/env python3
"""Build source ZIP or a native, Python-bundled desktop tool on the current OS."""
import argparse
import hashlib
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile

TOOL = Path(__file__).resolve().parent
ROOT = TOOL.parent


def stage(dest):
    dest.mkdir(parents=True)
    for name in ('app.py', 'backend.py', 'README.md', 'Start-Windows.cmd', 'Start-macOS.command', 'start-linux.sh'):
        shutil.copy2(TOOL/name, dest/name)
    shutil.copytree(TOOL/'web', dest/'web')
    shutil.copy2(TOOL/'screenshot.jpg', dest/'screenshot.jpg')
    (dest/'lib').mkdir()
    for name in ('custom_look_recipes.py', 'look_recipes.py'):
        shutil.copy2(ROOT/'tools'/name, dest/'lib'/name)
    for group in ('defaults', 'film-collection'):
        (dest/'recipes'/group).mkdir(parents=True)
        for source in sorted((ROOT/'recipes'/group).glob('*.a7look')):
            shutil.copy2(source, dest/'recipes'/group/source.name)
    shutil.copy2(ROOT/'LICENSE', dest/'LICENSE')
    for name in ('Start-macOS.command', 'start-linux.sh'):
        (dest/name).chmod(0o755)


def zip_tree(folder, out):
    files = sorted(p for p in folder.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
    sums = ''.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(folder).as_posix()}\n' for p in files)
    (folder/'SHA256SUMS').write_text(sums, encoding='utf-8')
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for p in sorted(folder.rglob('*')):
            if p.is_file():
                info = zipfile.ZipInfo(folder.name+'/'+p.relative_to(folder).as_posix(), (2026,11,16,0,0,0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = (0o100755 if p.stat().st_mode & 0o111 else 0o100644) << 16
                archive.writestr(info, p.read_bytes())
    with zipfile.ZipFile(out) as archive:
        if archive.testzip():
            raise ValueError('ZIP readback failed')
    checksum = hashlib.sha256(out.read_bytes()).hexdigest()
    out.with_suffix('.zip.sha256').write_text(f'{checksum}  {out.name}\n', encoding='utf-8')
    print(str(out) + '\nSHA256 ' + checksum)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native', action='store_true', help='Requires PyInstaller; builds only the current OS/architecture')
    p.add_argument('--out', type=Path, default=ROOT/'dist')
    args = p.parse_args()
    with tempfile.TemporaryDirectory(prefix='a7m3-tool-') as temp:
        work = Path(temp)
        source = work/'Sony_A7M3-Tool'
        stage(source)
        if not args.native:
            zip_tree(source, args.out/'Sony_A7M3-Tool.zip')
            return
        subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
                        '--name', 'A7M3-Tool', '--distpath', str(work/'native'),
                        '--workpath', str(work/'build'), '--specpath', str(work),
                        '--paths', str(source/'lib'), '--add-data', str(source/'web')+':web',
                        '--add-data', str(source/'recipes')+':recipes', str(source/'app.py')], check=True)
        native = work/'native'/'A7M3-Tool'
        shutil.copy2(TOOL/'README.md', native/'README.md')
        shutil.copy2(TOOL/'screenshot.jpg', native/'screenshot.jpg')
        shutil.copy2(ROOT/'LICENSE', native/'LICENSE')
        if sys.platform == 'darwin':
            launcher = native/'Start-macOS.command'
            launcher.write_text('#!/bin/sh\ncd "$(dirname "$0")" || exit 1\nexec ./A7M3-Tool\n', encoding='utf-8')
            launcher.chmod(0o755)
        label = {'darwin':'macOS','win32':'Windows'}.get(sys.platform, 'Linux')
        zip_tree(native, args.out/f'Sony_A7M3-Tool-{label}-{platform.machine()}.zip')


if __name__ == '__main__':
    main()
