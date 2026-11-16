"""Portable, offline stock 4.04 delta format. This module has no device I/O."""
import base64
import hashlib
import json
import stat
import zipfile

KIND = 'a7m3-stock-404-candidate-v1'
# These are file identities, NOT partition offsets or hashes of another body's settings.
PINS = {
    '/lib/viewUnified2.so': ('f561a1e5fa0d10d55727dd4a10ced97c9613b698a40b489ff9317634485e5129', 'a1c4d8e88f54f71786ff53bc15a59c32a2969a6ffc934ef77728123d8af172a7'),
    '/lib/CautionConfig.so': ('0b9f2b855c032fc36cc83386a1fe706a8b59042e52702035a7d1a293b4e9f8a0', 'be38cd21ffa9e1720cc910af10e3a526ecd4f580a418a56c8c1bd1009bf00567'),
    '/share/app/image_cmn_43.uxc': ('5cb0f3c26de5923674473ae91877960b8b01d42e573767b46d6f25bf376d2db0', 'b13dba8a2ab03594dfcfa70e0b3c4b3e82c7b27989d9e9dddc106ab692c09c59'),
    '/share/app/string_simplifiedchinese.uxc': ('61ce4af838a991ad02d89726c0bee3f0aa443ac4421b1d9edff07fe55c0dd249', 'abd89f064761b234623e603a461588f7433dbf1a282e669d413866ac26a7d33b'),
    '/share/app/string_english.uxc': ('eb4793ba3191a7aeb2f4e6f73694bf93e8f67c1f5ec6f1638dc67a291e015426', '36bed3b1be93c6fc1ecea704ea487d4baec315543a599e7d01846e87b59feb42'),
}
MODULE_SHA = '30474345352eaed6b1feb8f33e389278febaeb6c3fc493dc2355ab560ca591a4'
MAX_FILE = 32 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(data):
    return dict(size=len(data), sha256=sha(data))


def make_delta(before, after):
    """Fixed-offset differences plus an optional tail. Never insert in the middle."""
    if len(before) > len(after) or len(after) > MAX_FILE:
        raise ValueError('Unsupported size change')
    rows = []
    pos = 0
    while pos < len(after):
        if pos < len(before) and before[pos] == after[pos]:
            pos += 1
            continue
        start = pos
        pos += 1
        while pos < len(after) and (pos >= len(before) or before[pos] != after[pos]):
            pos += 1
        rows.append(dict(offset=start, before=base64.b64encode(before[start:pos]).decode(),
                         after=base64.b64encode(after[start:pos]).decode()))
    return dict(before=identity(before), after=identity(after), changes=rows)


def apply_delta(raw, delta, reverse=False):
    source, target = ('after', 'before') if reverse else ('before', 'after')
    if identity(raw) != delta[source]:
        raise ValueError('Exact file preimage required')
    old_size, new_size = delta['before']['size'], delta['after']['size']
    if not (type(old_size) is int and type(new_size) is int and 0 <= old_size <= new_size <= MAX_FILE):
        raise ValueError('Invalid delta size')
    data = bytearray(raw)
    end = 0
    for row in delta['changes']:
        at = row['offset']
        old = base64.b64decode(row['before'], validate=True)
        new = base64.b64decode(row['after'], validate=True)
        if (type(at) is not int or at < end or at > new_size or not new or
                at + len(new) > new_size or len(old) != min(len(new), max(0, old_size-at))):
            raise ValueError('Invalid or overlapping range')
        expected, value = (new, old) if reverse else (old, new)
        if at > len(data) or data[at:at+len(expected)] != expected:
            raise ValueError('Range preimage mismatch')
        # Reverse never shifts the following offsets: the tail is trimmed last.
        data[at:at+len(value)] = value
        end = at + len(new)
    result = bytes(data[:delta[target]['size']])
    if identity(result) != delta[target]:
        raise ValueError('Delta output hash mismatch')
    return result


def read_bundle(path):
    """Strict allowlist and embedded identity pins; no extraction or execution."""
    with zipfile.ZipFile(path) as archive:
        names = ['manifest.json', 'a7fl.so'] + [f'deltas/{i}.json' for i in range(len(PINS))]
        infos = archive.infolist()
        if (len(infos) != len(names) or set(archive.namelist()) != set(names) or
                sum(i.file_size for i in infos) > 8*1024*1024 or
                any(i.flag_bits & 1 or stat.S_ISLNK(i.external_attr >> 16) for i in infos)):
            raise ValueError('Unexpected bundle members or size')
        files = {n: archive.read(n) for n in names}
    manifest = json.loads(files['manifest.json'])
    if (manifest.get('kind') != KIND or manifest.get('model') != 'ILCE-7M3' or
            manifest.get('firmware') != '4.04' or manifest.get('device_install_verified') is not False or
            manifest.get('flash_ready') is not False):
        raise ValueError('Not an unverified stock-install candidate')
    sums = {n: sha(v) for n, v in files.items() if n != 'manifest.json'}
    if manifest.get('sha256') != sums or sha(files['a7fl.so']) != MODULE_SHA:
        raise ValueError('Bundle integrity or accepted module mismatch')
    records = manifest.get('files', [])
    if [r['path'] for r in records] != list(PINS):
        raise ValueError('Unexpected destination paths')
    deltas = {}
    for i, (path, pins) in enumerate(PINS.items()):
        delta = json.loads(files[f'deltas/{i}.json'])
        if (records[i].get('delta') != f'deltas/{i}.json' or
                records[i].get('before') != delta['before'] or records[i].get('after') != delta['after'] or
                (delta['before']['sha256'], delta['after']['sha256']) != pins):
            raise ValueError('Unknown stock or target file')
        deltas[path] = delta
    return manifest, deltas, files['a7fl.so']
