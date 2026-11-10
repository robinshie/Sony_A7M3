"""Construct a guarded one-sector patch from a local stock camera backup."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

from local import (LAB, BACKUP, IMAGE, TOTAL, PREFIX, OFFSET, ROOT, STOCK_SHA, STOCK_MENU_SHA,
                   atomic, file_sha, require, sha)

DEFAULT_TITLE = "我的相机/固件实验"
ORIGINAL = "影像质量/影像尺寸".encode()
MARKERS = ((0x4F7E6, b""), (0x4F7E7, b"${v1}"))


def replace_menu(source, title):
    require(re.fullmatch(r"[\u4e00-\u9fff]{4}/[\u4e00-\u9fff]{4}", title),
            "标题格式为「四个汉字/四个汉字」。")
    result = bytearray(source)
    found = 0
    for key, suffix in MARKERS:
        lead = key.to_bytes(3, "little") + b"\x1e"
        marker = lead + ORIGINAL + suffix + b"\0"
        require(source.count(marker) == 1, f"原始资源记录 {key:#x} 缺失或不唯一。")
        start = source.index(marker) + len(lead)
        result[start:start + len(ORIGINAL)] = title.encode()
        found += 1
    require(found == 2 and result != source, "没有需要写入的标题变化。")
    return bytes(result)


def image_record():
    return json.loads((LAB / "patch.json").read_text())


def build(resource, title):
    require(BACKUP.stat().st_size == TOTAL and file_sha(BACKUP, PREFIX) == STOCK_SHA,
            "需要这台相机的完整原始分区备份，并且其 ext2 内容须匹配 Sony 4.04。")
    menu = resource.read_bytes()
    require(sha(menu) == STOCK_MENU_SHA, "需要从官方 4.04 提取的简体中文菜单资源。")
    edited_menu = replace_menu(menu, title)
    with BACKUP.open("rb") as stream:
        header = stream.read(2048)
        stream.seek(OFFSET)
        old = stream.read(512)
    new = replace_menu(old, title)
    original_hash = file_sha(BACKUP)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=LAB, delete=False) as output:
            temp = Path(output.name)
            with BACKUP.open("rb") as source:
                shutil.copyfileobj(source, output, 4 * 1024 * 1024)
            output.seek(OFFSET)
            require(output.write(new) == 512, "镜像写入不完整。")
            output.flush()
            os.fsync(output.fileno())
        with temp.open("rb") as stream:
            stream.seek(OFFSET)
            require(temp.stat().st_size == TOTAL and stream.read(512) == new, "镜像回读不一致。")
        record = dict(model="ILCE-7M3", firmware="4.04", partition="/dev/nflasha15", offset=OFFSET,
                      partition_bytes=TOTAL, title=title, backup_sha256=original_hash,
                      original_sector_sha256=sha(old), modified_sector_sha256=sha(new),
                      original_menu_sha256=STOCK_MENU_SHA, modified_menu_sha256=sha(edited_menu),
                      header_sha256=sha(header), changed_bytes=sum(a != b for a, b in zip(old, new)),
                      image_sha256=file_sha(temp), image_ext2_sha256=file_sha(temp, PREFIX))
        for name, data in (("header.bin", header), ("before.bin", old), ("after.bin", new)):
            atomic(LAB / name, data)
        os.replace(temp, IMAGE)
        atomic(LAB / "patch.json", (json.dumps(record, ensure_ascii=False, indent=2) + "\n").encode())
    finally:
        if temp:
            temp.unlink(missing_ok=True)
    print(json.dumps(record, ensure_ascii=False, indent=2))


def verify_build(check_image=True):
    record = image_record()
    require((record["model"], record["firmware"], record["partition"], record["offset"],
             record["partition_bytes"]) == ("ILCE-7M3", "4.04", "/dev/nflasha15", OFFSET, TOTAL),
            "目标设备或分区不匹配。")
    require(BACKUP.stat().st_size == TOTAL and file_sha(BACKUP) == record["backup_sha256"] and
            file_sha(BACKUP, PREFIX) == STOCK_SHA, "原始备份 SHA-256 不匹配。")
    with BACKUP.open("rb") as source:
        header = source.read(2048)
        source.seek(OFFSET)
        old = source.read(512)
    new = replace_menu(old, record["title"])
    for name, data, key in (("header.bin", header, "header_sha256"), ("before.bin", old, "original_sector_sha256"),
                            ("after.bin", new, "modified_sector_sha256")):
        require((LAB / name).read_bytes() == data and sha(data) == record[key], f"{name} 校验失败。")
    if check_image:
        require(IMAGE.stat().st_size == TOTAL and file_sha(IMAGE) == record["image_sha256"],
                "改版分区镜像 SHA-256 不匹配。")
    return record


def compile_payloads(include_write):
    cc = os.environ.get("A7M3_ARM_CC", "arm-none-eabi-gcc")
    ld = os.environ.get("A7M3_ARM_LD", "arm-none-eabi-ld")
    src = ROOT / "payloads"
    flags = ["-mcpu=cortex-a9", "-marm", "-mfloat-abi=soft", "-Os", "-fPIC",
             "-ffreestanding", "-fno-builtin", "-fno-stack-protector",
             "-fno-unwind-tables", "-fno-asynchronous-unwind-tables"]
    jobs = {"readback": ("a7-readback-probe.c", []), "backup": ("a7-partition-backup.c", []),
            "runtime": ("a7-runtime-probe.c", [])}
    with tempfile.TemporaryDirectory(dir=LAB) as work:
        tmp = Path(work)
        if include_write:
            verify_build()
            asm = tmp / "sectors.S"
            names = (("expected_header", "header.bin"), ("stock_sector", "before.bin"),
                     ("custom_sector", "after.bin"))
            for _, name in names:
                shutil.copyfile(LAB / name, tmp / name)
            asm.write_text('.section .rodata.sectors,"a"\n.balign 4\n' + "".join(
                f'.global {label}\n.hidden {label}\n{label}:\n.incbin "{name}"\n'
                for label, name in names) + '.section .note.GNU-stack,"",%progbits\n')
            subprocess.run([cc, *flags, "-c", str(asm), "-o", "sectors.o"], cwd=tmp, check=True)
            jobs.update(write=("a7-sector-update.c", []), restore=("a7-sector-update.c", ["-DRESTORE"]))
        for action, (source, defines) in jobs.items():
            subprocess.run([cc, *flags, *defines, "-c", str(src / source), "-o", "main.o"], cwd=tmp, check=True)
            inputs = ["main.o"] + (["sectors.o"] if action in ("write", "restore") else [])
            subprocess.run([ld, "-shared", "--no-undefined", "-z", "noexecstack", "-o", "payload.so", *inputs],
                           cwd=tmp, check=True)
            atomic(LAB / f"{action}.so", (tmp / "payload.so").read_bytes())
            print(f"{action}: {file_sha(LAB / f'{action}.so')}")
