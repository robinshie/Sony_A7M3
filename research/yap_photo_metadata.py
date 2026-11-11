#!/usr/bin/env python3
"""Read YAP records from local ILCE-7M3 4.04 JPEGs; never access the camera.

The record is evidence of the parameters recorded during capture, not measured
register state, pixel response, or live-view operation. Offsets come from the
pinned AV-CAM image. The byte substitution is documented by ExifTool Sony.pm:
https://github.com/exiftool/exiftool/blob/master/lib/Image/ExifTool/Sony.pm
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from gamma_avcam import SHA

MAX_JPEG = 48 * 1024 * 1024
TYPE_SIZE = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2,
             9: 4, 10: 8, 11: 4, 12: 8}
RAWDEV_BASE = 0x1364
LPF_OFFSETS = (RAWDEV_BASE + 0x319, RAWDEV_BASE + 0x31a)
_decode = list(range(256))
for _plain in range(249):
    _decode[pow(_plain, 3, 249)] = _plain
DECODE = bytes(_decode)


def bounded(data, offset, size):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError('Truncated or out-of-bounds metadata')
    return data[offset:offset + size]


def exif_segment(data):
    if len(data) > MAX_JPEG or data[:2] != b'\xff\xd8':
        raise ValueError('Expected a bounded JPEG')
    at, found, dimensions = 2, [], None
    while at < len(data):
        if data[at] != 0xff:
            raise ValueError('Invalid JPEG marker')
        while at < len(data) and data[at] == 0xff:
            at += 1
        marker = bounded(data, at, 1)[0]
        at += 1
        if marker == 0xd9:
            break
        if marker == 0xda:
            # No compressed pixels need to be decoded for this inspection.
            break
        if marker == 0 or marker == 0xd8 or 0xd0 <= marker <= 0xd7:
            raise ValueError('Unexpected standalone marker')
        size = int.from_bytes(bounded(data, at, 2), 'big')
        if size < 2:
            raise ValueError('Invalid JPEG segment size')
        body = bounded(data, at + 2, size - 2)
        if marker == 0xe1 and body.startswith(b'Exif\0\0'):
            found.append(body[6:])
        if marker in (0xc0, 0xc1, 0xc2):
            if dimensions is not None or len(body) < 6:
                raise ValueError('Ambiguous or short JPEG frame header')
            bits, height, width = struct.unpack('>BHH', body[:5])
            dimensions = dict(width=width, height=height, bits=bits)
        at += size
    if len(found) != 1 or dimensions is None:
        raise ValueError('Require one EXIF segment and one JPEG frame header')
    return found[0], dimensions


class Tiff:
    def __init__(self, data):
        self.data = data
        if data[:4] != b'II*\0':
            raise ValueError('Expected Sony little-endian TIFF')

    def directory(self, offset, limit=None):
        limit = len(self.data) if limit is None else limit
        if not 8 <= offset < limit <= len(self.data):
            raise ValueError('IFD outside its container')
        count = struct.unpack('<H', bounded(self.data, offset, 2))[0]
        if count > 512 or offset + 2 + count * 12 + 4 > limit:
            raise ValueError('Invalid IFD length')
        result = {}
        for i in range(count):
            at = offset + 2 + 12 * i
            tag, kind, items, value = struct.unpack('<HHII', self.data[at:at+12])
            if tag in result or kind not in TYPE_SIZE:
                raise ValueError('Duplicate tag or unsupported TIFF type')
            size = items * TYPE_SIZE[kind]
            start = at + 8 if size <= 4 else value
            raw = bounded(self.data, start, size)
            result[tag] = (kind, items, start, raw)
        return result

    @staticmethod
    def required(entries, key, kind, count=None):
        if key not in entries:
            raise ValueError(f'Missing tag {key:#x}')
        entry = entries[key]
        if entry[0] != kind or (count is not None and entry[1] != count):
            raise ValueError(f'Unexpected layout for tag {key:#x}')
        return entry


def inspect_jpeg(data):
    exif, dimensions = exif_segment(data)
    tiff = Tiff(exif)
    root = tiff.directory(struct.unpack('<I', bounded(exif, 4, 4))[0])
    for key, expected in ((0x10f, b'SONY\0'), (0x110, b'ILCE-7M3\0'),
                          (0x131, b'ILCE-7M3 v4.04\0')):
        if tiff.required(root, key, 2)[3] != expected:
            raise ValueError('JPEG camera model or firmware does not match')
    pointer = tiff.required(root, 0x8769, 4, 1)[3]
    photo = tiff.directory(struct.unpack('<I', pointer)[0])
    maker = tiff.required(photo, 0x927c, 7)
    if maker[3][:12] != b'SONY DSC \0\0\0':
        raise ValueError('Unexpected Sony MakerNote header')
    tags = tiff.directory(maker[2] + 12, maker[2] + maker[1])
    encoded = tiff.required(tags, 0x2010, 7, 6352)
    if not maker[2] <= encoded[2] < encoded[2] + encoded[1] <= maker[2] + maker[1]:
        raise ValueError('Tag2010 outside MakerNote')
    decoded = encoded[3].translate(DECODE)
    # Known schema on this build, not a promise that all 4.04 images use it.
    if decoded[:4] != b'\x01\0\0\0':
        raise ValueError('Unknown Tag2010 version')
    return dict(model='ILCE-7M3', firmware='4.04', dimensions=dimensions,
        jpeg_sha256=hashlib.sha256(data).hexdigest(),
        tag2010_bytes=len(decoded),
        tag2010_sha256=hashlib.sha256(decoded).hexdigest(),
        lpf=dict(vaplpf=decoded[LPF_OFFSETS[0]], haplpf=decoded[LPF_OFFSETS[1]]),
        yap_record_hex=decoded[RAWDEV_BASE+0x310:RAWDEV_BASE+0x350].hex(),
        offsets=dict(rawdev=hex(RAWDEV_BASE), vaplpf=hex(LPF_OFFSETS[0]),
                     haplpf=hex(LPF_OFFSETS[1])),
        scope='Captured processing metadata, not measured registers or pixels',
        live_view_verified=False, filter_response_verified=False)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--avcam', type=Path, required=True)
    cli.add_argument('--out', type=Path)
    cli.add_argument('photos', nargs='+', type=Path)
    args = cli.parse_args()
    if hashlib.sha256(args.avcam.read_bytes()).hexdigest() != SHA:
        cli.error('Requires the pinned ILCE-7M3 4.04 AV-CAM image')
    result = dict(avcam_sha256=SHA, photos=[])
    for path in args.photos:
        with path.open('rb') as source:
            data = source.read(MAX_JPEG + 1)
        result['photos'].append(dict(file=path.name, **inspect_jpeg(data)))
    report = json.dumps(result, indent=2) + '\n'
    if args.out:
        args.out.write_text(report)
    print(report, end='')


if __name__ == '__main__':
    main()
