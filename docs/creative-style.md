# 「复古衣橱」创意风格实验

2026-11-11 后续工作：[RW 图标修复与验证](style-icons.md)、[FL 方向的机内色彩接口研究](color-interface.md)。下文保留 v3 及更早版本的构建和验收记录；安装图标包后改用 `creative-verify-icons`。

**状态：v3 已完成烧录、断电重启、屏幕验收及 USB 回读。** v2 已验证入口与参数持久化，但用户后续发现 Fn 名称仍显示基础风格、重新进入时未定位到新增项。当前验收命令改为 `a7m3.py creative-verify-identity`；`a7m3.py flash` 仍只写标题补丁。

## 日常精简流程

本次以原厂 4.04 和本机分区备份为基底，编译小段 ARM 补丁、修改资源，再生成分区差异。固件解包、初始备份、原函数定位及 USB/UTM 配置属于一次性准备，同一机身和固件版本下可以复用。

**改补丁 → 编译及 QEMU 组件测试 → 生成镜像与恢复数据 → 写入测试及文件系统检查 → 真机写入、重启、回读。**

| 步骤 | 当前实现 | 通过条件 |
| --- | --- | --- |
| 修改显示与定位 | `research/menu_identity.S`、`research/menu_identity.py` | 第 3 槽中性配方识别为新增项，其他槽保持原名 |
| 编译并测试原厂调用接口 | `research/menu_identity.py` | `QEMU_IDENTITY_PASSED`，418 条光标路径、91 条 Fn 名称路径 |
| 生成镜像与扇区前后数据 | `research/build_creative_identity.py` | 生成与前置镜像绑定的清单、镜像和恢复数据 |
| 验证写入、恢复及文件结构 | `research/creative_identity_test.py`、`research/check_creative_image.py` | QEMU 写入/回滚通过；ext2 和导出文件散列一致 |
| 重启后验收 | `a7m3.py creative-verify-identity` | 四个文件、运行代码、名称属性及配方一致，屏幕名称/定位/切换验收通过 |

构建脚本的固件、内核和运行库路径见后面的完整命令。QEMU 检查的是所改代码与写入逻辑；实际屏幕显示和拍摄效果仍在机身上确认。

已经安装本次 v3 后，只检查状态时无需重新 build。沿用本机环境变量、将相机接入 UTM 后，在仓库目录执行：

```sh
# 快速读取本次修正涉及的扇区；报告 preimage=2 表示它们匹配 v3。
python a7m3.py creative-read-identity

# 完整检查前，先在机身打开创意风格并选择「复古衣橱」，再接回 USB/UTM。
python a7m3.py creative-verify-identity
```

快速读取只覆盖修正包的目标扇区；完整检查还读取四个文件、运行内存和保存参数。只改文档无需重跑硬件测试；改补丁代码、资源或配方时，重建相关产物并重新生成验证记录。

**下次开发新版本的两个约束：** `recipes/retro-wardrobe.json` 当前用于配方说明和独立 UI 模型，原生代码及其测试仍有固定参数，只改 JSON 不会改变真机配方。现有 `build_creative_identity.py` / `creative-identity` 固定面向 v2 → v3；安装 v3 后，下一版应以已验证的 v3 镜像为前置状态生成新的增量包，并同步更新验收参数。不要反复套用旧包。名称目前也由构建代码和既有中文资源控制，尚未统一为配置驱动。

## v3：选中名称与重新进入时的定位

v2 的新增入口能应用配方，但保存的是原厂「中性 + 第 3 样式框」。原厂反向转换会恢复成旧子项；Fn 主页面通过另一份 `CautionConfig.so` 属性表获取名称，所以新增入口的中文名称不会自动传播到 Fn。

v3 在已验证 v2 基础上增加以下修正：

