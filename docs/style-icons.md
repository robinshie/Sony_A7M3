# 复古衣橱 RW 图标修复

2026-11-11。v3 已修复名称与列表定位，但图标仍沿用中性风格。本包以精确匹配的 v3 镜像为前置，增加 Fn 的 RW 徽标，以及 MENU 列表和选中页的大小图标。它没有增加 FL 或改变 +1、−1、−1 配方。

第一版已完成写入、断电重启后的整文件直接回读、运行菜单和参数检查；用户补测发现展开后的竖向列表仍显示 Ntrl。第二版补齐该路径，已写入并完成 9 个扇区、26,481,288 字节图标文件直接散列、运行菜单、名称定位和 +1、−1、−1 参数回读。第二版断电重启后的屏幕复测仍待用户确认。

## 第二版：展开后的竖向列表

同一风格使用四组不同尺寸的图标。第一版改了 Fn 的 70×35 图标，并为新增 MENU 项指定了新大小图标，但展开列表另用一张 58×50 资源。原厂 `viewUnified7.so` 文件偏移 `0x8c834` 明确引用 `0x0205c7c8`，因此继续显示第 3 槽的 Ntrl。

本次补齐同一槽位的三个现有资源：`0x0205c7c8`（58×50 竖向列表）、`0x0205c823`（70×60）、`0x0205c87e`（116×100）。后两者在原厂 `viewUnified2.so` 的 `0xa594f8`、`0xa594e8` 有直接引用。既有原厂「中性」及其他样式框的图标保持原样；第一版已正常的 RW 图标也保持原样。

第二版仅修改图像资源文件的 1,632 字节，涉及 9 个扇区，不改菜单代码、文字、选择定位或配方。全部索引、尺寸、数据指针及这三张图以外的字节均逐段比较不变；新流使用各自原有空间，不扩大文件。复用第一版已通过的原厂代码组件证明，并重新运行新包的扇区事务与文件系统检查。

已安装第一版 RW 图标包时，使用以下流程；不能从 v3 直接跳到这个增量包：

```sh
python3 research/style_icons_list.py --usr \
  "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha15_unpacked"
python3 research/build_creative_icons_list.py
python3 research/creative_icons_list_test.py \
  --kernel /path/to/vmlinuz-lts \
  --busybox /path/to/alpine-root/bin/busybox \
  --sony-root "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha7_unpacked"
python3 research/check_creative_image.py .lab/creative-icons-list
# 首次尚未建立直接读取探针时，先运行 research/image_hash_test.py。
python3 a7m3.py creative-icons-list --write-device
# 完整断电、检查竖向列表、在 MENU 中选回复古衣橱，再接回 USB/UTM。
python3 a7m3.py creative-verify-icons-list
```

第二版安装后，日常只读命令为 `creative-read-icons-list` / `creative-verify-icons-list`。恢复到第一版图标包使用 `creative-restore-icons-list --write-device`；若还需恢复到 v3，再按第一版恢复步骤操作。不能用第一版的验收命令判定第二版整文件散列。

第二版目标镜像 SHA-256：`8e8f65c08d15ad1dbbbf362ba0534e6b88194391503f24cb1b8dd94b3fbba405`。图标文件 SHA-256：`b0cd50e8d0fa40b49c8747309412638307c23690ec6ea9194779d1daead8d6ae`。本地包和精确恢复数据位于 `.lab/creative-icons-list/`，资源证明位于 `.lab/style-icons-list/`。

## 第一版构建与验收（v3 → RW 基础包）

已有 v3 的本地镜像与测试记录时，在仓库目录执行以下步骤。原厂资源、内核及运行库均取自本地，不会下载或发布固件。

```sh
python3 research/test_style_icons.py
python3 research/menu_icons.py \
  --usr "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha15_unpacked" \
  --kernel /path/to/vmlinuz-lts \
  --busybox /path/to/alpine-root/bin/busybox \
  --sony-root "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha7_unpacked"
python3 research/build_creative_icons.py
python3 research/creative_icons_test.py \
  --kernel /path/to/vmlinuz-lts \
  --busybox /path/to/alpine-root/bin/busybox \
  --sony-root "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha7_unpacked"
python3 research/check_creative_image.py .lab/creative-icons
python3 research/image_hash_test.py
# 相机接入 UTM；仅适用于已验证的 v3 → 本图标包。
python3 a7m3.py creative-icons --write-device
# 断电重启，分别检查 Fn 与 MENU 的创意风格，再接回 USB/UTM。
python3 a7m3.py creative-verify-icons
```

