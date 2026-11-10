#!/usr/bin/env python3
"""Build a diskless local UTM USB lab from user-provided Alpine and PMCA files."""
import argparse
import gzip
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import uuid
import zlib

from local import LAB, ROOT, require


def kernel_image(path):
    data = path.read_bytes()
    if data[0x38:0x3c] != b"ARM\x64":
        offset = data.find(b"\x1f\x8b\x08")
        require(offset >= 0, "Expected ARM64 Image or a gzip-wrapped Alpine vmlinuz-virt.")
        data = zlib.decompress(data[offset:], wbits=31)
    require(data[0x38:0x3c] == b"ARM\x64", "Expected ARM64 Linux Image.")
    return data


def prepare(args):
    image = kernel_image(args.kernel)
    require((args.pmca / "pmca/usb/sony.py").is_file(), "Expected a Sony-PMCA-RE checkout.")
    packages = sorted(args.apks.glob("*.apk"))
    require(all(any(p.name.startswith(prefix) for p in packages)
                for prefix in ("python3-", "py3-usb-", "py3-pycryptodome-", "libusb-")),
            "The offline APK directory needs Python, PyUSB, pycryptodome, libusb and their dependencies.")
    LAB.mkdir(parents=True, exist_ok=True)
    dest = LAB / "A7 III USB Lab.utm"
    require(not dest.exists(), f"{dest} already exists.")
    with tempfile.TemporaryDirectory(dir=LAB) as scratch:
        tmp = Path(scratch)
        overlay = tmp / "overlay"
        apkdir = overlay / "lab/apks"
        apkdir.mkdir(parents=True)
        shutil.copy2(ROOT / "camera/usb-lab-init", overlay)
        shutil.copyfile(args.apk_static, overlay / "lab/apk.static")
        (overlay / "lab/apk.static").chmod(0o755)
        shutil.copytree(args.pmca / "pmca", overlay / "lab/sony-pmca/pmca",
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        for package in packages:
            shutil.copyfile(package, apkdir / package.name)
        archive = tmp / "overlay.cpio"
        with archive.open("wb") as out:
            subprocess.run([shutil.which("bsdtar") or "tar", "-c", "--format=newc", "-f", "-", "."],
                           cwd=overlay, stdout=out, check=True, env={**os.environ, "COPYFILE_DISABLE": "1"})
        vm = tmp / dest.name
        data = vm / "Data"
        data.mkdir(parents=True)
        (data / "Image").write_bytes(image)
        with (data / "usb-lab-initramfs").open("wb") as out:
            with args.initrd.open("rb") as base:
                shutil.copyfileobj(base, out)
            with archive.open("rb") as source, gzip.GzipFile(fileobj=out, mode="wb", mtime=0) as gz:
                shutil.copyfileobj(source, gz)
        config = {
            "Backend": "Apple", "ConfigurationVersion": 4,
            "Information": {"Name": "A7 III USB Lab", "Notes": "Offline USB experiment",
                            "UUID": str(uuid.uuid4()).upper(), "IconCustom": False},
            "Display": [], "Drive": [], "Network": [],
            "Serial": [{"Mode": "Terminal", "Terminal": {"BackgroundColor": "#000000", "FontColor": "#ffffff",
                       "Font": "Menlo", "FontSize": 12, "CursorBlink": True}}, {"Mode": "Ptty"}],
            "System": {"Architecture": "aarch64", "CPUCount": 2, "MemorySize": 768,
                       "Boot": {"OperatingSystem": "Linux", "LinuxKernelPath": "Image",
                                "LinuxInitialRamdiskPath": "usb-lab-initramfs",
                                "LinuxCommandLine": "console=hvc0 rdinit=/usb-lab-init quiet panic=1"}},
            "Virtualization": {"Audio": False, "Balloon": False, "Entropy": True,
                               "Keyboard": "Disabled", "Pointer": "Disabled"},
        }
        with (vm / "config.plist").open("wb") as out:
            plistlib.dump(config, out)
        vm.rename(dest)
    print(dest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("kernel", "initrd", "apk-static", "apks", "pmca"):
        parser.add_argument(f"--{flag}", type=lambda value: Path(value).expanduser().resolve(), required=True)
    try:
        prepare(parser.parse_args())
    except (OSError, ValueError, zlib.error, subprocess.SubprocessError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == "__main__":
    main()