- `viewUnified2.so` 的 `0x005bb18e`（记忆选择）和 `0x005bb9de`（重新进入）调用新辅助函数。基础值 3、样式框 3 时，定位到根 97 下的新增项 98；其余输入沿用原函数。六个样式框的初始化循环保持原函数。
- 辅助函数共 28 字节，放在 v2 已腾出的 NOP 区域 `0x005b9a60`。保留 v2 的入口安装与参数处理。
- `CautionConfig.so` 的 `CreativeStyleCNeutralBox_3` 名称属性由 `0x0204e08d` 改为已存在的 `0x0204ed84`，即「复古衣橱」。其他样式框的中性名称保留。

**识别方式是「第 3 槽 + 中性」，没有额外的风格身份字段。** 手动在第 3 槽选择中性也会显示这个名称；在此槽调整对比度等参数不会取消该名称。其他原厂基础风格与槽位仍可选择。当前自定义中文资源仅支持简体中文。

组件测试执行原始逆向映射、Fn 编号转换和 Fn 节点选择机器码。UI 存储和节点虚函数使用测试替身；这能检查代码路由与名称解析，不能代替实际屏幕验收。写入载荷另外验证错误前置内容拒绝、重复写入拒绝、故障回滚、已知混合状态恢复及未涉及扇区不变。

在仓库目录，沿用已配置的环境与本地固件文件：

```sh
python research/menu_identity.py \
  --usr "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha15_unpacked" \
  --kernel /path/to/vmlinuz-lts \
  --busybox /path/to/alpine-root/bin/busybox \
  --sony-root "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha7_unpacked"
python research/build_creative_identity.py
python research/creative_identity_test.py \
  --kernel /path/to/vmlinuz-lts \
  --busybox /path/to/alpine-root/bin/busybox \
  --sony-root "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha7_unpacked"
python research/check_creative_image.py .lab/creative-v3
# 相机接入 UTM；仅适用于机身仍为 v2 的首次更新。
python a7m3.py creative-identity --write-device
# 完整断电重启，验收下列界面行为，再接回 USB/UTM。
python a7m3.py creative-verify-identity
```

屏幕验收：选中「复古衣橱」→ 退出到 Fn 确认名称 → 再进入时直接停在该项 → 切到「标准」确认名称随之改变 → 最后选回配方并核对 +1、−1、−1。不能仅凭写入回读成功标记这一项通过。

2026-11-10，用户完成断电重启后确认：名称和定位均正确，切换标准也正常。随后 `creative-verify-identity` 回读通过：4 个扇区与目标一致，四个完整文件散列匹配；运行中的两个定位调用、28 字节辅助函数及 Fn 名称属性已加载；菜单仍为 20 项，编号 98，原厂第 3 槽和当前参数均为 +1、−1、−1。此验证覆盖界面与配方保存，不包含实拍色彩效果比较。

v3 相对 v2 改动 31 字节、4 个扇区。镜像 SHA-256：`d1666d072c6b8852c44b4b3e61a4d0efadc7f56d38c43fb3c30b2578cdd35959`。`viewUnified2.so`：`43c3f773a78be3311a37827bdaf8762b3c1d8203a80b072b4e18e704fcea5923`；`CautionConfig.so`：`be38cd21ffa9e1720cc910af10e3a526ecd4f580a418a56c8c1bd1009bf00567`。中英文资源沿用 v2。恢复到 v2 使用 `python a7m3.py creative-restore-identity --write-device`，完整断电后再使用 v2 的验收命令。所有镜像、精确恢复数据、机身备份及原厂机器码留在忽略目录 `.lab/`。

以下保留 v1/v2 的实现与验证记录，相关旧版本命令不适用于直接覆盖已安装的 v3。

目标是在「创意风格」中新增「复古衣橱」，保留原有选项，并在机身中实际应用、保存以下设置。配方在 [`recipes/retro-wardrobe.json`](../recipes/retro-wardrobe.json)。这是基于 Sony 现有调节项的实验配方，尚无实拍对比，不声称复现某款富士胶片模拟。

| 参数 | 值 |
| --- | --- |
| 基础风格 | 中性 Neutral |
| 对比度 | +1 |
| 饱和度 | −1 |
| 锐度 | −1 |
| 白平衡 | 日光，需在机身手动设置 |
| 图片配置文件 / 照片效果 | 关 / 关，需在机身手动设置 |

