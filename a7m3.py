#!/usr/bin/env python3
"""Sony A7 III 4.04 菜单实验：备份、构建、QEMU 验证、烧录和恢复。"""
import argparse
import fcntl
import os
from pathlib import Path
import subprocess
import sys

from build_image import DEFAULT_TITLE, build, verify_build
from local import BACKUP, LAB, SETTINGS, require
from qemu_test import payload, test


def path(value):
    return Path(value).expanduser().resolve()


def device(action):
    if action not in ("serial-check", "status"):
        pmca = path(os.environ.get("A7M3_PMCA_DIR", LAB / "Sony-PMCA-RE"))
        require((pmca / "pmca" / "usb" / "sony.py").is_file(),
                "请用 A7M3_PMCA_DIR 指向本地 Sony-PMCA-RE 源码目录。")
        sys.path.insert(0, str(pmca))
        from camera.service import settings_ok
        if action in ("creative-read", "creative-flash", "creative-restore", "creative-verify", "creative-inspect",
                      "creative-fix", "creative-read-fix", "creative-verify-fix", "creative-restore-fix",
                      "creative-identity", "creative-read-identity", "creative-verify-identity", "creative-restore-identity",
                      "creative-icons", "creative-read-icons", "creative-verify-icons", "creative-restore-icons",
                      "creative-icons-list", "creative-read-icons-list", "creative-verify-icons-list", "creative-restore-icons-list"):
            from camera.creative_flash import payload as creative_payload, verified, configure
            operation=configure(action)
            verified(check_image=operation in ("flash","fix","identity","icons","icons-list"))
            creative_payload("write" if operation in ("flash","fix","identity","icons","icons-list") else "restore" if operation=="restore" else "read")
        elif action in ("menu-ram-install", "menu-ram-inspect", "menu-ram-restore"):
            from camera.menu_ram import payload as menu_payload
            menu_payload(action.removeprefix("menu-ram-"))
        elif action in ("settings-snapshot", "settings-runtime-snapshot"):
            if action == "settings-runtime-snapshot":
                payload("runtime")
        elif action == "backup":
            require(not BACKUP.exists() and not BACKUP.with_suffix(".partial").exists(),
                    "已有完整或部分备份；请归档，工具不会覆盖。")
            payload("backup")
        elif action in ("write", "restore"):
            settings_ok(SETTINGS.read_bytes())
            verify_build(check_image=action == "write")
            payload(action)
        else:
            verify_build(check_image=False)
            payload("readback")
    from camera.handoff import run
    run(action)


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    actions = cli.add_subparsers(dest="action", required=True)
    image = actions.add_parser("build", help="从本地备份和原始简体中文资源构建镜像")
    image.add_argument("--resource", type=path, required=True)
    image.add_argument("--title", default=DEFAULT_TITLE)
    qemu = actions.add_parser("qemu-test", help="编译 ARM 载荷并在 QEMU 中验证")
    qemu.add_argument("--kernel", type=path, required=True)
    qemu.add_argument("--busybox", type=path, required=True, help="ARMv7 静态 BusyBox 或 Alpine ARMv7 rootfs 的 bin/busybox")
    qemu.add_argument("--sony-root", type=path, required=True, help="本地解包的 Sony nflasha7_unpacked")
    qemu.add_argument("--read-only", action="store_true", help="只测备份和读回；不需要真机原始备份")
    for name, help_text in (
        ("check", "校验本地镜像和原始分区备份"),
        ("serial-check", "检查 UTM 专用串口，不访问相机"),
        ("status", "检查 UTM 是否看到一台目标相机"),
        ("backup", "从真机读取 BK4 设置和完整 /usr 分区"),
        ("settings-snapshot", "只读获取新的 BK4 设置快照，不覆盖初始备份"),
        ("settings-runtime-snapshot", "只读获取 BK4 和维护进程库布局，供原厂设置调用研究"),
        ("menu-ram-install", "临时添加原厂菜单入口，仅修改运行内存，引用已有风格槽 3"),
        ("menu-ram-inspect", "读取临时菜单入口及调用计数"),
        ("menu-ram-restore", "恢复内存中的原厂菜单入口及分派函数"),
        ("creative-read", "只读检查创意风格补丁涉及的扇区"),
        ("creative-inspect", "只读比较运行内存代码、菜单表和磁盘资源"),
        ("creative-fix", "将已写入的第一版改为打开菜单时初始化，并恢复英文资源"),
        ("creative-read-fix", "只读检查第二版补丁扇区"),
        ("creative-verify-fix", "重启后回读第二版补丁和三个文件"),
        ("creative-restore-fix", "恢复到第二版写入前的第一版文件"),
        ("creative-icons", "修复复古衣橱在 Fn、列表与选择页中的 RW 图标"),
        ("creative-read-icons", "只读检查 RW 图标补丁扇区"),
        ("creative-verify-icons", "重启后回读 RW 图标资源、代码及原配方"),
        ("creative-restore-icons", "恢复 RW 图标修复前的 v3"),
        ("creative-icons-list", "补齐复古衣橱的竖向列表及第 3 槽图标"),
        ("creative-read-icons-list", "只读检查竖向列表图标补丁扇区"),
        ("creative-verify-icons-list", "验证竖向列表图标、原有菜单与配方"),
        ("creative-restore-icons-list", "恢复竖向列表补丁前的第一版 RW 图标"),
        ("creative-identity", "在第二版基础上修复 Fn 名称及重新进入创意风格时的定位"),
        ("creative-read-identity", "只读检查第三版补丁扇区"),
        ("creative-verify-identity", "重启后验证第三版文件、运行代码与配方"),
        ("creative-restore-identity", "恢复第三版写入前的第二版，保留新增入口与配方"),
        ("creative-flash", "烧录通过原厂组件测试的创意风格入口、配方和名称补丁"),
        ("creative-verify", "重启后回读创意风格扇区及三个完整文件"),
        ("creative-restore", "恢复创意风格补丁前的十个扇区，保留此前标题修改"),
        ("flash", "仅烧录菜单标题补丁并回读；不包含创意风格"),
        ("verify", "重启后读取扇区和菜单，校验改版"),
        ("restore", "写回原始扇区并回读"),
        ("verify-original", "重启后读取扇区和菜单，校验原版"),
    ):
        action = actions.add_parser(name, help=help_text)
        if name in ("flash", "restore", "creative-flash", "creative-restore", "creative-fix", "creative-restore-fix",
                    "creative-identity", "creative-restore-identity", "creative-icons", "creative-restore-icons",
                    "creative-icons-list", "creative-restore-icons-list"):
            action.add_argument("--write-device", action="store_true", required=True)
    args = cli.parse_args()
    os.umask(0o077)
    LAB.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        with (LAB / ".lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if args.action == "build":
                build(args.resource, args.title)
            elif args.action == "qemu-test":
                test(args.kernel, args.busybox, args.sony_root, args.read_only)
            elif args.action == "check":
                verify_build()
                print("本地镜像和备份校验通过。")
            else:
                if args.action in ("flash", "restore"):
                    print(f"真机写入操作：{args.action}；请保持电量和 USB 连接。", flush=True)
                    print("范围：菜单标题资源扇区；不包含创意风格或成像处理修改。", flush=True)
                device("write" if args.action == "flash" else args.action)
                if args.action in ("flash", "restore"):
                    print("写入已回读。请关机、断开 USB、重新开机后运行对应的校验命令。")
        return 0
    except (OSError, ValueError, ImportError, KeyError, subprocess.SubprocessError) as exc:
        print(f"未通过：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
