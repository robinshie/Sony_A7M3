"""Direct Windows/Linux libusb transport. Importing does not enumerate USB.

Normal mode requires explicit consent to switch. No payload or write retry is
performed here; the caller owns one authenticated session and its transaction.
"""
from contextlib import contextmanager
import importlib.util
from pathlib import Path
import struct
import sys
import time

VENDOR, NORMAL, SERVICE = 0x054c, 0x0c02, 0x0336
BUILD = b'37114_13.2026020901'


def dependencies():
    vendor = Path(__file__).resolve().parent/'vendor'
    if vendor.is_dir() and str(vendor) not in sys.path:
        sys.path.insert(0,str(vendor))
    return {name: importlib.util.find_spec(name) is not None
            for name in ('usb','libusb_package','Cryptodome','pmca')}


class TransportError(RuntimeError):
    pass


def runtime_check():
    """Check bundled native libraries only. Never call find/list/open devices."""
    if not all(dependencies().values()): raise TransportError('USB dependencies missing')
    import libusb_package
    from Cryptodome.Hash import SHA1
    from pmca.usb.sony import SonySenserAuthDevice
    from pmca.usb.driver.generic.libusb import UsbBackend
    if libusb_package.get_libusb1_backend() is None: raise TransportError('libusb library unavailable')
    assert SHA1.new(b'abc').hexdigest() == 'a9993e364706816aba3e25717850c26c9cd0d89d'
    return dict(libusb_loaded=True, crypto_loaded=True, protocol_imported=True, devices_enumerated=False)


def usb_error(error):
    return TransportError('无法打开相机 USB 接口。Windows 需为 054C:0C02（大容量）和 '
        '054C:0336（Sony USB Device）分别配置兼容 libusb 的驱动；关闭其他占用相机的软件。'
        '工具不会替换驱动或重试写入。原因：'+str(error))


class Factory:
    missing = (0,0x10000006)
    prefix = '/tmp/jiritsu/'

    def __init__(self,camera):
        self.camera = camera

    def call(self,code,data=b'',maximum=32*1024*1024):
        class Response(bytearray):
            def write(self,raw):
                if len(self)+len(raw)>maximum: raise TransportError('维护响应超出上限')
                self.extend(raw)
        reply=Response()
        result,_=self.camera.dev.sendSenserPacket(0x40,struct.pack('<HH',0x1001,code)+data,reply)
        status=struct.unpack_from('<I',reply)[0] if len(reply)>=4 else None
        return (result,status),bytes(reply[4:])

    def read(self,path,maximum=32*1024*1024):
        if not path.startswith('/') or '\0' in path: raise ValueError('Invalid camera path')
        return self.call(0x4008,b'\x01\0\0/..'+path.encode('ascii')+b'\0',maximum)

    def contents(self,path,maximum=32*1024*1024):
        status,raw=self.read(path,maximum)
        if status!=(0,0): raise TransportError(f'相机文件读取失败：{path} {status}')
        return raw

    def checked(self,code,data=b''):
        status,raw=self.call(code,data)
        if status!=(0,0): raise TransportError(f'维护命令失败：{code:#x} {status}')
        return raw

    def run(self,payload,report):
        if not report.isascii() or not report.replace('.','').isalnum(): raise ValueError('Invalid report name')
        names=('libJit.so',report)
        self.checked(0x4002,b'\0\0')
        for name in names:
            if self.read(self.prefix+name)[0]!=self.missing:
                raise TransportError('相机上已有未清理的任务；停止，不能覆盖：'+name)
        try:
            self.checked(0x000f,b'\0libJit.so\0')
            self.checked(0x0010,b'\0\xff\0'+payload)
            return self.contents(self.prefix+report)
        finally:
            # A disconnect propagates; it never initiates a new authentication.
            for name in names:
                status,_=self.read(self.prefix+name)
                if status==(0,0):
                    self.checked(0x000f,b'\0'+name.encode()+b'\0')
                    self.checked(0x0012,b'\0\xff')
                    status,_=self.read(self.prefix+name)
                if status!=self.missing: raise TransportError('临时文件清理未确认：'+name)


