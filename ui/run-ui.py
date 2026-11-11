#!/usr/bin/env python3
"""Launch the separate ILCE-7M3 layout verification guest in QEMU."""
import argparse
import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent
DEFAULT_QEMU = os.environ.get("A7M3_QEMU", "qemu-system-arm")

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--qemu", type=Path, default=DEFAULT_QEMU)
    p.add_argument("--guest", type=Path, default=ROOT / "build/a7m3-ui.elf")
    p.add_argument("--serial", type=Path)
    p.add_argument("--qmp", type=Path)
    p.add_argument("--headless", action="store_true")
    p.add_argument("--display", default="cocoa,zoom-to-fit=on")
    p.add_argument("--name", default="Sony A7 III - 界面验证 (简体中文 / English)")
    a = p.parse_args()
    qemu = shutil.which(str(a.qemu.expanduser()))
    if not qemu:
        p.error("qemu-system-arm not found; set --qemu.")
    if not a.guest.is_file():
        p.error("Guest image missing; build with python3 build.py first.")
    cmd = [
        qemu, "-name", a.name,
        "-M", "realview-pbx-a9", "-smp", "1", "-m", "256",
        "-nodefaults", "-audio", "none", "-nic", "none", "-monitor", "none",
        "-display", "none" if a.headless else a.display,
        "-serial", f"file:{a.serial.resolve()}" if a.serial else "null",
        "-device", f"loader,file={a.guest.resolve()},cpu-num=0",
    ]
    if a.qmp:
        cmd.extend(["-qmp", f"unix:{a.qmp.resolve()},server=on,wait=off"])
    os.execv(qemu, cmd)

if __name__ == "__main__":
    main()
