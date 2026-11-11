"""Host Sony maintenance transport for guarded title and creative-menu updates."""
import io
import json
import os
import struct
import time

import usb.backend.libusb1
import usb.core
import usb.util
from pmca.backup import BackupFile
from pmca.usb.driver.generic import GenericUsbDriver
from pmca.usb.driver.generic.libusb import UsbBackend
from pmca.usb.sony import SonySenserAuthDevice, SonySenserCamera, SonySenserDevice

from build_image import verify_build
from camera.factory_backup import backup_partition
from local import BUILD_ID, LAB, MENU_PATH, SETTINGS, TOTAL, require, sha
from qemu_test import payload


class ClaimedBackend(UsbBackend):
    def reset(self):
        # macOS whole-device capture after a successful claim loses the service interface.
        pass


class Response(bytearray):
    def __init__(self,maximum=1024*1024):
        super().__init__()
        require(0<maximum<=32*1024*1024, "维护响应上限异常。")
        self.maximum=maximum

    def write(self, data):
        require(len(self) + len(data) <= self.maximum, "维护接口返回的数据过大。")
        self.extend(data)


class Factory:
    missing = (0, 0x10000006)
    prefix = "/tmp/jiritsu/"

    def __init__(self, camera):
        self.camera = camera

    def call(self, code, data=b"", maximum=1024*1024):
        reply = Response(maximum)
        result, _ = self.camera.dev.sendSenserPacket(0x40, struct.pack("<HH", 0x1001, code) + data, reply)
        status = struct.unpack_from("<I", reply)[0] if len(reply) >= 4 else None
        return (result, status), bytes(reply[4:])

    def checked(self, code, data=b""):
        status, contents = self.call(code, data)
        require(status == (0, 0), f"维护命令 {code:#06x} 失败：{status!r}")
        return contents

    def read(self, path, maximum=1024*1024):
        return self.call(0x4008, b"\x01\0\0/.." + path.encode("ascii") + b"\0",maximum)

    def contents(self, path, maximum=1024*1024):
        status, result = self.read(path,maximum)
        require(status == (0, 0), f"无法读回 {path}：{status!r}")
        return result

    def select(self, name):
        self.checked(0x000f, b"\0" + name.encode("ascii") + b"\0")

    def run(self, data, report):
        self.checked(0x4002, b"\0\0")
        names = ("libJit.so", report)
        for name in names:
            require(self.read(self.prefix + name)[0] == self.missing, f"临时路径 {name} 已被占用。")
        try:
            self.select("libJit.so")
            self.checked(0x0010, b"\0\xff\0" + data)
            return self.contents(self.prefix + report)
        finally:
            for name in names:
                status, _ = self.read(self.prefix + name)
                if status == (0, 0):
                    self.select(name)
                    self.checked(0x0012, b"\0\xff")
                    status, _ = self.read(self.prefix + name)
                require(status == self.missing, f"无法确认临时文件 {name} 已清理。")


def settings_ok(data):
    require(4096 < len(data) < 16 * 1024 * 1024, "设置备份长度异常。")
    backup = BackupFile(io.BytesIO(data))
    require(backup.revision == 4 and backup.size == len(data), "设置备份不是完整的 BK4。")


