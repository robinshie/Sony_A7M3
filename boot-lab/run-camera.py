#!/usr/bin/env python3
"""Boot the original A7M3 4.04 kernel and initrd in the local QEMU lab."""
import argparse
import json
import os
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIRMWARE = Path(os.environ.get("A7M3_FIRMWARE_ROOT", REPO / ".lab/firmware.tar_unpacked"))
SOURCES = {
    "main": "0700_part_image/dev/nflasha3_unpacked",
    "updater": "0400_updater/dev/nflasha1_unpacked/boot",
}
SHIM = 0x1000
ATAGS = 0x100
KEMCO = 0x00103000
KERNEL = 0x00108000
INITRD = 0x00700000
LOGO = "0700_part_image/dev/nflasha15_unpacked/share/startbinary/logo.bin"
LCD_BASE = 0x50000000
FRAMEBUFFER = 254 << 20
LOGO_WIDTH = 640
LOGO_HEIGHT = 480

def words(*args):
    return struct.pack("<" + "I" * len(args), *args)

def loader(file, addr, cpu=False):
    return ["-device", f"loader,file={file},addr={addr:#x},force-raw=on" + (",cpu-num=0" if cpu else "")]

def boot_shim(show_logo):
    # The lab shim writes the test display registers, then starts the Sony kernel.
    code, literals = [], []

    def load_constant(register, value):
        literals.append((len(code), register, value))
        code.append(0)

    if show_logo:
        load_constant(3, LCD_BASE)
        for offset, value in [
            (0x00, (LOGO_WIDTH // 16 - 1) << 2),
            (0x04, LOGO_HEIGHT - 1),
            (0x10, FRAMEBUFFER),
            (0x18, 0x82B),  # Power on, TFT, RGB byte order, 32 bpp, enable.
        ]:
            load_constant(0, value)
            code.append(0xE5830000 | offset)  # STR r0, [r3, #offset]
        code.append(0xF57FF04F)  # DSB SY
    code.append(0xE3A00000)  # MOV r0, #0
    for register, value in [(1, 0xDA9), (2, ATAGS), (15, KERNEL)]:
        load_constant(register, value)
    for index, register, value in literals:
        offset = 4 * (len(code) - index - 2)
        assert 0 <= offset < 0x1000
        code[index] = 0xE59F0000 | (register << 12) | offset
        code.append(value)
    return words(*code)

def make_framebuffer(source, destination):
    magick = shutil.which("magick") or "/opt/homebrew/bin/magick"
    if not Path(magick).is_file():
        raise SystemExit("ImageMagick (magick) is required to decode the original JPEG.")
    rgba = subprocess.check_output([
        magick, f"jpeg:{source}", "-alpha", "on", "-depth", "8", "rgba:-",
    ])
    if len(rgba) != LOGO_WIDTH * LOGO_HEIGHT * 4:
        raise SystemExit("Unexpected dimensions for the Sony startup image.")
    destination.write_bytes(rgba)

def main():
    root = Path(__file__).resolve().parent
    p = argparse.ArgumentParser()
    p.add_argument("image", nargs="?", choices=SOURCES, default="updater")
    p.add_argument("--firmware", type=Path, default=FIRMWARE, help="unpacked firmware.tar directory")
    p.add_argument("--qemu", type=Path, default=root/"qemu-system-arm-a7m3")
    p.add_argument("--out", type=Path, help="run directory for logs and boot parameters")
    p.add_argument("--headless", action="store_true")
    p.add_argument("--show-boot-logo", action="store_true", help="display Sony's static startup image on the lab LCD")
    p.add_argument("--real-init", action="store_true", help="run Sony init instead of the diagnostic shell")
    p.add_argument("--lpj", action="store_true", help="use Sony's preset delay calibration")
    p.add_argument("--trace", action="store_true")
    p.add_argument("--console-control", action="store_true", help="expose a private local serial test socket")
    args = p.parse_args()
    if args.headless and args.console_control:
        p.error("--console-control requires the Cocoa display")
    firmware = args.firmware.resolve()
    src = firmware / SOURCES[args.image]
    show_logo = args.show_boot_logo
    out = (args.out or REPO / ".lab" / f"run-{args.image}{'-logo' if show_logo else ''}").resolve()
    out.mkdir(parents=True, exist_ok=True)
    if show_logo:
        make_framebuffer(firmware / LOGO, out / "boot-logo.rgba")
    initrd_size = (src/"initrd.img").stat().st_size
    visible_ram = FRAMEBUFFER >> 20 if show_logo else 256
    # The KEMCO block is the boot-argument format expected by the Sony kernel.
    init = "/sbin/init" if args.image == "main" or args.real_init else "/bin/sh"
    command = (
        f"console=ttyAM0,115200 amba2.console=1 ip=off mem={visible_ram}M@0 memrsv=1M@0 "
        f"root=/dev/ram0 initrd={INITRD:#x},{initrd_size:#x} rw init={init} "
        "cgroup_disable=memory panic=0 noalign"
    )
    if args.lpj:
        command += " lpj=1757184"
    if args.image == "main":
        command += " rootfstype=ext2"
    (out/"shim.bin").write_bytes(boot_shim(show_logo))
    (out/"atags.bin").write_bytes(words(
        5, 0x54410001, 1, 4096, 0, 4, 0x54410002, visible_ram << 20, 0,
        4, 0x54420005, INITRD, initrd_size, 0, 0,
    ))
    (out/"kemco.bin").write_bytes(("kemco\n"+command+"\n*\n").encode()+b"\0")
    qmp_dir = None if args.headless else Path(tempfile.mkdtemp(prefix="a7m3-qmp-", dir="/tmp"))
    qmp = str(qmp_dir/"control.sock") if qmp_dir else None
    cmd = [
        str(args.qemu.resolve()), "-name",
        "Sony A7M3 4.04 - original startup image (static)" if show_logo else f"Sony A7M3 4.04 - {args.image} boot lab",
        "-M", "a7m3-lab,lab-lcd=on" if show_logo else "a7m3-lab",
        "-cpu", "cortex-a9,vfp-d32=off,neon=off",
        "-m", "256", "-nodefaults", "-monitor", "none",
        "-nic", "none", "-no-reboot",
    ]
    if qmp:
        cmd += ["-qmp", f"unix:{qmp},server=on,wait=off"]
    serial = out/"serial.log"
    serial_socket = str(qmp_dir/"serial.sock") if args.console_control else None
    if args.headless:
        cmd += ["-display", "none", "-serial", f"file:{serial}"]
    else:
        cmd += ["-display", "cocoa",
                "-chardev", f"vc,id=screen,cols=108,rows=35,logfile={serial}"]
        if serial_socket:
            cmd += ["-chardev", f"socket,id=control,path={serial_socket},server=on,wait=off",
                    "-chardev", "hub,id=hub,chardevs.0=screen,chardevs.1=control",
                    "-serial", "chardev:hub"]
        else:
            cmd += ["-serial", "chardev:screen"]
    if args.trace:
        cmd += ["-d", "int,guest_errors", "-D", str(out/"qemu-trace.log")]
    cmd += loader(out/"shim.bin", SHIM, True) + loader(out/"atags.bin", ATAGS)
    cmd += loader(out/"kemco.bin", KEMCO) + loader(src/"vmlinux.bin", KERNEL)
    cmd += loader(src/"initrd.img", INITRD)
    if show_logo:
        cmd += loader(out/"boot-logo.rgba", FRAMEBUFFER)
    (out/"run.json").write_text(json.dumps({"command": cmd, "qmp": qmp, "serial_socket": serial_socket}, indent=2)+"\n")
    print(f"Serial log: {serial}\nQMP socket: {qmp}", flush=True)
    os.execv(cmd[0], cmd)

if __name__ == "__main__":
    main()
