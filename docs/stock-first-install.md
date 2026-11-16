# 原厂 4.04 首次安装候选

2026-11-16：已接入真实的原厂首装实验后端与 GUI，包括 Windows/Linux libusb 会话、逐机备份、模块和语言暂存、图标/配置/加载器激活、WBI 前像绑定处理、完整回读。**这是可执行实验候选，不是已通过原厂机验收的稳定刷机器。** 当前仅有已改装开发机，本轮没有枚举、连接或修改它。

现有 v0.01 及 GUI Release 保持原样。本页是后端开发记录，不是让普通用户刷写的操作教程。

## 从原厂到当前功能需要哪些文件

| `/usr` 下的文件 | 安装内容 | 当前验证 |
| --- | --- | --- |
| `lib/a7fl.so` | 六套配色、曲线、拍后效果、SD 导入、独立外观、删除、动态名称 | 使用已验收的 `30474345…` 模块，重新构建散列不变 |
| `lib/viewUnified2.so` | 原菜单修改及开机/菜单加载器 | 原厂至目标改动 662 字节，涉及 4 个 4 KiB 页面 |
| `lib/CautionConfig.so` | 原厂菜单配置补丁 | 改动 2 字节，涉及 1 个页面 |
| `share/app/image_cmn_43.uxc` | RW 图标资源 | 改动 5741 字节，涉及 13 个页面 |
| `share/app/string_simplifiedchinese.uxc` | 简中完整扩展菜单资源 | 从原厂直接生成最终文件，不依赖中间版本 |
| `share/app/string_english.uxc` | 英文完整扩展菜单资源 | 同上 |

上述页面数量是文件偏移统计，**不是可直接写入的进程虚拟地址或磁盘扇区表**。尤其不能将文件前像比较直接套到已重定位的数据页面。

差分包只有目标模块、文件差分及清单，不含整机镜像、个人配置、序列号、校准、照片或设置备份。目标模块启动时走现有默认设置初始化流程，不复制开发机的配方银行。缺少设置时初始化为关的路径在 ARM 测试中覆盖；原厂机实际启动尚未验证。

## 本地构建和演练

需要 Python 3.10+、e2fsprogs 的 `debugfs/e2fsck`；ARM 暂存程序还需 `arm-none-eabi-gcc/ld`，模块回归需 QEMU。Python 差分解析器只有标准库，可在 Windows、macOS、Linux 运行。镜像和 ARM 演练本轮只在当前 Mac 执行。

开发目录还需已有的本地原厂备份、RW 资源、当前已验收模块、语言和相应证据。仓库不提供 Sony 原厂文件；缺少这些输入时命令会失败，而不会跳过校验。

从仓库根目录执行，输出路径必须是 `.lab/` 内**不存在的新目录**：

```sh
python3 -m unittest discover -s tools -p test_stock_install_bundle.py -v
python3 research/native_install_test.py
python3 research/native_custom_integration_test.py
python3 research/stock_first_install.py --out .lab/stock-first-install-new
python3 research/stock_stage_build.py \
  --stock .lab/a7m3-live-usr-nflasha15.bin \
  --candidate .lab/stock-first-install-new/stock-404-candidate.zip \
  --out .lab/stock-first-install-new/arm-stage
```

模块回归必须先完成再构建暂存程序，以绑定最新测试证明。不要并行重建依赖的证明文件。

`stock_first_install.py` 会核对本地原始备份的文件系统前缀；这是开发用固定输入，不要求其他机身的完整备份与开发机相同。未来设备预检应按机型、构建号和逐文件前像识别，并保存该机自己的备份。

输出：

- `stock-404-candidate.zip`：原厂文件到当前文件的完整差分候选；不是官方 DAT，也不是现有部署脚本的升级包。
- `rehearsal/installed.img`：仅在本地镜像副本上完成安装的终态。
- `rehearsal/restored.img`：撤销候选后核对原厂文件的终态。
- `rehearsal-proof.json`：所有文件、尾部、空间、独立回读和文件系统检查结果。
- `arm-stage/stock-stage-only.so`：绑定原厂前像的 ARM 暂存阶段；**仅处理模块与两种语言，单独执行不会装好全部功能**。由实验安装控制器串联后续阶段，不单独上传执行。

所有生成文件只保留在 `.lab/`。不能把本地镜像作为“通用整机固件”分发或写到另一台相机。

## 已执行验证

- 固定原厂 `/usr` 镜像：873 个普通文件/符号链接。仅五个预期文件改变，新增模块及两份原语言备份；其余文件和分区尾部不变。
- 独立 `debugfs` 导出目标文件，逐字节比对；安装各阶段及恢复阶段 `e2fsck -fn` 全部通过。
- 恢复后，873 个原文件的内容、模式和所有者与基线一致。ext2 空闲区、时间戳等元数据不要求镜像逐字节相同。
- 原厂空闲 9,796,608 字节；模块/语言暂存需求（含余量）925,696 字节；安装终态余量 8,887,296 字节。完整复制主菜单库的方案空间不足。
- 现有文件事务核心：160 个故障注入点，18,980 项检查通过。覆盖的是主机 syscall 模型及 ARM 链接，不能等同断电恢复实测。
- 当前模块 ARM 菜单/导入/删除/连续选择/启动回归通过；生成二进制仍为 `30474345352eaed6b1feb8f33e389278febaeb6c3fc493dc2355ab560ca591a4`。
- 差分往返、错误前像、重复执行、损坏范围、重复 ZIP 条目、未知目标及篡改声明会被拒绝。