def perform(camera, action):
    factory = Factory(camera)
    require(factory.contents("/version.txt") == BUILD_ID, "机身内部版本与已验证的 4.04 不符。")
    print("LIVE_FIRMWARE_BUILD_MATCH", flush=True)
    if action in ("creative-read", "creative-flash", "creative-restore", "creative-verify", "creative-inspect",
                  "creative-fix", "creative-read-fix", "creative-verify-fix", "creative-restore-fix",
                  "creative-identity", "creative-read-identity", "creative-verify-identity", "creative-restore-identity",
                  "creative-icons", "creative-read-icons", "creative-verify-icons", "creative-restore-icons",
                  "creative-icons-list", "creative-read-icons-list", "creative-verify-icons-list", "creative-restore-icons-list",
                  "creative-icons-display", "creative-read-icons-display", "creative-verify-icons-display", "creative-restore-icons-display",
                  "creative-icons-belt", "creative-read-icons-belt", "creative-verify-icons-belt", "creative-restore-icons-belt"):
        from camera.creative_flash import perform as creative_update, configure
        creative_update(camera,factory,configure(action))
        return
    if action in ("menu-ram-install", "menu-ram-inspect", "menu-ram-restore"):
        from camera.menu_ram import perform as menu_experiment
        menu_experiment(camera, factory, action.removeprefix("menu-ram-"))
        return
    if action in ("settings-snapshot", "settings-runtime-snapshot"):
        data = camera.getBackupPresetData(True)
        settings_ok(data)
        directory = LAB / "settings-snapshots"
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        destination = directory / f"settings-{time.time_ns()}.bin"
        with destination.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        settings_ok(destination.read_bytes())
        print(f"LIVE_SETTINGS_SNAPSHOT {destination} bytes={len(data)} sha256={sha(data)}", flush=True)
        if action == "settings-runtime-snapshot":
            raw = factory.run(payload("runtime"), "a7rt.bin")
            require(len(raw) == 67044, "进程布局报告长度异常。")
            magic, maps_n, cmdline_n = struct.unpack_from("<Iii", raw)
            require(magic == 0x41375254 and 0 < maps_n < 65536 and 0 < cmdline_n < 512,
                    f"进程布局读取失败或被截断：{maps_n}, {cmdline_n}")
            for suffix, contents in ((".maps", raw[12:12+maps_n]),
                                     (".cmdline", raw[65548:65548+cmdline_n])):
                with destination.with_suffix(suffix).open("xb") as stream:
                    stream.write(contents)
            print(f"LIVE_RUNTIME_LAYOUT_READ maps={maps_n} cmdline={cmdline_n}", flush=True)
            values=struct.unpack_from("<36I",raw,66060)
            state={"caution_base":values[0],"node_status":values[1],
                   "root":values[2:12],"neutral":values[12:22],"real":values[22:32],
                   "neutral_properties":values[32:34],"real_properties":values[34:36]}
            view=struct.unpack_from("<210I",raw,66204)
            state.update(view_base=view[0],view_status=view[1],mdt_root=view[2:12],
                         mdt_entries=[view[i:i+10] for i in range(12,202,10)],
                         manager=view[202:204],element=view[204:210])
            with destination.with_suffix(".nodes.json").open("x") as stream:
                json.dump(state,stream,indent=2)
            print(f"LIVE_CREATIVE_NODES_READ status={values[1]}",flush=True)
            print(f"LIVE_CREATIVE_MENU_TABLE_READ status={view[1]}",flush=True)
        return
    if action == "backup":
        if not SETTINGS.exists():
            data = camera.getBackupPresetData(True)
            settings_ok(data)
            with SETTINGS.open("xb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        settings_ok(SETTINGS.read_bytes())
        backup_partition(camera)
        return

    patch = verify_build(check_image=action == "write")
    if action in ("write", "restore"):
        settings_ok(SETTINGS.read_bytes())
        raw = factory.run(payload(action), "a7wr.bin")
        require(len(raw) == 552, "写入报告长度异常；先执行只读验证。")
        report = struct.unpack_from("<10i", raw)
        print(f"LIVE_SECTOR_REPORT action={action} {report}", flush=True)
        key = "modified" if action == "write" else "original"
        require(report[:7] == (0x41375752, TOTAL, 1, 1, 512, 0, 1) and
                sha(raw[40:]) == patch[f"{key}_sector_sha256"], "写入未通过，请查看报告再做只读验证。")
        print(f"LIVE_SECTOR_{action.upper()}_VERIFIED sha256={sha(raw[40:])}", flush=True)
        return

    key = "modified" if action == "verify" else "original"
    raw = factory.run(payload("readback"), "a7rdo.bin")
    require(len(raw) == 6696, "读回报告长度异常。")
    magic, _, _, size_rc, head_n, target_n, _, size = struct.unpack_from("<I6i4xQ", raw)
    require((magic, head_n, target_n) == (0x41523731, 2048, 512) and
            (size, size_rc) in ((TOTAL, 0), (0, -25)), "读回的分区布局异常。")
    sector = sha(raw[2088:2600])
    menu = sha(factory.contents(MENU_PATH))
    require(sha(raw[40:2088]) == patch["header_sha256"] and sector == patch[f"{key}_sector_sha256"] and
            menu == patch[f"{key}_menu_sha256"],
            f"机身内容与 {key} 不符：sector={sector} menu={menu}")
    print(f"LIVE_IMAGE_VERIFIED state={key} sector_sha256={sector} menu_sha256={menu}", flush=True)


def connect(action):
    library = os.environ.get("A7M3_LIBUSB", "/opt/homebrew/lib/libusb-1.0.dylib")
    backend = usb.backend.libusb1.get_backend(find_library=lambda _: library)
    require(backend is not None, "找不到 libusb；可通过 A7M3_LIBUSB 指定。")
    deadline = time.monotonic() + 40
    device = None
    seen = False
    failure = None
    print("WAITING_FOR_SONY_SERVICE_USB", flush=True)
    while time.monotonic() < deadline:
        devices = list(usb.core.find(find_all=True, idVendor=0x054c, idProduct=0x0336, backend=backend))
        require(len(devices) <= 1, "检测到多台 Sony 维护设备，停止。")
        if devices:
            if not seen:
                seen = True
                time.sleep(1.2)
                continue
            candidate = devices[0]
            try:
                require(candidate.get_active_configuration()[(0, 0)].bInterfaceClass == 0xff,
                        "维护接口类型与预期不符。")
                usb.util.claim_interface(candidate, 0)
                device = candidate
                break
            except usb.core.USBError as exc:
                failure = exc
                usb.util.dispose_resources(candidate)
                if exc.errno not in (13, 16, 19):
                    raise
        time.sleep(0.08)
    require(device is not None, f"无法打开 Sony 维护 USB：{failure or '未枚举'}。")

    try:
        driver = GenericUsbDriver(ClaimedBackend(device))
        device.default_timeout = 12000 if action.startswith("creative-") or action in ("backup", "settings-snapshot", "settings-runtime-snapshot",
                                                     "menu-ram-install", "menu-ram-inspect", "menu-ram-restore") else 2500
        auth = SonySenserAuthDevice(driver)
        auth.start()
        try:
            auth.authenticate()
            perform(SonySenserCamera(SonySenserDevice(driver)), action)
        finally:
            auth.stop()
    finally:
        usb.util.dispose_resources(device)
