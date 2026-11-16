import types
import unittest
from unittest.mock import patch
import usb_transport as u


class Adapter:
    def __init__(self,normal=False,multiple=False):
        self.normal=normal;self.multiple=multiple;self.events=[];self.auths=0
    def list(self):
        self.events.append('list')
        devices=[types.SimpleNamespace(idProduct=u.NORMAL if self.normal else u.SERVICE)]
        return devices*2 if self.multiple else devices
    def open(self,d):self.events.append('open');return d
    def close(self,d):self.events.append('close')
    def normal_identity(self,d):self.events.append('identity')
    def authenticate(self,d):
        self.events.append('auth');self.auths+=1;self.normal=False
        return types.SimpleNamespace(stop=lambda:self.events.append('stop'))
    def camera(self,d):return types.SimpleNamespace(readBackup=lambda key:b'ILCE-7M3'+bytes(8))


class TransportTests(unittest.TestCase):
    def connect(self,adapter,allow=False):
        return u.connect(adapter=adapter,allow_switch=allow,timeout=0)
    def test_no_automatic_mode_switch(self):
        a=Adapter(normal=True)
        with self.assertRaises(u.TransportError),self.connect(a):pass
        self.assertEqual(a.events,['list'])
    def test_multiple_refused_before_open(self):
        a=Adapter(multiple=True)
        with self.assertRaises(u.TransportError),self.connect(a):pass
        self.assertEqual(a.events,['list'])
    def test_windows_two_stage_and_cleanup(self):
        a=Adapter(normal=True)
        with patch.object(u.sys,'platform','win32'),patch.object(u.Factory,'contents',return_value=u.BUILD):
            with self.connect(a,True):a.events.append('action')
        self.assertEqual(a.auths,2)
        self.assertEqual(a.events,['list','open','identity','auth','close','list','open','auth','action','stop','close'])
    def test_session_failure_never_retries(self):
        a=Adapter()
        with patch.object(u.Factory,'contents',return_value=u.BUILD):
            with self.assertRaises(OSError),self.connect(a):raise OSError('disconnected')
        self.assertEqual(a.auths,1);self.assertEqual(a.events[-2:],['stop','close'])
    def test_wrong_build_refused(self):
        a=Adapter()
        with patch.object(u.Factory,'contents',return_value=b'wrong'):
            with self.assertRaises(u.TransportError),self.connect(a):self.fail('Must not yield')
        self.assertEqual(a.events[-2:],['stop','close'])
    def test_wrong_model_before_switch(self):
        a=Adapter(normal=True)
        a.normal_identity=lambda _:(_ for _ in ()).throw(u.TransportError('wrong model'))
        with patch.object(u.sys,'platform','win32'):
            with self.assertRaises(u.TransportError),self.connect(a,True):pass
        self.assertEqual(a.auths,0);self.assertEqual(a.events[-1],'close')
    def test_mac_normal_mode_is_not_automatically_taken(self):
        a=Adapter(normal=True)
        with patch.object(u.sys,'platform','darwin'):
            with self.assertRaises(u.TransportError),self.connect(a,True):pass
        self.assertEqual(a.events,['list'])


if __name__=='__main__':unittest.main()