离线 `debugfs` 的链接/删除操作只用于终态演练。真实安装必须使用相机内核的文件操作与持久化日志，不能在已挂载文件系统上照抄这些命令。

## 真实激活与 GUI 包构建

`research/stock_activate.c` 使用逐文件绑定的事务。主菜单/配置必须找到匹配的 RX 私有映射；图标文件建立自有私有映射，拒绝已有冲突映射。扫描其他进程的路径及设备/inode 别名，发现其他读者则停止；修改前验证旧页并建立 COW，保持运行中的旧代码。按图标→配置→加载器激活，加载器的辅助代码先写、入口分支页后写。所有修改通过 VFS，fsync/回读后恢复只读；每个阶段有独立日志，不自动重放。

隔离 ARM Linux 测试真正执行 mmap/mprotect、procfs 检查、VFS 写入和回读：三个组件共 134 项检查通过，包括每页短写失败恢复、COW 失败拒绝、重复执行拒绝。挂载状态和指定 I/O 失败由测试 shim 提供，因此不是 Sony 3.0 内核或断电恢复验收。所有新载荷局部绑定符号，避免不同阶段同名辅助函数相互引用。

接着前面的本地构建步骤执行；`--firmware-lab` 指向本机含 ARM Linux 测试内核、BusyBox 和原厂根文件系统的目录：

```sh
python3 research/stock_activate_build.py \
  --stock .lab/a7m3-live-usr-nflasha15.bin \
  --candidate .lab/stock-first-install-new/stock-404-candidate.zip \
  --out .lab/stock-activation-new
python3 research/stock_activate_test.py \
  --directory .lab/stock-activation-new --firmware-lab /path/to/firmware-lab \
  --stock .lab/a7m3-live-usr-nflasha15.bin \
  --installed .lab/stock-first-install-new/rehearsal/installed.img
python3 research/native_menu_wbi.py
python3 research/stock_installer_package.py \
  --candidate .lab/stock-first-install-new/stock-404-candidate.zip \
  --stage .lab/stock-first-install-new/arm-stage \
  --activation .lab/stock-activation-new --out .lab/stock-package-new
python3 tool/build.py --native --out .lab/stock-tool-new \
  --installer .lab/stock-package-new/Sony_A7M3-Stock404-Experimental.zip
```

`stock_installer_package.py` 核对各证明的源码、候选和载荷散列后才打包；它不生成另一台相机的设置。WBI 模板只有一个 1024 字节前像绑定槽，GUI 仅在本次同一连接里核对 WBI0/WBI1、容量、进程和邻接扇区后填入；模板未绑定时不会匹配真实头部。编译器只在开发侧需要，Windows 用户不需要编译 ARM 程序。

GUI 的 `tool/first_install.py` 负责唯一会话：验证候选外部 SHA-256 → 逐机备份及原厂前像 → 等待单独确认 → 再次核对前像 → 暂存 → 三阶段激活/回读 → WBI → 最终回读。仅 `ready` 状态接受确认；10 分钟超时取消，不自动重新连接或重试任何写入。失败保留本地证据。`awaiting-cold-boot` 不标记实机验收成功。

USB 层使用固定上游提交 `a82f5baaa8e9c3d9f28f94699e860fb2e48cc8e0` 的最小 Sony-PMCA-RE 源码子集，路径 `tool/vendor/`，保留 MIT 许可证与散列清单。Windows 的两个 VID/PID 模式分开打开；机型/构建号不符或多台设备时停止。不会自动替换 USB 驱动。Mac 暂时仍需既有 UTM 环境手动完成交接。

## 发布稳定首次安装器前的剩余验收

2026-11-16 的 [三平台构建记录](https://github.com/robinshie/Sony_A7M3/actions/runs/43866534385) 已通过：Windows x64、macOS arm64、Linux x64 均运行 34 项 GUI/会话模拟测试，构建原生程序，再从解压后的程序加载 libusb 动态库、认证模块和散列库，启动本地 GUI、复制/回读临时配方并退出。`--usb-runtime-check` 明确不枚举设备；CI 无相机，因此这个结果不代表 Windows 实物通信或原厂首装成功。Mac 本地含候选包的独立程序也完成相同启动检查。

实验候选 SHA-256：`fdf9b39de2de1fa03b3b4c19907f1ee606b233b8e7399e7910d5206ac79373b6`。工具源码在 `codex/stock-404-installer` 开发分支；未替换 main 或 v0.01 稳定附件。

1. Windows 实物 USB、驱动组合以及 Mac GUI 的 UTM 交接。
2. Sony 内核中原厂各资源的实际映射/读者状态；当前严格检查可能拒绝执行，不能删掉检查强行刷入。断电中断后的整套恢复尚未完成。
3. 纯原厂 4.04 → 安装 → 断电启动 → SD 导入 → 保存 → JPEG L/M/S → 再次断电保留。已有改装机的升级记录不能替代。

代码中已有真实写入路径；底层组件的 `flash_ready:false` 和完整包的 `hardware_verified:false` 表示尚无硬件验收，不能理解为包永远只读。当前不覆盖公开 v0.01 稳定附件。
