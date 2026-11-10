# 构建、烧录、验证与恢复

适用范围：Sony **ILCE-7M3 4.04**，机身内部构建标识 `37114_13.2026020901`。当前实现修改简体中文资源中的两条标题记录。其他型号、版本、磁盘布局以及任意分区写入不受支持。请只对自己有权操作的机身使用。

## 1. 准备本地资料

- Python 3.9 或以上、QEMU（`qemu-system-arm`）、GNU Arm Embedded Toolchain（`arm-none-eabi-gcc` 和 `arm-none-eabi-ld`）、支持 newc 的 BSD tar。
- 真机通道需要 Apple Silicon Mac、带 Apple Virtualization USB 直通的 UTM、libusb、Micro‑USB 数据线和充足电量。这条 USB 路径实测于 macOS 27.2 / UTM 5.0.8。兼容性见 [UTM USB 文档](https://docs.getutm.app/guest-support/sharing/usb/)。
- QEMU 测试使用 [Alpine ARMv7](https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/armv7/) 的 Linux `vmlinuz-lts`，以及解开的 ARMv7 minirootfs 的 `bin/busybox`（脚本同时读取其相邻的 `lib/ld-musl-armhf.so.1`）；也可提供静态链接的 ARMv7 BusyBox。请保留文件的执行权限。
- 从 [Sony Mac 4.04](https://support.sony.jp/electronics/support/software/00380674) 安装镜像只读提取 `FirmwareData_ILCE7M3V404.dat`；无需运行更新器。用 [fwtool.py](https://github.com/ma1co/fwtool.py/tree/cdba742b73eed5981480c326aeb30033aabf0223) 解包。本项目直接测试了 Mac 包中的 DAT；Windows EXE 不作为解包输入。

```sh
git clone https://github.com/robinshie/Sony_A7M3.git
cd Sony_A7M3
mkdir -p .lab
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
git clone https://github.com/ma1co/fwtool.py.git .lab/fwtool
git -C .lab/fwtool checkout cdba742b73eed5981480c326aeb30033aabf0223
python -m pip install -r .lab/fwtool/requirements.txt
git clone https://github.com/ma1co/Sony-PMCA-RE.git .lab/Sony-PMCA-RE

shasum -a 256 .lab/FirmwareData_ILCE7M3V404.dat
python .lab/fwtool/fwtool.py unpack -f .lab/FirmwareData_ILCE7M3V404.dat -o .lab/sony-4.04
export A7M3_FIRMWARE_ROOT="$PWD/.lab/sony-4.04/firmware.tar_unpacked"
sony_dev="$A7M3_FIRMWARE_ROOT/0700_part_image/dev"
```

实测 DAT 的 SHA‑256：`7f5c9597ee8ceb5a80255976a6e8cd8035639b4362dd7bd328ca2f6401846bda`。如果解包后没有 `nflasha7_unpacked` 和 `nflasha15_unpacked`，请先核对 DAT 版本和解包输出。

所有中间文件默认保存在 `.lab/`。可用 `A7M3_LAB` 指向独立目录；为每台相机保留独立的目录和备份。也可用 `A7M3_ARM_CC`、`A7M3_ARM_LD`、`A7M3_QEMU` 指定本机工具路径。

## 2. 准备 UTM USB 实验机

`prepare_utm.py` 从本机已有的 [Alpine aarch64 virt](https://dl-cdn.alpinelinux.org/alpine/v3.22/releases/aarch64/) 和 [Sony-PMCA-RE](https://github.com/ma1co/Sony-PMCA-RE) 生成离线、无虚拟硬盘的 `.utm` 包。需要 virt ISO 中的 `boot/vmlinuz-virt` 和 `boot/initramfs-virt`，以及同一 Alpine 发行版 aarch64 的离线 APK。可在一台同发行版的 Alpine aarch64 环境启用 main 和 community 后用 `apk fetch --recursive --output /path/to/apks python3 py3-usb py3-pycryptodome libusb apk-tools-static` 下载完整依赖。用 BSD tar 从 `apk-tools-static` 包提取 `sbin/apk.static`。不要混用发行版或架构。

```sh
python prepare_utm.py \
  --kernel .lab/alpine-virt/boot/vmlinuz-virt \
  --initrd .lab/alpine-virt/boot/initramfs-virt \
  --apk-static .lab/apk-static/sbin/apk.static \
  --apks .lab/apks --pmca .lab/Sony-PMCA-RE
open ".lab/A7 III USB Lab.utm"
```

在 UTM 启动 `A7 III USB Lab`，等客机显示 `USB_LAB_READY`。主机侧通过 UTM 的第二个 PTY（串口索引 1）与离线客机通讯。这个串口是该实验机专用的本地 Shell；不要把它指向有其他用途的虚拟机。若 UTM 装在其他位置，设置 `A7M3_UTMCTL`；客机名字改过则设置 `A7M3_VM`。主机使用 Homebrew libusb，非默认安装可以用 `A7M3_LIBUSB` 指定 dylib，另放的 PMCA 源码可以用 `A7M3_PMCA_DIR` 指定。

```sh
python a7m3.py serial-check
```

用 Micro‑USB 接相机，设为「大容量存储」。在 macOS 顶部「虚拟机配件」把 `ILCE-7M3` 分给 UTM，再运行 `python a7m3.py status`。相机必须是唯一一台目标 Sony 设备。工具经维护命令切换 USB 模式并将接口交回 Mac，普通 USB 存储卷只是 SD 卡和 PMHOME。

## 3. 备份并构建

先用一次只读 QEMU 测试验证备份和读回载荷；以下路径中的 ARMv7 内核和 rootfs 由你本地提供：

```sh
python a7m3.py qemu-test --read-only \
  --kernel .lab/armv7/vmlinuz-lts \
  --busybox .lab/armv7/root/bin/busybox \
  --sony-root "$sony_dev/nflasha7_unpacked"

python a7m3.py backup
```

`backup` 保存并核对 BK4 设置备份，再读取 300 MiB 的 `/dev/nflasha15`，逐块验证 75 个 4 MiB 块的 CRC。它不会覆盖已有完整备份或部分文件。已拥有同一台机身的原始备份时，可将 `a7m3-live-usr-nflasha15.bin` 与 `a7m3-settings-backup.bin` 复制到 `.lab/`，无需再读一次。请另存一份完整原始备份。

```sh
python a7m3.py build \
  --resource "$sony_dev/nflasha15_unpacked/share/app/string_simplifiedchinese.uxc" \
  --title '我的相机/固件实验'
python a7m3.py check
python a7m3.py qemu-test \
  --kernel .lab/armv7/vmlinuz-lts \
  --busybox .lab/armv7/root/bin/busybox \
  --sony-root "$sony_dev/nflasha7_unpacked"
```

标题必须是「四个汉字/四个汉字」，保持 UTF‑8 字节长度和原文件布局；请先在 [QEMU 菜单实验](ui.md) 里确认字体能显示。构建不需要 USB，生成 `a7m3-4.04-usr-custom.img` 和 `patch.json`。QEMU 以隔离的 ARM Linux 虚拟机检查这套具体载荷，测试用的是可丢弃的文件而非真机。每次改标题重建后，都要重新执行完整 `qemu-test`。

## 4. 写入与回读

```sh
python a7m3.py verify-original
python a7m3.py flash --write-device
# 关机并断开 USB，重新开机，在简体中文 MENU 的拍摄设置 1 第一页检查标题。
# 之后重新接入 UTM 并恢复大容量存储模式：
python a7m3.py verify
```

写入前会核对型号、内部固件构建标识、原始备份、分区容量、分区头、目标扇区原始字节及 QEMU 记录。只写入一个 512 字节扇区，随后同步和读回；写入或即时读回异常时载荷会尝试写回原字节。**写入过程中不要关机或拔线。** 若命令中断或失败，先读回检查状态，不要直接重试写入。相机无法启动或进入 USB 维护模式时，这个工具无法恢复。

## 5. 恢复

```sh
python a7m3.py restore --write-device
# 关机断开 USB、重开后重新连接：
python a7m3.py verify-original
```

保留刷写时的 `patch.json`、原始备份和 QEMU 校验文件。恢复仅接受与当时改版完全匹配的目标扇区。想换另一套标题时先恢复原版，重启并校验后再构建新改版。若 USB 切换超时但从未报告写入，检查虚拟机和线缆状态；若需要断电重启，先按 [Sony 断开 USB 的说明](https://helpguide.sony.net/ilc/1720/v1/en/contents/TP0001629824.html) 确保存取灯熄灭。
