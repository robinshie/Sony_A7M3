#!/usr/bin/env python3
"""Build stock-to-current deltas and rehearse on a local image; never use USB.

Outputs are deliberately not accepted by the camera update CLIs. In-place
changes below are ONLY for an offline filesystem copy, not a live write recipe.
"""
import argparse
import base64
import json
import mmap
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]
from local import BACKUP, PREFIX, STOCK_SHA, TOTAL, file_sha
from ext2_patch import Ext2
from native_install_plan import quoted, required_blocks
from package_custom_release import validate_acceptance
from stock_install_bundle import KIND, PINS, MODULE_SHA, sha, make_delta, apply_delta, read_bundle

DEBUGFS = shutil.which('debugfs') or '/opt/homebrew/opt/e2fsprogs/sbin/debugfs'
FSCK = shutil.which('e2fsck') or '/opt/homebrew/opt/e2fsprogs/sbin/e2fsck'
VIEW = '/lib/viewUnified2.so'
LOCALES = list(PINS)[3:]


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode()


def read_files(image, paths):
    with image.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        fs = Ext2(data)
        return {p: fs.contents(fs.find(p)) for p in paths}


def stock_input(path):
    if not stat.S_ISREG(path.stat().st_mode) or path.stat().st_size != TOTAL:
        raise ValueError('Expected a regular 300 MiB backup file, never a device')
    if file_sha(path, PREFIX) != STOCK_SHA:
        raise ValueError('Not the exact locally verified stock 4.04 filesystem')


def inventory(image):
    """Hash every regular file and symlink, also retaining ownership and mode."""
    result = {}
    with image.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
        fs = Ext2(data)
        def walk(number, path, ancestors):
            if number in ancestors:
                raise ValueError('Directory cycle')
            inode = fs.inode(number)
            mode = fs.u16(inode)
            size = fs.u32(inode+4)
            kind = mode & 0xf000
            if kind == 0x4000:
                contents = fs.contents(inode)
                at = 0
                while at < len(contents):
                    child, length, count, _ = struct.unpack_from('<IHBB', contents, at)
                    if length < 8 or length % 4 or at+length > len(contents) or count > length-8:
                        raise ValueError('Invalid ext2 directory')
                    name = contents[at+8:at+8+count].decode('utf-8')
                    if child and name not in ('.', '..'):
                        walk(child, path+'/'+name, ancestors | {number})
                    at += length
            else:
                raw = (bytes(data[inode+40:inode+40+size]) if kind == 0xa000 and size <= 60
                       else fs.contents(inode))
                result[path] = dict(size=size, sha256=sha(raw), mode=mode,
                                    uid=fs.u16(inode+2), gid=fs.u16(inode+24))
        walk(2, '', set())
        dimensions = dict(block_size=fs.bs, filesystem_bytes=fs.blocks*fs.bs,
                          free_bytes=fs.u32(1036)*fs.bs, free_inodes=fs.u32(1040))
        tail = sha(data[fs.blocks*fs.bs:])
    return result, dimensions, tail


