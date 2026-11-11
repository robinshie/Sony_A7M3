#!/usr/bin/env python3
"""Offline regression: transport fallback must not authorize a wrong-camera payload."""
import contextlib
import io
from pathlib import Path
import runpy
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from research.yc_trace import live

def module(name,**items):
    m=ModuleType(name);m.__dict__.update(items);return m

def guest(arguments=(),product=0x0c02,model='ILCE-7M3',sony=True,count=1):
    events=[]
    def event(name):events.append(name)
    backend=SimpleNamespace(classInterfaceRequestOut=lambda *a:event('bulk-reset'),clearHalt=lambda *a:event('clear-halt'))
    driver=SimpleNamespace(reset=lambda:event('detach'),backend=backend,epIn=[1],epOut=[2])
    context=SimpleNamespace(listDevices=lambda vendor:[SimpleNamespace(idProduct=product)]*count,openDevice=lambda item:driver)
    class Extended:
        def __init__(self,d):pass
        def getCameraInfo(self):event('extended-info');return SimpleNamespace(modelName=model)
    class Auth:
        def __init__(self,d):pass
        def start(self):event('auth-start')
        def authenticate(self):event('auth-finish')
    modules={
        'pmca.usb':module('pmca.usb',MscDevice=lambda d:SimpleNamespace(getDeviceInfo=lambda:event('inquiry'))),
        'pmca.usb.driver.generic.libusb':module('pmca.usb.driver.generic.libusb',MscContext=lambda:context),
        'pmca.usb.sony':module('pmca.usb.sony',SonyExtCmdCamera=Extended,SonyMscExtCmdDevice=lambda d:d,
            SonySenserAuthDevice=Auth,isSonyMscCamera=lambda value:sony),
    }
    rejected=False
    with patch.dict(sys.modules,modules),patch.object(sys,'argv',['guest_switch.py',*arguments]),contextlib.redirect_stdout(io.StringIO()):
        try:runpy.run_path(str(ROOT/'camera/guest_switch.py'),run_name='__main__')
        except SystemExit:rejected=True
    return rejected,events

def host_reject(build,model):
    calls=[]
    class Factory:
        def __init__(self,camera):pass
        def contents(self,path,*args):calls.append(path);return build if path=='/version.txt' else b'wrong-library'
        def run(self,*args):raise AssertionError('Camera payload was attempted before identity/library rejection')
    camera=SimpleNamespace(readBackup=lambda key:model)
    with patch.dict(sys.modules,{'camera.service':module('camera.service',Factory=Factory)}):
        try:live(camera,ROOT/'.lab/nonexistent-identity-fixture','install',('write','make'))
        except ValueError:return calls
    raise AssertionError('Wrong model/build/library accepted')

def main():
    ok,events=guest();assert not ok and 'extended-info' in events and events[-1]=='auth-finish'
    bad,events=guest(model='different');assert bad and 'auth-start' not in events
    for args in ((),('--host-identity-check',)):
        for kwargs in ({'product':0x1234},{'count':2},{'sony':False}):
            bad,events=guest(args,**kwargs);assert bad and 'auth-start' not in events
    bad,events=guest(('--unexpected',));assert bad and 'auth-start' not in events
    ok,events=guest(('--host-identity-check',));assert not ok and 'extended-info' not in events and events[-1]=='auth-finish'
    model=b'ILCE-7M3'+bytes(8);build=b'37114_13.2026020901'
    assert host_reject(b'other',model)==['/version.txt']
    assert host_reject(build,b'other')==['/version.txt']
    assert host_reject(build,model)==['/version.txt','/usr/lib/libObj.so']
    print('GUEST_HOST_IDENTITY_PASSED cases=13; no hardware accessed')

if __name__=='__main__':main()
