#!/usr/bin/env python3
"""Synthetic JPEG boundary/identity checks; no private images or camera needed."""
import struct
import unittest

from yap_photo_metadata import DECODE, MAX_JPEG, inspect_jpeg


def fixture(v=1, h=1):
    # Minimal independent TIFF builder. Offsets deliberately differ from Sony's
    # actual JPEG layout so the reader cannot depend on fixed file positions.
    t = bytearray(7200)
    t[:8] = b'II*\0' + struct.pack('<I', 8)
    def directory(at, entries):
        struct.pack_into('<H', t, at, len(entries))
        for i, entry in enumerate(entries):
            struct.pack_into('<HHII', t, at+2+12*i, *entry)
    directory(8, [(0x10f,2,5,180), (0x110,2,9,190),
                  (0x131,2,15,210), (0x8769,4,1,80)])
    t[180:185] = b'SONY\0'
    t[190:199] = b'ILCE-7M3\0'
    t[210:225] = b'ILCE-7M3 v4.04\0'
    directory(80, [(0x927c,7,6800,300)])
    t[300:312] = b'SONY DSC \0\0\0'
    directory(312, [(0x2010,7,6352,400)])
    raw = bytearray(6352)
    raw[0] = 1
    raw[0x167d], raw[0x167e] = v, h
    t[400:6752] = bytes(pow(b,3,249) if b<249 else b for b in raw)
    def segment(marker, body):
        return b'\xff'+bytes([marker])+struct.pack('>H',len(body)+2)+body
    return (b'\xff\xd8' + segment(0xe1,b'Exif\0\0'+t) +
            segment(0xc0,struct.pack('>BHHB',8,4000,6000,1)+b'\x01\x11\x00') +
            b'\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00\xff\xd9')


class MetadataTest(unittest.TestCase):
    def test_all_byte_values(self):
        for v in range(256):
            r=inspect_jpeg(fixture(v,255-v))
            self.assertEqual(r['lpf'],dict(vaplpf=v,haplpf=255-v))
            self.assertEqual(r['dimensions'],dict(width=6000,height=4000,bits=8))
            self.assertFalse(r['live_view_verified'])
            self.assertFalse(r['filter_response_verified'])

    def test_substitution_is_bijective(self):
        self.assertEqual(sorted(DECODE),list(range(256)))
        self.assertEqual(DECODE[249:],bytes(range(249,256)))

    def test_reject_malformed_and_wrong_camera(self):
        good=fixture()
        mutations=[b'',good[:2],good[:10],good[:-20],
                   good.replace(b'ILCE-7M3\0',b'ILCE-7M4\0'),
                   good.replace(b'v4.04',b'v4.05'),
                   good.replace(b'SONY DSC ',b'OTHER DSC'),
                   good.replace(b'II*\0',b'MM\0*'),
                   good.replace(b'Exif\0\0',b'Other!')]
        # TIFF starts at JPEG byte 12. Cover root pointer, duplicate tag,
        # unknown type, enormous count, wrong schema, and external tag data.
        for offset, fmt, value in ((16,'I',0xffffff00), (20,'H',513),
            (34,'H',0x10f), (24,'H',13), (26,'I',0xffffffff),
            (330,'I',6351), (334,'I',100), (412,'B',8)):
            b=bytearray(good);struct.pack_into('<'+fmt,b,offset,value)
            mutations.append(bytes(b))
        # Duplicate EXIF segment must not silently select a different record.
        segment_size=int.from_bytes(good[4:6],'big')+2
        mutations.append(good[:2]+good[2:2+segment_size]+good[2:])
        mutations.append(b'\xff\xd8'+bytes(MAX_JPEG))
        for i,b in enumerate(mutations):
            with self.subTest(case=i),self.assertRaises(ValueError):
                inspect_jpeg(b)


if __name__=='__main__':
    unittest.main()
