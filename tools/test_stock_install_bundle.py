"""Portable delta failures and round trips; no Sony binaries or USB required."""
import copy
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import stock_install_bundle as b


class DeltaTests(unittest.TestCase):
    def test_round_trip_and_tail(self):
        rng = random.Random(404)
        for size in (0,1,2,31,4095,4096,4097):
            old = bytes(rng.randrange(256) for _ in range(size))
            for growth in (0,1,27):
                new = bytearray(old)+bytes([254])*growth
                for at in range(0,len(new),11):
                    new[at] ^= 127
                delta = b.make_delta(old,bytes(new))
                self.assertEqual(b.apply_delta(old,delta),new)
                self.assertEqual(b.apply_delta(bytes(new),delta,True),old)

    def test_wrong_baseline_and_replay(self):
        delta = b.make_delta(b'abcdef',b'aBCdef!')
        for raw in (b'ABCdef',b'aBCdef!',b'abcde'):
            with self.assertRaises(ValueError):
                b.apply_delta(raw,delta)

    def test_tampered_ranges(self):
        delta = b.make_delta(b'abcdef',b'AbcdeF')
        for change in ('overlap','negative','outside','empty','base64','old','output'):
            d = copy.deepcopy(delta)
            if change == 'overlap': d['changes'][1]['offset'] = 0
            if change == 'negative': d['changes'][0]['offset'] = -1
            if change == 'outside': d['changes'][0]['offset'] = 100
            if change == 'empty': d['changes'][0]['after'] = ''
            if change == 'base64': d['changes'][0]['after'] = '!!!!'
            if change == 'old': d['changes'][0]['before'] = 'eA=='
            if change == 'output': d['after']['sha256'] = '0'*64
            with self.subTest(change=change), self.assertRaises(ValueError):
                b.apply_delta(b'abcdef',d)

    def test_shrink_refused(self):
        with self.assertRaises(ValueError): b.make_delta(b'abc',b'ab')

    def test_bundle_validation(self):
        old,new,module = b'abc',b'Abc!',b'own-module'
        pins = {'/lib/example.so':(b.sha(old),b.sha(new))}
        delta = b.make_delta(old,new)
        files = {'a7fl.so':module,'deltas/0.json':json.dumps(delta).encode()}
        manifest = dict(kind=b.KIND,model='ILCE-7M3',firmware='4.04',flash_ready=False,
                        device_install_verified=False,files=[dict(path='/lib/example.so',delta='deltas/0.json',
                            before=delta['before'],after=delta['after'])],
                        sha256={n:b.sha(v) for n,v in files.items()})
        with tempfile.TemporaryDirectory() as temp, patch.object(b,'PINS',pins), patch.object(b,'MODULE_SHA',b.sha(module)):
            path = Path(temp)/'candidate.zip'
            def write(m, extra=None):
                with zipfile.ZipFile(path,'w') as z:
                    for n,v in files.items(): z.writestr(n,v)
                    z.writestr('manifest.json',json.dumps(m))
                    if extra: z.writestr(extra,b'bad')
            write(manifest)
            self.assertEqual(b.read_bundle(path)[2],module)
            for extra in ('../evil','a7fl.so'):
                if extra == 'a7fl.so':
                    with self.assertWarns(UserWarning): write(manifest,extra)
                else: write(manifest,extra)
                with self.assertRaises(ValueError): b.read_bundle(path)
            for key,value in [('flash_ready',True),('device_install_verified',True),('firmware','4.03'),('sha256',{})]:
                m=copy.deepcopy(manifest);m[key]=value;write(m)
                with self.subTest(key=key),self.assertRaises(ValueError): b.read_bundle(path)
            m=copy.deepcopy(manifest);m['files'][0]['path']='/setting/user-data';write(m)
            with self.assertRaises(ValueError): b.read_bundle(path)
            m=copy.deepcopy(manifest);m['files'][0]['after']['size']=99;write(m)
            with self.assertRaises(ValueError): b.read_bundle(path)
            write(manifest)
            with zipfile.ZipFile(path,'a') as z:
                link=zipfile.ZipInfo('link');link.external_attr=0o120777<<16
                z.writestr(link,b'a7fl.so')
            with self.assertRaises(ValueError): b.read_bundle(path)


if __name__ == '__main__': unittest.main()