def build(stock, out):
    stock_input(stock)
    old = read_files(stock, PINS)
    module_path = ROOT/'.lab/native-module-custom-candidate/liba7-fl-module.so'
    module = module_path.read_bytes()
    validate_acceptance(ROOT/'.lab/custom-look-incident/1794824744407403000/live-list-acceptance.json', module)
    new = read_files(ROOT/'.lab/creative-icons-belt/a7m3-retro-wardrobe.img', PINS)
    new[VIEW] = (ROOT/'.lab/native-setting-loader/viewUnified2.so').read_bytes()
    for p in LOCALES:
        new[p] = (ROOT/'.lab/native-fl-custom-strings'/Path(p).name).read_bytes()
    entries = {'a7fl.so': module}
    records = []
    for i, (p, pins) in enumerate(PINS.items()):
        if (sha(old[p]), sha(new[p])) != pins:
            raise ValueError('Unknown input or target: '+p)
        delta = make_delta(old[p], new[p])
        if apply_delta(old[p], delta) != new[p] or apply_delta(new[p], delta, reverse=True) != old[p]:
            raise ValueError('Bidirectional delta failed: '+p)
        name = f'deltas/{i}.json'
        entries[name] = json_bytes(delta)
        pages = sorted({at//4096*4096 for row in delta['changes']
                        for at in range(row['offset'], row['offset']+len(base64.b64decode(row['after'])))})
        records.append(dict(path=p, delta=name, before=delta['before'], after=delta['after'],
                            changed_pages_4096=pages))
    manifest = dict(kind=KIND, model='ILCE-7M3', firmware='4.04', flash_ready=False,
                    device_install_verified=False, files=records,
                    module=dict(path='/lib/a7fl.so', size=len(module), sha256=MODULE_SHA),
                    sha256={n: sha(v) for n,v in entries.items()},
                    settings_policy='No settings, calibration, serial, LUT backup or personal banks in this bundle',
                    limitations=['Offline image rehearsal only', 'Live stock activation not implemented or verified',
                                 'Stock cold boot and Windows USB transport not verified'])
    entries['manifest.json'] = json_bytes(manifest)
    package = out/'stock-404-candidate.zip'
    with zipfile.ZipFile(package, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, raw in sorted(entries.items()):
            archive.writestr(name, raw)
    read_bundle(package)
    return package


def rehearse(stock, package, out):
    stock_input(stock)
    _, deltas, module = read_bundle(package)
    original, capacity, tail = inventory(stock)
    if '/lib/a7fl.so' in original or any('/.a7fl-' in p for p in original):
        raise ValueError('Existing installation found')
    raw = read_files(stock, PINS)
    target = {p: apply_delta(raw[p], deltas[p]) for p in PINS}
    bs = capacity['block_size']
    required = sum(required_blocks(len(x), bs) for x in [module]+[target[p] for p in LOCALES])+16
    if required*bs > capacity['free_bytes'] or capacity['free_inodes'] < 3:
        raise ValueError('Not enough space for module and staged locales')
    work = out/'rehearsal'
    work.mkdir()
    image = work/'installed.img'
    shutil.copyfile(stock, image)
    logs = {}
    def command(label, lines, destination=image):
        script = work/(label+'.debugfs')
        script.write_text('\n'.join(lines)+'\n', encoding='utf-8')
        run = subprocess.run([DEBUGFS, '-w', '-f', str(script), str(destination)], capture_output=True, text=True, check=True)
        log = run.stdout+run.stderr
        (work/(label+'.log')).write_text(log, encoding='utf-8')
        if any(t in log.lower() for t in ('file not found', 'no free', 'usage:', 'already exists', 'invalid argument')):
            raise ValueError('debugfs failed: '+label)
    def check(label, destination=image):
        run = subprocess.run([FSCK, '-fn', str(destination)], capture_output=True, text=True, check=True)
        log = run.stdout+run.stderr
        (work/(label+'-fsck.log')).write_text(log, encoding='utf-8')
        logs[label] = sha(log.encode())
    def patch(p, old, new, destination=image):
        with destination.open('r+b') as stream, mmap.mmap(stream.fileno(), 0) as data:
            Ext2(data).replace(p, old, new)
            data.flush()
    check('stock')
    inputs = {'a7fl.so': module, **{Path(p).name:target[p] for p in LOCALES}}
    for name, data in inputs.items():
        (work/name).write_bytes(data)
    lines = [f'write {quoted(work/"a7fl.so")} /lib/a7fl.so', 'sif /lib/a7fl.so mode 0100555']
    for i,p in enumerate(LOCALES):
        lines += [f'write {quoted(work/Path(p).name)} /share/app/.a7fl-{i}.new',
                  f'sif /share/app/.a7fl-{i}.new mode 0100444']
    command('stage', lines)
    check('staged')
    for i,p in enumerate(LOCALES):
        candidate = f'/share/app/.a7fl-{i}.new'
        backup = f'/share/app/.a7fl-{i}.orig'
        command(f'publish-{i}', [f'ln {p} {backup}', f'sif {p} links_count 2', f'rm {p}',
                                f'ln {candidate} {p}', f'sif {candidate} links_count 2', f'rm {candidate}'])
        check(f'published-{i}')
    # Offline only: a live process may have any of these files mapped.
    for p in ('/share/app/image_cmn_43.uxc', '/lib/CautionConfig.so', VIEW):
        patch(p, raw[p], target[p])
        check('patched-'+Path(p).name)
    installed, after_capacity, after_tail = inventory(image)
    changed = {p for p in original if original[p] != installed.get(p)}
    expected_new = {'/lib/a7fl.so', '/share/app/.a7fl-0.orig', '/share/app/.a7fl-1.orig'}
    if changed != set(PINS) or set(installed)-set(original) != expected_new or after_tail != tail:
        raise ValueError('Unrelated files or partition tail changed')
    for p in PINS:
        if installed[p]['sha256'] != sha(target[p]):
            raise ValueError('Installed file mismatch')
    if installed['/lib/a7fl.so']['sha256'] != MODULE_SHA:
        raise ValueError('Module readback mismatch')
    # Independent ext2 implementation checks each installed file too.
    for i,p in enumerate(list(PINS)+['/lib/a7fl.so']):
        export = work/f'export-{i}'
        subprocess.run([DEBUGFS, '-R', f'dump {quoted(p)} {quoted(export)}', str(image)], check=True, capture_output=True)
        if export.read_bytes() != (module if p == '/lib/a7fl.so' else target[p]):
            raise ValueError('Independent readback mismatch: '+p)
        export.unlink()
    restored = work/'restored.img'
    shutil.copyfile(image, restored)
    for p in (VIEW, '/lib/CautionConfig.so', '/share/app/image_cmn_43.uxc'):
        patch(p, target[p], apply_delta(target[p], deltas[p], reverse=True), restored)
    lines = ['rm /lib/a7fl.so']
    for i,p in enumerate(LOCALES):
        backup = f'/share/app/.a7fl-{i}.orig'
        lines += [f'rm {p}', f'ln {backup} {p}', f'sif {backup} links_count 2', f'rm {backup}']
    command('restore', lines, restored)
    check('restored', restored)
    undone, _, restored_tail = inventory(restored)
    if undone != original or restored_tail != tail:
        raise ValueError('Offline restoration differs from stock file inventory')
    result = dict(passed=True, camera_written=False, stock_body_tested=False,
                  live_activation_ready=False, baseline_sha256=file_sha(stock), bundle_sha256=file_sha(package),
                  installed_image_sha256=file_sha(image), restored_image_sha256=file_sha(restored),
                  stock_file_count=len(original), changed_files=sorted(changed), added_files=sorted(expected_new),
                  all_unrelated_files_unchanged=True, all_restored_files_identical=True, partition_tail_unchanged=True,
                  capacity_before=capacity, capacity_after=after_capacity, staging_bytes_with_margin=required*bs,
                  full_view_copy_fits=capacity['free_bytes'] >= required*bs+required_blocks(len(target[VIEW]),bs)*bs,
                  filesystem_checks=logs,
                  scope='Offline filesystem endstates and byte-identical file restoration, not power-loss or live-device recovery',
                  source_sha256={p:file_sha(ROOT/p) for p in ['research/stock_first_install.py', 'research/ext2_patch.py', 'tools/stock_install_bundle.py']})
    (out/'rehearsal-proof.json').write_bytes(json_bytes(result))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock', type=Path, default=BACKUP)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to((ROOT/'.lab').resolve()):
        parser.error('Output must be a new directory inside .lab; device paths are not supported')
    out.mkdir(parents=True, exist_ok=False)
    package = build(args.stock.resolve(), out)
    result = rehearse(args.stock.resolve(), package, out)
    print('STOCK_FIRST_INSTALL_OFFLINE_PASSED')
    print(json.dumps({k:result[k] for k in ('stock_file_count','changed_files','staging_bytes_with_margin','capacity_after','stock_body_tested')}, indent=2))


if __name__ == '__main__':
    main()