仅安装第一版时，日常运行 `creative-read-icons` 或 `creative-verify-icons`。完整检查前必须在 MENU → 拍摄设置 1 → 创意风格中选一次复古衣橱，保证原厂延迟初始化的菜单已建立；仅打开 Fn 不能证明 MENU 根节点已初始化。命令不会自动重刷。

恢复到此前的 v3：`python3 a7m3.py creative-restore-icons --write-device`，随后完整断电并使用 v3 的验收流程。上述脚本均绑定本机已保存的镜像和精确散列，不能跨版本套用。

## 图标与布局

| 用途 | 资源 ID | 尺寸 |
| --- | --- | --- |
| Fn 第 3 槽中性图标，当前作为复古衣橱身份 | `0x0205c76d` | 70 × 35 |
| 新增项的选中图标 | `0x0205c049` | 116 × 100 |
| 新增项的列表图标 | `0x0205c04a` | 70 × 60 |

RW 是自行绘制的 5×7 几何字形及方框，不依赖 Sony 字体。选中图标使用橙色，普通图标使用灰白色。仅复古衣橱使用新大小图标，原有 19 个顶层菜单项的图标引用不变。由于身份仍使用「中性 + 第 3 槽」，手动选择该槽的中性同样显示 RW。

`image_cmn_43.uxc` 的格式为固定 16 位索引、图像记录和分块 LZ77 数据；像素为小端 RGBA4444，按 8×8 Morton 顺序排列。编解码器位于 `research/style_icons.py`。使用原文件的严格 SHA-256 前置校验，未识别的九宫格记录原样保留。

资源包大小仍为 26,481,288 字节。第一张资源无损重压缩，腾出 40 字节存放新记录，解码后的所有像素与原版一致；新 RW Fn 图标的短压缩流腾出两张新图标的空间。补丁校验其他常规资源的记录与压缩字节不变；不需要文件系统分配新块。

`viewUnified2.so` 在 `0x005b9a1e` 加入调用，使用已确认的 NOP 空间 `0x005b9ab0` 写入新增菜单项的两个图标 ID。v3 的反向选择、名称识别和原厂参数路径保留。

## 验证范围与缓存差异

- 原厂 ARM 组件测试：256 条分派、34,643 条参数组合、418 条光标路径、91 条 Fn 名称路径，加上新增项两种图标及原 19 项引用检查。
- 编解码测试覆盖块边界、重叠匹配、损坏输入和 Morton 边缘填充；新图标还与本地 fwtool 的独立 LZ77 解码器比较一致。
- 扇区事务测试通过读取、写入、回滚、重复拒绝、恢复、已知混合状态恢复及错误前置内容拒绝。独立 e2fsck 与 debugfs 导出检查通过。
- 原机屏幕、真实图片效果与 ISP 性能不能由这些 QEMU 测试代替。

本轮观察到：断电重启后，图标文件普通读取的索引偏移 `0xa2–0xa5` 仍为旧的 `ff ff ff ff`；以 ARM `O_DIRECT=0x10000` 读取相同文件得到正确的新索引 `8f 7a 94 7a`，10 个目标扇区也匹配。原因已限定为缓存视图与磁盘数据不同，但具体保留机制尚未确认。

完整验证因此对图标文件使用固定路径的只读探针，直接读取**整个文件**并计算 SHA-256；不修改返回数据、不忽略差异、不刷新或写入图标文件。探针只写 44 字节临时报告，完成后清理。SHA-256 在 ARM QEMU 中与 Python hashlib 比较，75 组分块和填充边界测试通过；第一版已经完成真机 26,481,288 字节直接散列校验。大文件直接读取和运行中的 MENU 图标引用分别验收，不能用磁盘散列代替界面结果。

## 本地包指纹

v3 前置镜像 SHA-256：`d1666d072c6b8852c44b4b3e61a4d0efadc7f56d38c43fb3c30b2578cdd35959`。

目标镜像 SHA-256：`1d0285f123cb79999517d9e0e80dde0bc40a622b111c60683a8f20c6ab4cb7f8`，共 2,278 个不同字节，10 个 512 字节扇区；激活代码扇区最后写入。图标文件 SHA-256：`5b6e94231de326292babb99aeae97f9fa98bc09d086368f6336a58405a5a4ea7`。

新包及恢复数据在 `.lab/creative-icons/`，原厂组件证明在 `.lab/menu-icons/`，直接散列证明在 `.lab/image-hash/`。这些目录和全部相机备份保持本地，不提交 GitHub。
