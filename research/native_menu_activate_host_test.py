#!/usr/bin/env python3
"""Offline host workflow tests; imports no USB implementation and contacts nothing."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from camera import native_activate as n
from local import BUILD_ID,LAB,file_sha


def report(binding,writing=False,status=0,pid=37):
    return struct.pack('<8I4i32s',0x41374e41,1,100 if writing else 3,pid,0x20000000,0,
                       7 if writing else 0,15 if writing else 0,status,0,int(status!=0),1,bytes.fromhex(binding))


def journal(binding,reverse=False):
    states=[(10,0,0),(20,1,0),(21,3,0),(22,7,0),(30,7,0)]
    written=0
    for step,index in enumerate((3,2,1,0) if reverse else (0,1,2,3)):
        states.append((40+step*2,7,written));written|=1<<index;states.append((41+step*2,7,written))
    states.append((100,7,15))
    out=b''
    for seq,(phase,cow,written) in enumerate(states,1):
        head=struct.pack('<5I',0x41374641,seq,phase,cow,written)+bytes.fromhex(binding)
        out+=head+hashlib.sha256(head).digest()
    return out


class Camera:
    def readBackup(self,key):
        assert key==0x3e0005
        return b'ILCE-7M3'+bytes(8)


class Factory:
    missing=(0,0x10000006)
    def __init__(self,bundle,state='old',fault=None):
        self.bundle=bundle;self.view=bundle.old if state=='old' else bundle.new
        self.files={};self.runs=[];self.fault=fault
    def contents(self,path,maximum=1024*1024):
        if path=='/version.txt':return b'foreign' if self.fault=='build' else BUILD_ID
        assert path==n.VIEW and len(self.view)<=maximum
        return self.view
    def read(self,path,maximum=1024*1024):
        assert path in self.bundle.journals.values()
        return ((0,0),self.files[path]) if path in self.files else (self.missing,b'')
    def run(self,raw,name):
        assert name==n.REPORT
        mode=next(mode for mode,data in self.bundle.payloads.items() if data==raw)
        self.runs.append(mode);binding=self.bundle.manifest['bundle_sha256']
        if mode=='preflight':
            if self.fault=='foreign-file':self.view=bytes([self.view[0]^1])+self.view[1:]
            return report(binding,status=-1 if self.fault=='preflight' else 0)
        if self.fault=='transport':raise OSError('simulated disconnect')
        self.view=self.bundle.new if mode=='activate' else self.bundle.old
        if self.fault=='rollback':self.view=self.bundle.old
        self.files[self.bundle.journals[mode]]=journal(binding,mode!='activate')
        return report(binding,True,status=-1 if self.fault=='rollback' else 0,pid=38 if self.fault=='changed-pid' else 37)


class Workflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=n.Bundle(LAB/'native-menu-activate',LAB/'native-install-bound',LAB/'native-module/proof.json',LAB/'creative-icons-belt',LAB/'native-fl-strings')
    def invoke(self,mode='preflight',state='old',fault=None,write=False,existing=False):
        factory=Factory(self.bundle,state,fault)
        if existing:factory.files[self.bundle.journals[mode]]=journal(self.bundle.manifest['bundle_sha256'])
        with tempfile.TemporaryDirectory(dir=self.bundle.directory) as td:
            evidence=Path(td)
            fake=types.ModuleType('camera.service');fake.Factory=lambda camera:factory
            with patch.dict(sys.modules,{'camera.service':fake}):
                try:result=n.operate(Camera(),self.bundle,mode,evidence,write)
                except Exception as exc:result=exc
            names={str(p.relative_to(evidence)) for p in evidence.rglob('*') if p.is_file()}
            final=json.loads((evidence/'result.json').read_text()) if (evidence/'result.json').exists() else None
        return result,factory,names,final
    def test_default_readonly(self):
        result,factory,names,_=self.invoke()
        self.assertTrue(result['verified']);self.assertEqual(factory.runs,['preflight']);self.assertNotIn('write-started.json',names)
    def test_activation_fresh_same_session_preflight(self):
        result,factory,names,_=self.invoke('activate',write=True)
        self.assertTrue(result['verified']);self.assertEqual(factory.runs,['preflight','activate'])
        self.assertIn('write-started.json',names);self.assertIn('after/viewUnified2.so',names)
    def test_explicit_write_required(self):
        result,factory,_,_=self.invoke('activate')
        self.assertIsInstance(result,ValueError);self.assertFalse(factory.runs)
    def test_no_existing_journal_resume(self):
        result,factory,names,_=self.invoke('activate',write=True,existing=True)
        self.assertIsInstance(result,ValueError);self.assertFalse(factory.runs);self.assertNotIn('write-started.json',names)
    def test_native_preflight_failure_never_writes(self):
        result,factory,names,_=self.invoke('activate',write=True,fault='preflight')
        self.assertIsInstance(result,ValueError);self.assertEqual(factory.runs,['preflight']);self.assertNotIn('write-started.json',names)
    def test_foreign_view_never_writes(self):
        result,factory,names,_=self.invoke('activate',write=True,fault='foreign-file')
        self.assertIsInstance(result,ValueError);self.assertEqual(factory.runs,['preflight']);self.assertNotIn('write-started.json',names)
    def test_wrong_build_never_runs(self):
        result,factory,_,_=self.invoke('activate',write=True,fault='build')
        self.assertIsInstance(result,ValueError);self.assertFalse(factory.runs)
    def test_failed_write_captures_state_no_auto_recovery(self):
        result,factory,names,final=self.invoke('activate',write=True,fault='rollback')
        self.assertIsInstance(result,ValueError);self.assertEqual(factory.runs,['preflight','activate'])
        self.assertIn('after/viewUnified2.so',names);self.assertFalse(final['verified']);self.assertEqual(final['view']['state'],'old')
    def test_transport_exception_no_retry(self):
        result,factory,names,_=self.invoke('activate',write=True,fault='transport')
        self.assertIsInstance(result,OSError);self.assertEqual(factory.runs,['preflight','activate']);self.assertIn('write-started.json',names)
    def test_changed_process_fails_same_session_guard(self):
        result,factory,_,final=self.invoke('activate',write=True,fault='changed-pid')
        self.assertIsInstance(result,ValueError);self.assertEqual(factory.runs,['preflight','activate']);self.assertFalse(final['verified'])
    def test_explicit_recovery(self):
        result,factory,_,_=self.invoke('recover',state='new',write=True)
        self.assertTrue(result['verified']);self.assertEqual(factory.runs,['recover'])
    def test_explicit_postboot_deactivate(self):
        result,factory,_,_=self.invoke('deactivate',state='new',write=True)
        self.assertTrue(result['verified']);self.assertEqual(factory.runs,['deactivate'])
    def test_explicit_postboot_deactivate_recovery(self):
        result,factory,_,_=self.invoke('deactivate-recover',state='new',write=True)
        self.assertTrue(result['verified']);self.assertEqual(factory.runs,['deactivate-recover'])
    def test_deactivate_rejects_old_file_before_write(self):
        result,factory,names,_=self.invoke('deactivate',state='old',write=True)
        self.assertIsInstance(result,ValueError);self.assertFalse(factory.runs);self.assertNotIn('write-started.json',names)
    def test_journal_foreign_and_torn(self):
        binding=self.bundle.manifest['bundle_sha256'];raw=journal(binding)
        self.assertIsNone(n.journal_records(raw,binding)['integrity_error'])
        self.assertEqual(n.journal_records(raw[:-1],binding)['integrity_error'],'Torn trailing record')
        self.assertIsNotNone(n.journal_records(raw,'00'*32)['integrity_error'])
    def test_report_binding(self):
        binding=self.bundle.manifest['bundle_sha256'];raw=report(binding)
        self.assertTrue(n.report_success(n.activation_report(raw,binding)))
        with self.assertRaises(ValueError):n.activation_report(raw,'00'*32)
        with self.assertRaises(ValueError):n.activation_report(raw[:-1],binding)
    def test_known_partial_and_foreign(self):
        mixed=bytearray(self.bundle.old)
        for off,size in self.bundle.patches:mixed[off:off+size//2]=self.bundle.new[off:off+size//2]
        self.assertEqual(self.bundle.known_view(mixed),'known-mixed')
        mixed[100]^=1;self.assertEqual(self.bundle.known_view(mixed),'foreign')


class SettingWorkflow(Workflow):
    @classmethod
    def setUpClass(cls):
        cls.bundle=n.Bundle(LAB/'native-setting-activate',LAB/'native-install-bound',LAB/'native-module/proof.json',LAB/'creative-icons-belt',LAB/'native-fl-strings',setting=True)
    def test_separate_layout_and_journals(self):
        self.assertEqual(self.bundle.patches,n.SETTING_PATCHES)
        self.assertFalse(set(self.bundle.journals.values()) & set(n.JOURNALS.values()))
        self.assertEqual(self.bundle.old[0x188aec:0x188af0],self.bundle.new[0x188aec:0x188af0])
        with self.assertRaises(ValueError):
            n.Bundle(LAB/'native-setting-activate',LAB/'native-install-bound',LAB/'native-module/proof.json',LAB/'creative-icons-belt',LAB/'native-fl-strings')


if __name__=='__main__':
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(c) for c in (Workflow,SettingWorkflow))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
    proof={'tests_passed':result.testsRun,'camera_contacted':False,'source_sha256':{p:file_sha(ROOT/p) for p in ['camera/native_activate.py','research/native_menu_activate_host_test.py']},'native_manifest_sha256':{p:file_sha(LAB/p/'manifest.json') for p in ('native-menu-activate','native-setting-activate')},'scope':'Offline mocked transport order/report/recovery tests for original and retargeted profiles; not a camera test.'}
    for p in ('native-menu-activate','native-setting-activate'):
        (LAB/p/'host-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