真机版本新增一个名为「复古衣橱」的菜单入口，使用原厂第三个样式框保存中性风格及三个调节值。选择新增入口时会应用 +1、−1、−1；第三个样式框因此作为本配方的存储槽。没有增加 ISP 色彩算法、LUT 或新的参数存储槽。白平衡及两个关闭项是拍摄前提，目前不会由新增入口自动切换；QEMU 独立 UI 原型曾模拟这三项自动设置，不能据此声称真机也支持。

Sony 对创意风格和六个样式框的说明见[原厂帮助指南](https://helpguide.sony.net/ilc/1720/v1/en/contents/TP0001653152.html)。使用已有样式框手动保存配方，是原厂已有功能；它不等于本实验要求的新增固件菜单项。

## 运行界面原型

沿用[界面实验的依赖](ui.md)，然后执行：

```sh
export A7M3_FIRMWARE_ROOT="/path/to/firmware.tar_unpacked"
python ui/build.py --retro-wardrobe
python ui/run-ui.py --guest ui/build/retro-wardrobe/a7m3-ui.elf
```

按 `M` 返回取景，`F` 打开 Fn；向下后向右四次选中「创意风格」，按 Enter，向上跳到新增项，再按 Enter 查看配方。确认只修改这个模拟器的内存状态；取消保持先前选择。QEMU 重启会重置状态。它没有传感器、ISP、JPEG 色彩变换或机身参数持久化。

新配方确认页会设置模拟状态中的基础风格、三个参数、日光白平衡和两个关闭项。选择旧风格时，模型将三个参数清零。选择非关闭的照片效果或图片配置文件时，模型将风格回到标准；这里描述的是测试模型的行为，不代表已验证的原厂完整状态机。

```sh
python ui/run-ui.py --headless --guest ui/build/retro-wardrobe/a7m3-ui.elf \
  --qmp /tmp/a7-creative.sock --serial /tmp/a7-creative.log
# 另一终端；测试需从新启动的来宾执行。
python ui/verify-creative.py /tmp/a7-creative.sock /tmp/a7-creative.log .lab/creative-shots
```

自动测试覆盖确认、取消、重复应用、模拟参数值、保留全部 13 个旧选项、照片效果冲突后的重新应用以及中英文截图。原来的 38 页导航检查仍可独立运行。

## 原厂代码的组件测试

`research/creative_dispatch.py` 从用户的本地 4.04 库提取一个无外部调用的 Thumb 函数，将**未修改的机器码**装入裸机 ARM QEMU 执行。提取范围为 `viewUnified2.so` 虚拟地址 `0x005b98dc` 到 `0x005b9b6e`，共 658 字节。脚本固定校验两个原厂库的 SHA-256；输入版本不符就停止。原厂字节、ELF、日志、报告均留在忽略目录 `.lab/creative-research/`，仓库不分发 Sony 二进制。

```sh
python research/creative_dispatch.py --usr \
  "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha15_unpacked"
```

2026-11-10 的执行结果：

- 输入 0–96 共 97 个路径，返回值在 0–13，输出槽位值在 0–6。
- 输入 −1、97、98 均返回 14，且不修改输出槽位；测试中的槽位初值为 −99。
- 因此，单纯追加新编号并沿用当前转换函数不能完成新增风格。返回 14 的下游语义尚未验证，不能仅凭数值将其当作可用的第十四种风格。
- 这只验证一个 UI 编号转换函数，不是原厂界面启动测试，也不验证 ISP 或图像输出。

静态分析还定位到 `CautionConfig.so` 中的 `CmnViewSettingNodeCreativeStyle::_getSubNode()`（`0x0069335c`）。它读取设置 ID `0x01070316`，再选择不同的节点数组。已有机身备份中此值为 `0x3e`，按静态分支对应 `cmnViewSettingNodesCreativeStyleTypeEmnt`，含 91 个节点引用。之后的运行进程只读检查确认：根节点的子节点指针和计数与此数组一致；Neutral 节点已连接到根节点，Real 节点尚未连接。

报告包含 99 份导出的 CreativeStyle 属性表及各节点数组的重定位名称。属性表中的数字键、UI 编号、底层风格值和设置备份 ID 不能互相混用。库里出现 `CreativeStyleReal` 名称，也不能据此认定有可直接启用的隐藏风格。

### 原厂设置函数的执行测试

`research/creative_setter.py` 在原虚拟地址执行 `viewUnified2.so` 的 `0x00420d18–0x00420faf`（664 字节），保留其原始指令和参数 ID 表。分配内存、备份写入、参数对象及模型请求均由记录型桩函数接管，QEMU 不连接相机。运行命令：

```sh
python research/creative_setter.py --usr \
  "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha15_unpacked"
```

已通过 38,416 组组合测试：内部风格编号 −1 至 14、样式框 0 至 6、三个调节值各 −3 至 +3。编号 0–11、13 为接受路径；12、−1、14 被拒绝。测试检查保存请求的字段、字节值，以及发往 `@M00B`、命令 38 的参数列表。模型参数 383、386、389、392 分别承载基础风格、对比度、饱和度和锐度；原函数还重复添加一次参数 383，测试保留了这一原始行为。

中性对应此函数的内部编号 2，发送的基础风格值为 3。样式框 3 的保存路径包含 `0x01070762=2`、`0x0107075e=3`，以及 `0x01070a11`、`0x01070a17`、`0x01070a1d` 三个调节字段，与本次机身快照差异对应。这说明用户当前配方保存在原厂第三个样式框；没有创建额外的参数存储槽。

**测试还确认：将模型请求桩函数的返回值设为失败，原设置函数仍返回 1。** 因此仅凭函数返回值不能宣称参数已被 ISP 接受。上述测试验证的是调用和保存请求，不验证机身提交完成、成像效果或重启恢复。没有将该函数作为 USB 写设置命令开放；原函数自身也没有完整的样式框范围保护。

已追到的调用链为：UI 包装设置函数 `0x002d2e74` → `CmnViewProcessDataMgr`（数据项 40）→ 类型表项 45 → 设置函数 `0x00420d18`。读取路径对应 `0x002d2e00` 和 `0x004231f4`。这些内部地址只适用于散列匹配的 4.04 库，不能直接加到其他版本的加载地址上执行。

## 真机设置与运行进程的只读验证

2026-11-10，用户在机身中手动选择中性、调整参数，并关机再开机后重新连接。多份独立 BK4 快照通过长度及校验和检查；最终读到以下字段。此过程未通过 USB 写入这些设置，也没有添加新的风格条目。

| BK4 属性 ID | 原厂 `libObj.so` 注册名称 | 最终值 |
| --- | --- | --- |
| `0x01070175` | `COLOR_MODE_TYPE` | `03`，与本次机身选择中性对应 |
| `0x01070178` | `CONTRAST_LEVEL` | `01`，+1 |
| `0x01070187` | `SATURATION_LEVEL` | `ff`，有符号单字节 −1 |
| `0x0107018a` | `SHARPNESS_LEVEL` | `ff`，有符号单字节 −1 |

原厂注册位置在 `libObj.so` 的 `0x004ba91e`、`0x004ba93a`、`0x004ba956`、`0x004ba972`，相邻字符串分别给出上述名称。对比度测试中先读到 `02`，恢复配方后为 `01`；饱和度及锐度从 `00` 变为 `ff`。同次保存还改变了其他字段，因此不能把上述四个地址当作完整的风格保存协议。初次未重启的快照没有体现手动调整，后续测试明确要求关机再开机。

沿用[真机操作手册](updater.md)中的环境配置：

```sh
python a7m3.py settings-snapshot
python research/settings_diff.py --pmca .lab/Sony-PMCA-RE \
  .lab/settings-snapshots/settings-BEFORE.bin \
  .lab/settings-snapshots/settings-AFTER.bin
```

快照每次创建新文件，不覆盖最初备份。差异工具默认只输出属性 ID、长度、散列及属性/重置值是否变化；`--show-small-values` 可在本地显示不超过 8 字节的变化值。这些结果只是参数候选，工具不提供据此自动写回的功能。快照包含机身私有信息，均保存在忽略目录。

`settings-runtime-snapshot` 还会在维护进程 RAM 内临时加载 `a7-runtime-probe.c` 编译的探针。它顺序读取 `/proc/self/maps` 和 `cmdline`，按映射权限检查范围后读取几个已知节点；只创建维护临时目录里的报告，读回后清理。它不改节点、固件或设置。运行前必须完成 `a7m3.py qemu-test`，工具校验被加载载荷的 SHA-256 与测试记录一致。

运行检查确认维护入口位于 `/usr/bin/im.elf` 进程，`libObj.so`、`viewUnified2.so` 与 `CautionConfig.so` 均已加载。这个结果说明可以进一步研究同一进程中的接口，**不证明**新增节点或调用设置服务已经成功。

探针的 QEMU 检查包含：目标库未加载时不解引用；加载合成节点库时读取已知标记；前后磁盘测试扇区一致。合成库只含测试整数，不分发原厂库。原有备份、错误前置镜像拒绝、写入及恢复测试也通过。

扩展探针还读取 `viewUnified2.so` 的菜单根对象、19 个顶层条目及两个设置服务对象，共返回 67,044 字节。它先验证根对象的指针、数量及编号，再跟随指针；QEMU 用独立合成库验证这些检查。2026-11-10 的真机回读得到 `node_status=2`、`view_status=2`，顶层菜单数据与本地原厂库一致（仅加载重定位不同），两个服务对象均有已初始化的虚函数表。

此菜单根位于库偏移 `0x00a60c90`，条目数组位于 `0x00a60998`。根编号是 **97**；已有 13 个基础项和 6 个样式框父项，样式框下还有子项。因此编号 97 不能作为新增叶子使用。静态子项的编号顺序与转换函数的内部风格顺序存在差异；尚未验证菜单初始化、游标定位与这些编号之间的完整关系。上述探针只读；下面的独立实验才会修改运行内存。

## 临时原厂菜单入口实验

`research/menu_ram.py` 构建安装、检查、恢复三个 ARM 载荷。它保留原有 19 个顶层条目，在匿名 RAM 中复制表并追加编号 **98** 的条目；根编号 97 不变。新项暂借已存在的标题资源 `0x0204f7e6`，在本次已修改机身上显示为「我的相机/固件实验」，还不是最终「复古衣橱」名称。

替换分派函数保留输入 0–96 的原厂返回值；98 返回基础风格值 3、样式框 3，其余非法输入继续返回 14 且不修改输出槽位。此入口引用已配置的原厂第三个样式框，不新建参数存储槽，也不直接调用设置服务、修改白平衡或写入 BK4。它能否经原厂 UI 正确选择配方，必须在机身上验证。

```sh
python research/menu_ram.py \
  --usr "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha15_unpacked" \
  --kernel /path/to/vmlinuz-lts \
  --busybox /path/to/alpine-root/bin/busybox \
  --sony-root "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha7_unpacked"
# 沿用 updater.md 的 UTM、PMCA 环境配置：
python a7m3.py menu-ram-install
python a7m3.py menu-ram-inspect
python a7m3.py menu-ram-restore
```

QEMU 运行 Linux、Sony 本地提取的 glibc 和一个按原地址排列的合成菜单库；这不是启动整套相机固件。测试驱动在 libc 初始化完成后动态加载载荷。测试覆盖缺库拒绝、原始代码和表校验、追加条目、原输入行为保留、98 路由、调用计数、重复安装、恢复、错误根对象/代码拒绝，以及测试磁盘未改变。原厂机器码和库都留在 `.lab/`，不随仓库分发。原先在预加载构造函数中嵌套 `dlopen` 的测试曾崩溃；改为正常进程主函数加载后通过，未把该失败版本上传相机。

主机在上传前校验载荷及五份源文件的散列与 QEMU 成功记录一致。安装前还会新建机身 BK4 快照，确认当前中性配方和第三个样式框的九个字段；不符即拒绝。载荷再次检查机身加载地址、可读写范围、全部 19 行和原分派机器码。它只修改代码页与菜单根对象的运行内存，另写临时报告；不打开固件分区或写设置。恢复会还原根对象及代码；保留匿名分配到断电，避免已有 UI 指针悬空。断电也会清除整个实验。

2026-11-10 真机返回 `status=1`、`count=20`、`code_changed=1`、`error=0`，原配方九个字段匹配。安装载荷 SHA-256 为 `65854c0bf59db72b906f6205ec91284ebb731eb2406400197b50fdacb44ff92b`。随后用户确认临时入口出现，选择后显示 +1、−1、−1；独立 USB 检查得到调用计数 19、最后编号 98、返回风格 3、样式框 3。这证实了新增条目的原厂选择路径，尚未提供实拍效果比较。

机身验证步骤：等存取灯熄灭后拔 USB，保持开机；从 Fn 打开创意风格，在列表末尾寻找临时标题并选择，核对三个调节值。再接回 USB/UTM，执行 `menu-ram-inspect` 检查是否收到编号 98、返回风格 3 和槽位 3。先完成此检查，再研究最终名称、参数应用与永久文件补丁。

## 永久补丁与烧录

v2 基础实现使用 `research/menu_lazy.S`。原分派函数的 658 字节空间装入 388 字节的紧凑分派表、菜单创建处理和参数处理，其余填 Thumb NOP。`0x005bb266` 的调用改为先准备 20 项菜单，再沿用原厂 `CmnMenuTableUtil::initMenuData`，完整保留调用参数和返回路径。它在每次打开创意风格时执行；已有新增项时不会重复分配。最终版本保留原厂 `DT_INIT`、`.init_array` 和 ELF 装载段。

选择路径在 `0x005b9fba` 增加一个跳转：查询当前菜单编号，只有 98 才把原厂设置调用前的三个参数改为 +1、−1、−1；其他编号保留原值。中性基础值和样式框由已在真机验证的分派路径取得，提交仍经过原厂设置服务。Sony glibc/QEMU 测试覆盖 256 个分派输入、34,643 组参数组合、菜单创建时的原调用参数/返回值以及重复打开。

简体中文 UXC 表的资源编号 `0x04ed84` 原本未分配。`research/uxc_strings.py` 填充此索引槽，并在原有末尾块的空余空间中追加 20 字节「复古衣橱」记录。原有已分配字符串、索引位置及表长度均保持不变，也保留此前「我的相机/固件实验」标题。**最终版本只添加简体中文名称**；英文资源的文件内容与长度已恢复原厂值，其他语言未添加新名称。

### 初始化修正的依据

第一版 `menu_persistent.S` 曾在 `DT_INIT` 安装入口，10 个扇区写入回读通过，但用户重启后没有看到新菜单。诊断发现：运行中的分派代码已匹配新文件，动态初始化字段仍为原值，菜单表仍是 19 项；英文文件读取长度也仍为旧值。不能把磁盘文件已更新视为运行中的初始化已执行。

第二版因此改为菜单创建时安装入口，并恢复英文资源。相对第一版修正 7 个扇区、174 字节；真机报告 `status=1`、`error=0`、`written=7`、`readback_ok=1`。第一版源码和精确镜像留作实验及恢复依据，不是当前推荐的实现。

### 构建与检查

`research/ext2_patch.py` 解析 ext2 目录和直接/间接块，只替换原有文件数据及必要的文件长度，不申请或释放块。v2 镜像通过 `e2fsck -fn` 全部五项检查；用独立 `debugfs` 导出三个目标文件后，散列均与构建目标一致。文件数和占用块数与前置镜像相同。

此项目记录本机两阶段实验。`build_creative_fix.py` 的前置镜像来自已归档的 `.lab/creative-v1/`，必须与其清单散列一致；不能对任意固件直接套用。保留第一版镜像和恢复载荷之后，第二版构建命令为：

```sh
python research/menu_lazy.py \
  --usr "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha15_unpacked" \
  --kernel /path/to/vmlinuz-lts \
  --busybox /path/to/alpine-root/bin/busybox \
  --sony-root "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha7_unpacked"
python research/build_creative_fix.py
python research/creative_fix_test.py \
  --kernel /path/to/vmlinuz-lts \
  --busybox /path/to/alpine-root/bin/busybox \
  --sony-root "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha7_unpacked"
python research/check_creative_image.py .lab/creative-v2
```

`menu_lazy.py` 沿用 RAM 实验生成的原分派映射与 Sony 运行库测试启动文件，因此应先按前文运行 `research/menu_ram.py`。固件、镜像、原厂机器码、设置和现场报告均在忽略目录，不上传 GitHub。

`creative-fix --write-device` 仅接受已写入第一版、且运行状态与诊断一致的机身。写入前备份设置并验证第三样式框；载荷核对完整分区容量、文件系统头和每个目标扇区，最后才修改菜单创建调用。写入或回读失败时尝试恢复本次操作前的精确字节。QEMU 已验证读回、写入、恢复、重复安装拒绝、未知前置内容拒绝、已知混合状态恢复及注入失败后的回滚。断电无法由补偿代码处理，写入期间仍须保持供电和连接。

当前已经是第二版，日常检查只需：

```sh
python a7m3.py creative-read-fix
python a7m3.py creative-verify-fix
```

如要完全撤销创意风格、恢复到只含旧标题修改的状态，保持 USB 连接依次执行以下两步，全部回读成功后再关机重启：

```sh
python a7m3.py creative-restore-fix --write-device
python a7m3.py creative-restore --write-device
```

第一步恢复到第一版；第二步才恢复到创意风格实验前。恢复路径已在 QEMU 中验证，本次未为测试恢复而撤销用户刚安装的功能。

### 最终真机验收

2026-11-10，用户按断电重启步骤操作后，确认 Fn → 创意风格中出现「复古衣橱」，选择后显示 +1、−1、−1。随后独立 USB 检查通过：

- 第二版全部目标扇区与写入后的预期字节一致。
- 三个完整文件的长度和 SHA-256 一致，见下表。
- 运行中的分派函数、参数跳转和菜单创建跳转均与目标文件一致。
- 菜单数量 20；新项编号 98，名称资源 `0x0204ed84`。
- 完整 BK4 快照通过格式检查，九个当前/样式框字段匹配：中性、第三样式框、对比度 +1、饱和度 −1、锐度 −1。

| 文件 | 验证后的 SHA-256 |
| --- | --- |
| `/usr/lib/viewUnified2.so` | `8a010075b48c8e5db202990fcf37a3f49f5d3b7461327edfdfdb89c8a53d9604` |
| `/usr/share/app/string_simplifiedchinese.uxc` | `ee8160400a4c4610ba3df655a6333e0ad0c5f94aeecc56c0b898a6603c8aedc9` |
| `/usr/share/app/string_english.uxc` | `eb4793ba3191a7aeb2f4e6f73694bf93e8f67c1f5ec6f1638dc67a291e015426` |

最终本地完整镜像 SHA-256 为 `820eb129bbbfc6a82044f33787b58b9bf5b69a9f6cf881500ba670173aaca7db`。相对原来的标题改版镜像，最终分区有 8 个扇区、686 字节不同；其中包含第一版留在英文文件 EOF 之后、不属于有效文件内容的记录字节。镜像散列来自本地完整镜像，不能表述为刚读回整个真机 300 MiB 分区所得的散列。

`native_integration_verified: true`、`reboot_verified: true` 记录上述验收范围。尚无同场景 JPEG 实拍对照，也未穷尽所有机身模式组合；本版本仍是基于原厂中性风格的参数配方。
