import copy
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import first_install as f


def wbi(data,write=False,pid=37):
    empty=data[:512]==bytes(512)
    values=[0x57423741,1,100 if write else (2 if empty else 3),1 if empty else 0,0,pid,0x03c00000,0,
            int(write),0 if empty else 1,512 if write else 0,1 if write else 0,1,0]
    return struct.pack('<3I2i9I',*values)+bytes.fromhex(f.sha(data))+data


class Factory:
    def __init__(self):
        self.original={f'/lib/{p}':('old-'+p).encode() for p in ('icons','config','loader')}
        self.targets={p:raw.replace(b'old',b'new') for p,raw in self.original.items()}
        self.files={'/usr'+p:raw for p,raw in self.original.items()};self.calls=[];self.fail=None
        self.header=bytearray(1024);self.header[:4]=b'WBI0';struct.pack_into('<I',self.header,20,512);self.header[512:]=b'n'*512
        self.header=bytes(self.header)
        self.manifest={'stage':{'bundle_sha256':'11'*32},'activation':{'profiles':[]},'sha256':{},'wbi':{'offset':16}}
        self.payloads={'stage.so':b'stage','wbi-probe.so':b'probe','wbi-template.so':b'x'*1040}
        for name in ('icons','config','loader'):
            p={'name':name,'path':'/usr/lib/'+name,'before_sha256':f.sha(self.original['/lib/'+name]),
               'after_sha256':f.sha(self.targets['/lib/'+name]),'bundle_sha256':'22'*32,'page_offsets':[0]}
            self.manifest['activation']['profiles'].append(p)
            for mode in ('preflight','activate'):self.payloads[name+'/'+mode+'.so']=(name+'-'+mode).encode()
    def contents(self,path):return self.files[path]
    def run(self,raw,report):
        self.calls.append(raw)
        if raw==b'probe':return wbi(self.header)
        if raw==b'stage':
            self.files['/usr/lib/a7fl.so']=b'module'
            return struct.pack('<6I4i32s',0x41374649,1,100,0,7,3,0,0,0,1,bytes.fromhex('11'*32))
        for p in self.manifest['activation']['profiles']:
            for mode in ('preflight','activate'):
                if raw==(p['name']+'-'+mode).encode():
                    ok=raw!=self.fail
                    if mode=='activate' and ok:self.files[p['path']]=self.targets[p['path'].removeprefix('/usr')]
                    return struct.pack('<8I4i32s',0x41374e41,1,3 if mode=='preflight' else 100,37,0x20000000,0,
                        0 if mode=='preflight' else 1,0 if mode=='preflight' else 1,0 if ok else -1,0,0,1,bytes.fromhex('22'*32))
        # WBI template is the only byte-bound payload.
        expected=raw[16:1040]
        assert expected==self.header
        old=self.header;self.header=bytes(512)+old[512:]
        return wbi(old,True)


class InstallTests(unittest.TestCase):
    def run_transaction(self,a):
        pins={p:(f.sha(old),f.sha(a.targets[p])) for p,old in a.original.items()}
        initial,data=f.wbi_report(wbi(a.header))
        with tempfile.TemporaryDirectory() as td,patch.object(f,'PINS',pins),patch.object(f,'MODULE_SHA',f.sha(b'module')):
            result=f.write_device(a,a.manifest,a.payloads,a.original,(initial,data),Path(td),lambda _:None)
            self.assertTrue((Path(td)/'written-awaiting-cold-boot.json').exists())
            return result
    def test_real_workflow_order(self):
        a=Factory();result=self.run_transaction(a)
        self.assertEqual(a.calls[:8],[b'probe',b'stage',b'icons-preflight',b'icons-activate',b'config-preflight',b'config-activate',b'loader-preflight',b'loader-activate'])
        self.assertFalse(result['cold_boot_verified']);self.assertTrue(result['written_and_readback'])
    def test_failure_stops_before_next_stage_and_wbi(self):
        for phase in (b'icons-preflight',b'config-activate',b'loader-preflight'):
            a=Factory();a.fail=phase
            with self.subTest(phase=phase),self.assertRaises(ValueError):self.run_transaction(a)
            self.assertEqual(a.calls[-1],phase);self.assertEqual(a.header[:4],b'WBI0')
    def test_changed_preimage_never_sends_payload(self):
        a=Factory();a.files['/usr/lib/icons']=b'foreign'
        with self.assertRaises(ValueError):self.run_transaction(a)
        self.assertFalse(a.calls)
    def test_already_invalidated_wbi_does_not_write_it(self):
        a=Factory();a.header=bytes(512)+a.header[512:];self.run_transaction(a)
        self.assertEqual(a.calls[-1],b'probe');self.assertEqual(len(a.calls),9)
    def test_bad_wbi_data_and_lengths(self):
        a=Factory();raw=wbi(a.header)
        for invalid in (raw[:-1],raw[:-1]+b'X',b''):
            with self.assertRaises(ValueError):f.wbi_report(invalid)
    def test_confirm_requires_exact_ready_job(self):
        task=f.Installer()
        with self.assertRaises(ValueError):task.decide('unknown',True)
        task.state={'job':'one','phase':'ready','messages':[]}
        with self.assertRaises(ValueError):task.decide('two',True)
        task.decide('one',False)
        self.assertFalse(task.confirmed)
        with self.assertRaises(ValueError):task.decide('one',True)
    def test_package_hash_required_before_transport(self):
        for expected in ('','0'*64):
            with self.assertRaises(ValueError):f.load_package(b'anything',expected)


if __name__=='__main__':unittest.main()
