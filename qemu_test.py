"""Run the ARM payloads against a disposable disk fixture in an isolated QEMU guest."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zlib

from build_image import compile_payloads
from local import LAB, ROOT, OFFSET, atomic, file_sha, require, sha

MARKERS = {"readback": "QEMU_READBACK_OK", "backup": "QEMU_BACKUP_OK",
           "write": "QEMU_WRITE_OK", "restore": "QEMU_RESTORE_OK"}
LIBS = {"ld-linux.so.3": "ld-2.11.2.so", "libc.so.6": "libc-2.11.2.so",
        "libcrypt.so.1": "libcrypt-2.11.2.so", "librt.so.1": "librt-2.11.2.so",
        "libpthread.so.0": "libpthread-2.11.2.so"}


def payload(name):
    path = LAB / f"{name}.so"
    witnesses = json.loads((LAB / "qemu-tests.json").read_text())
    log = (LAB / "qemu.log").read_text()
    content = path.read_bytes()
    require(0 < len(content) <= 16384 and content[:6] == b"\x7fELF\x01\x01" and
            content[16:20] == b"\x03\0(\0", "载荷不是预期的 ARM32 共享对象。")
    require(sha(content) == witnesses["payloads"].get(name) and MARKERS[name] in log and
            "QEMU_ALL_TESTS_PASSED" in log, f"{name} 尚未通过 QEMU。")
    if name in ("write", "restore"):
        require(witnesses.get("patch_sha256") == file_sha(LAB / "patch.json"),
                "镜像构建清单已改变。请重新运行 qemu-test，再写入真机。")
    return content


def test(kernel, busybox, sony_root, read_only):
    compile_payloads(not read_only)
    enabled = ("readback", "backup") if read_only else tuple(MARKERS)
    patch_digest = None if read_only else file_sha(LAB / "patch.json")
    with tempfile.TemporaryDirectory(dir=LAB) as temporary:
        tmp = Path(temporary)
        fs = tmp / "root"
        for name in ("bin", "sony/bin", "sony/lib", "sony/dev", "sony/proc", "sony/tmp/jiritsu", "payloads"):
            (fs / name).mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / "qemu/init", fs / "init")
        shutil.copyfile(busybox, fs / "bin/busybox")
        musl = busybox.parent.parent / "lib/ld-musl-armhf.so.1"
        if musl.is_file():
            (fs / "lib").mkdir()
            shutil.copy2(musl, fs / "lib/ld-musl-armhf.so.1")
            (fs / "lib/libc.musl-armv7.so.1").symlink_to("ld-musl-armhf.so.1")
        shutil.copyfile(sony_root / "bin/busybox", fs / "sony/bin/busybox")
        for path in (fs / "bin/busybox", fs / "sony/bin/busybox"):
            path.chmod(0o755)
        for link, original in LIBS.items():
            shutil.copyfile(sony_root / "lib" / original, fs / "sony/lib" / link)
            (fs / "sony/lib" / link).chmod(0o755)
        header = bytearray(2048)
        header[1080:1082] = b"\x53\xef"
        header = bytes(header) if read_only else (LAB / "header.bin").read_bytes()
        before = bytes(range(256)) * 2 if read_only else (LAB / "before.bin").read_bytes()
        (fs / "header.bin").write_bytes(header)
        (fs / "before.bin").write_bytes(before)
        if not read_only:
            shutil.copyfile(LAB / "after.bin", fs / "after.bin")
        # The write offset is beyond the first chunk; that chunk has only the header.
        require(OFFSET >= 4 * 1024 * 1024, "Backup fixture layout changed.")
        (fs / "crc.txt").write_text(f"{zlib.crc32(header.ljust(4 * 1024 * 1024, bytes(1))):08x}\n")
        witnesses = {}
        for name in enabled:
            path = fs / "payloads" / f"{name}.so"
            shutil.copyfile(LAB / path.name, path)
            witnesses[name] = file_sha(path)
        initrd = tmp / "initrd.cpio"
        with initrd.open("wb") as out:
            subprocess.run([shutil.which("bsdtar") or "tar", "-c", "--format=newc", "-f", "-", "."], cwd=fs, stdout=out, check=True,
                           env={**os.environ, "COPYFILE_DISABLE": "1"})
        cmd = [os.environ.get("A7M3_QEMU", "qemu-system-arm"), "-M", "virt", "-cpu", "cortex-a15",
               "-m", "768", "-display", "none", "-serial", "stdio", "-monitor", "none", "-nic", "none",
               "-no-reboot", "-kernel", str(kernel), "-initrd", str(initrd), "-append",
               "console=ttyAMA0 rdinit=/init quiet panic=1"]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=35)
        except subprocess.TimeoutExpired as exc:
            atomic(LAB / "qemu.log", exc.stdout or b"")
            raise
        atomic(LAB / "qemu.log", result.stdout)
        text = result.stdout.decode(errors="replace")
        print(text, end="")
        require(result.returncode == 0 and "QEMU_ALL_TESTS_PASSED" in text and
                all(MARKERS[name] in text for name in enabled) and
                (read_only or "QEMU_WRONG_PREIMAGE_REFUSED" in text), "QEMU 测试失败。")
        proof = {"payloads": witnesses, "patch_sha256": patch_digest}
        atomic(LAB / "qemu-tests.json", (json.dumps(proof, indent=2) + "\n").encode())
