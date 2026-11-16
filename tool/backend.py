"""Portable desktop-tool operations. No camera flash transport is enabled."""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

HOME = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
LIB = HOME / 'lib'
sys.path.insert(0, str(LIB if LIB.is_dir() else HOME.parent / 'tools'))
from custom_look_recipes import MAX_BYTES, encode, parse
from look_recipes import FIELDS, LABELS, LOW, HIGH, LOOKS

MAX_ZIP = 64 * 1024 * 1024
INSTALL_REASON = ('原厂 4.04 首次安装尚未验收；现有部署脚本绑定开发机前像、加载器与私有备份。'
                  '此工具未接入刷写后端，不能安装或更新机身固件。')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def filename(name):
    if (not isinstance(name, str) or len(name.encode('utf-8')) > 240 or
            name.startswith('.') or name.endswith((' ', '.')) or
            re.search(r'[<>:"/\\|?*\x00-\x1f\x7f]', name) or
            not name.lower().endswith('.a7look') or
            re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', name)):
        raise ValueError('文件名须为普通 .a7look 文件名，不能含路径或系统保留名称。')
    return name


def recipe_record(name, raw):
    filename(name)
    item = parse(raw)
    return {'filename': name, 'recipe': item, 'sha256': digest(raw)}


def bundled_recipes():
    root = HOME / 'recipes'
    if not root.is_dir():
        root = HOME.parent / 'recipes'
    result = []
    for folder in ('defaults', 'film-collection'):
        for p in sorted((root / folder).glob('*.a7look')):
            result.append(recipe_record(p.name, p.read_bytes()))
    return result


def card_root(path):
    card = Path(path).expanduser().resolve(strict=True)
    if ((sys.platform != 'win32' and card == Path(card.anchor)) or
            (sys.platform == 'win32' and card == Path(card.anchor) and
             card.drive.casefold() == os.environ.get('SystemDrive', 'C:').casefold()) or
            card == Path('/System/Volumes/Data')):
        raise ValueError('不能选择电脑系统盘。请选择相机的 SD 存储卡。')
    if not card.is_dir() or not any((card / n).is_dir() for n in ('DCIM', 'AVF_INFO', 'PRIVATE')):
        raise ValueError('请选择 SD 卡根目录（包含 DCIM、AVF_INFO 或 PRIVATE），不要选择 DCIM 内部。')
    return card


def discover_cards():
    roots = []
    if sys.platform == 'win32':
        import ctypes
        mask = ctypes.windll.kernel32.GetLogicalDrives()
        roots = [Path(chr(65+i) + ':/') for i in range(26) if mask & (1 << i)]
    else:
        for parent in (Path('/Volumes'), Path('/media'), Path('/run/media'), Path('/mnt')):
            try:
                children = list(parent.iterdir())
                roots.extend(children)
                if str(parent) in ('/media', '/run/media'):
                    for child in children:
                        if child.is_dir():
                            roots.extend(child.iterdir())
            except OSError:
                continue
    found = set()
    for root in roots:
        try:
            found.add(str(card_root(root)))
        except (OSError, ValueError):
            pass
    return sorted(found)


def card_entries(card):
    return [p for p in card.iterdir() if p.suffix.lower() == '.a7look'
            and not p.name.startswith('._')]


def read_card(path):
    card = card_root(path)
    result = []
    for p in sorted(card_entries(card)):
        try:
            if p.is_symlink() or not p.is_file():
                raise ValueError('不是普通文件')
            with p.open('rb') as stream:
                row = recipe_record(p.name, stream.read(MAX_BYTES+1))
            result.append(row)
        except (OSError, ValueError, TypeError) as exc:
            result.append({'filename': p.name, 'error': str(exc)})
    return {'card': str(card), 'files': result}


def copy_plan(path, records):
    card = card_root(path)
    if not isinstance(records, list) or not 1 <= len(records) <= 32:
        raise ValueError('请选择 1 至 32 个配方。')
    entries = card_entries(card)
    existing = {p.name.casefold(): p for p in entries}
    if len(existing) != len(entries):
        raise ValueError('卡上存在仅大小写不同的同名文件，请先整理。')
    existing_ids = {}
    for p in entries:
        if p.is_file() and not p.is_symlink():
            try:
                with p.open('rb') as stream:
                    item = parse(stream.read(MAX_BYTES+1))
                existing_ids.setdefault(item['id'], set()).add(p.name.casefold())
            except (ValueError, TypeError):
                pass  # Legacy patch files remain untouched and count towards the limit.
    planned, ids = {}, set()
    for record in records:
        name = filename(record['filename'])
        raw = encode(record['recipe'])
        item = parse(raw)
        key = name.casefold()
        if key in planned or item['id'] in ids:
            raise ValueError('所选配方存在重复文件名或 ID：' + name)
        if existing_ids.get(item['id'], set()) - {key}:
            raise ValueError('卡上已有同 ID 的其他文件，取消复制：' + name)
        ids.add(item['id'])
        state = 'copy'
        if key in existing:
            p = existing[key]
            if p.is_symlink() or not p.is_file():
                raise ValueError('目标不是普通文件：' + name)
            with p.open('rb') as stream:
                old = stream.read(MAX_BYTES+1)
            # Treat JSON formatting as immaterial but never overwrite changed parameters.
            if parse(old) != item:
                raise ValueError('卡上同名文件内容不同，不会覆盖：' + name)
            state = 'present'
        planned[key] = {'filename': name, 'data': raw, 'state': state, 'sha256': digest(raw)}
    if len(existing.keys() | planned.keys()) > 32:
        raise ValueError('复制后将超过机内文件列表的 32 项上限。请先移走不用的配方。')
    return card, list(planned.values())


def copy_recipes(path, records):
    card, plan = copy_plan(path, records)  # Validate every input before creating any file.
    results = []
    for row in plan:
        target = card / row['filename']
        created = False
        try:
            if row['state'] == 'copy':
                with target.open('xb') as stream:
                    created = True
                    stream.write(row['data'])
                    stream.flush()
                    os.fsync(stream.fileno())
                if target.read_bytes() != row['data']:
                    raise OSError('完整回读不一致')
            results.append({k: v for k, v in row.items() if k != 'data'})
        except OSError as exc:
            if created:
                try:
                    target.unlink()
                except OSError:
                    pass
            return {'ok': False, 'files': results, 'error': f'{row["filename"]}: {exc}',
                    'message': '复制中断；前面已完成的文件保留，请检查 SD 卡后重试。'}
    return {'ok': True, 'files': results, 'message': '复制及回读完成。请在系统中安全推出，再到机内「从 SD 卡导入」。'}


def inspect_package(raw, expected=''):
    """Validate all ZIP members in memory; never extract or execute package code."""
    if not raw or len(raw) > MAX_ZIP:
        raise ValueError('ZIP 大小须在 1 字节至 64 MiB 之间。')
    actual = digest(raw)
    expected = expected.strip().lower()
    if expected and (not re.fullmatch('[0-9a-f]{64}', expected) or expected != actual):
        raise ValueError('ZIP SHA-256 与填写的发布校验值不一致。')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        infos = archive.infolist()
        if len(infos) > 10000 or sum(i.file_size for i in infos) > 128*1024*1024:
            raise ValueError('ZIP 展开大小或文件数超过限制。')
        members, names = {}, set()
        for info in infos:
            name = info.filename
            parts = name.rstrip('/').split('/')
            if (not parts or any(p in ('', '.', '..') for p in parts) or
                    '\\' in name or ':' in name or name.startswith('/') or
                    any(ord(c) < 32 for c in name) or name.casefold() in names or
                    stat.S_ISLNK(info.external_attr >> 16) or info.flag_bits & 1 or
                    info.file_size > 16*1024*1024):
                raise ValueError('ZIP 含不支持、重复或不安全的条目：' + name)
            names.add(name.casefold())
            if not info.is_dir():
                members[name] = info
        manifests = [n for n in members if len(PurePosixPath(n).parts) == 2 and n.endswith('/release-manifest.json')]
        if len(manifests) != 1:
            raise ValueError('需要包含 release-manifest.json 的 v0.01 完整功能 ZIP；不是 SD 工具 ZIP。')
        prefix = manifests[0].rsplit('/', 1)[0] + '/'
        sums = prefix + 'SHA256SUMS'
        if sums not in members or any(not n.startswith(prefix) for n in members):
            raise ValueError('发布包根目录或校验清单不完整。')
        checked = set()
        for line in archive.read(sums).decode('utf-8').splitlines():
            match = re.fullmatch(r'([0-9a-f]{64})  (.+)', line)
            if not match:
                raise ValueError('SHA256SUMS 格式错误。')
            checksum, relative = match.groups()
            name = prefix + relative
            if name not in members or name == sums or name in checked:
                raise ValueError('校验清单包含未知或重复文件。')
            if digest(archive.read(name)) != checksum:
                raise ValueError('文件校验失败：' + relative)
            checked.add(name)
        if checked != set(members) - {sums}:
            raise ValueError('存在未列入 SHA256SUMS 的文件。')
        manifest = json.loads(archive.read(manifests[0]))
        module = manifest['module']
        name = prefix + module['file']
        if (manifest['release'] != 'v0.01' or name not in checked or
                members[name].file_size != module['size'] or digest(archive.read(name)) != module['sha256']):
            raise ValueError('模块与版本清单不匹配。')
        return {'sha256': actual, 'files_verified': len(checked), 'manifest': manifest,
                'external_hash_matched': bool(expected), 'install_enabled': False,
                'install_reason': INSTALL_REASON,
                'message': '文件完整性校验通过。此结果不代表机身兼容、来源可信或已经安装。'}