class LibusbAdapter:
    def __init__(self):
        missing=[n for n,ok in dependencies().items() if not ok]
        if missing: raise TransportError('USB 依赖未安装：'+', '.join(missing))
        import usb.core
        import usb.util
        import libusb_package
        self.core,self.util=usb.core,usb.util
        self.backend=libusb_package.get_libusb1_backend()
        if self.backend is None: raise TransportError('libusb 动态库未加载')

    def list(self):
        try:
            return [d for d in self.core.find(find_all=True,idVendor=VENDOR,backend=self.backend)
                    if d.idProduct in (NORMAL,SERVICE)]
        except self.core.USBError as error: raise usb_error(error) from error

    def open(self,device):
        from pmca.usb.driver.generic import GenericUsbDriver,MscBbbDriver,MscCbiDriver
        from pmca.usb.driver.generic.libusb import UsbBackend
        try:
            interface=device.get_active_configuration()[(0,0)]
            expected=8 if device.idProduct==NORMAL else 255
            if interface.bInterfaceClass!=expected: raise TransportError('USB 接口类型不符')
            # Use only the current interface; never a whole-device reset.
            if sys.platform.startswith('linux') and device.is_kernel_driver_active(0):
                device.detach_kernel_driver(0)
            self.util.claim_interface(device,0)
            class Backend(UsbBackend):
                def reset(self): pass
            backend=Backend(device)
            if device.idProduct==NORMAL:
                if interface.bInterfaceProtocol==0x50: cls=MscBbbDriver
                elif interface.bInterfaceProtocol in (0,1): cls=MscCbiDriver
                else: raise TransportError('不支持此大容量存储协议')
            else: cls=GenericUsbDriver
            driver=cls(backend)
            device.default_timeout=12000
            return driver
        except Exception as error:
            self.close(device)
            if isinstance(error,self.core.USBError): raise usb_error(error) from error
            raise

    def close(self,device):
        self.util.dispose_resources(device)

    def normal_identity(self,driver):
        from pmca.usb import MscDevice
        from pmca.usb.sony import SonyExtCmdCamera,SonyMscExtCmdDevice,isSonyMscCamera
        if not isSonyMscCamera(MscDevice(driver).getDeviceInfo()): raise TransportError('设备不是 Sony 相机')
        info=SonyExtCmdCamera(SonyMscExtCmdDevice(driver)).getCameraInfo()
        if info.modelName!='ILCE-7M3': raise TransportError('只支持 ILCE-7M3')

    def authenticate(self,driver):
        from pmca.usb.sony import SonySenserAuthDevice
        auth=SonySenserAuthDevice(driver)
        auth.start()
        try: auth.authenticate()
        except Exception:
            auth.stop()
            raise
        return auth

    def camera(self,driver):
        from pmca.usb.sony import SonySenserCamera,SonySenserDevice
        return SonySenserCamera(SonySenserDevice(driver))


@contextmanager
def connect(*,allow_switch=False,adapter=None,progress=lambda message:None,timeout=40):
    adapter=adapter or LibusbAdapter()
    devices=adapter.list()
    if len(devices)!=1: raise TransportError('请只连接一台 A7M3；当前目标数量：'+str(len(devices)))
    device=devices[0]
    if device.idProduct==NORMAL:
        if not allow_switch: raise TransportError('相机在大容量存储模式，需先明确同意切换服务模式')
        if sys.platform=='darwin': raise TransportError('Mac 大容量模式仍需 UTM 交接；本入口仅接受已经交回 Mac 的 Sony 服务设备')
        driver=adapter.open(device)
        try:
            adapter.normal_identity(driver)
            progress('已核对 ILCE-7M3，正在切换服务模式')
            adapter.authenticate(driver)
            # Do not stop authentication here: that reverses the mode switch.
        finally: adapter.close(device)
        del driver
        deadline=time.monotonic()+timeout
        while True:
            found=adapter.list()
            if len(found)>1: raise TransportError('切换期间出现多台目标设备，停止')
            if found and found[0].idProduct==SERVICE:
                device=found[0];break
            if time.monotonic()>=deadline:
                raise TransportError('等待 Sony USB Device 超时；检查 054C:0336 驱动，不自动重复切换')
            time.sleep(.1)
    driver=adapter.open(device)
    auth=None
    try:
        auth=adapter.authenticate(driver)
        camera=adapter.camera(driver)
        factory=Factory(camera)
        if bytes(camera.readBackup(0x3e0005))!=b'ILCE-7M3'+bytes(8) or factory.contents('/version.txt')!=BUILD:
            raise TransportError('维护模式机型或内部版本不是匹配的 A7M3 4.04')
        progress('服务模式机型和 4.04 构建号已核对')
        yield camera,factory
    finally:
        try:
            if auth is not None: auth.stop()
        finally: adapter.close(device)
