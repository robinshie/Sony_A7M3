# 真机「创意外观」实验模块

构建范围是自有 ARM 驻留模块、菜单资源和原厂加载入口补丁。Sony 固件主体使用经过散列校验的 ILCE-7M3 4.04 二进制，内部版本为 `37114_13.2026020901`。固件、相机备份、照片和生成的安装包只保存在忽略提交的 `.lab/`。

## 入口与功能

首版目标入口：**MENU → 拍摄设置 1 → 第 14 页 → 创意外观**。它与创意风格同级，保留原页的防闪烁拍摄、人脸登记及登记人脸优先三个项目，也保留已有「复古衣橱」和 RW 图标修改。

选择关或「FL（实验版）」；对比度、高光、阴影、褪色、饱和度直接生成机内 LUT 的变化。调节先预览，最后选择「保存」写入配置。锐度、锐度范围、清晰度尚未实现，保持置灰。首版只接入静态拍摄菜单，使用已验证的表 0 通路；图片配置文件和照片效果应保持关闭。

这是自制近似 FL。原厂非线性色度编解码、节点格式及 LUT 写入路径已有验证；A7 IV 的完整色彩算法和 ISP 处理没有复现。菜单和参数的 ARM 组件测试，也不等于模拟了相机传感器或 ISP。

## 当前安装记录（2026-11-11）

- 真机已安装 `/usr/lib/a7fl.so`，大小 42,208 字节，SHA-256 `2478cec27f88e838f03915da36ac09c66efff9d6a3bd53d59fc487f6cd345aac`。
- 简体中文和英文资源已写入，原资源分别链接为 `.a7fl-zh.orig`、`.a7fl-en.orig`。启动快照曾带回旧目录缓存：raw 目录使用新 inode 16687/16688，VFS 却恢复旧 inode 16523/16411。按原厂升级步骤使旧 WBI 头失效后，用户断电重启，新目录与两份完整语言资源校验均通过。没有在旧缓存视图中重复安装文件。
- 文件安装器完成阶段 100，三份文件均发布，两个原资源备份均存在，`/usr` 已恢复只读。安装日志位于 `/setting/A7FL.INSTALL`。
- 配置文件 `/setting/A7FL0.CFG` 已通过真实 ARM 文件读写、同步和回读验证，当前为 generation 1、FL 关闭。四张 LUT 回读仍为原厂值。
- 分页菜单修正版已写入：完整 `viewUnified2.so`（10,854,816 字节）SHA-256 为 `a1c4d8e88f54f71786ff53bc15a59c32a2969a6ffc934ef77728123d8af172a7`。修正日志 `/setting/A7FL.RETARGET` 完成阶段 100，3 个当前执行页面保留旧私有副本，`/usr` 恢复只读。保留已验证的启动钩子，恢复旧 GlobalMenu 调用，改接 SettingMenu 构造入口。新入口在下次冷启动生效。
- 首次 GlobalMenu 版本曾正常开机但未出现入口；只读状态确认模块加载和颜色初始化成功，配置为关闭、四张 LUT 保持原厂值。已据此改接实际分页 SettingMenu，并执行原始构造函数及初始化至菜单树深度初始化调用的 ARM 验证。
- **菜单显示、物理按键保存及拍照验收尚未通过。写入和回读成功不等于功能已可用。**

## 构建与验证顺序

原厂文件、已验证 RW 基线镜像、原始四张 LUT 和近似 FL 基表必须已经准备好。路径通过各脚本参数传入。主要工具如下：

| 步骤 | 工具 | 产物/检查 |
|---|---|---|
| 新增文字资源 | `research/native_fl_strings.py` | 保留全部旧条目，新增标签 |
| 原厂文字解析器验证 | `research/native_resource_fixture.py` | 原始 ARM 解析代码接受新资源 |
| 原生节点、保存动作、加载器 | `research/native_adjust_fixture.py`、`research/native_menu_action.py`、`research/native_menu_boot_loader.py` | 原始机器码的导航、生命周期、调用约定检查 |
| LUT 与配置 | `research/native_fl_runtime.py`、`research/native_store.py` | 预览、保存、恢复、断写和文件边界 |
| 平台绑定 | `research/native_bootstrap.py`、`research/native_bootstrap_test.py` | 固定机型/版本、代码字节、真实入口和页面身份 |
| 整合模块 | `research/native_module.py` | 编译实际模块并核对所有依赖证明 |
| 文件安装器 | `research/native_install_test.py`、`research/native_install_build.py` | 故障注入，绑定真实模块，生成安装负载 |
| 加载入口激活 | `research/native_menu_activate_test.py`、`research/native_menu_activate_build.py`、`camera/native_activate.py` | 原执行页隔离、原生文件写入、完整回读及撤销路径 |
| 重启后只读检查 | `research/native_inspect.py`、`camera/native_status.py` | 查询已加载模块、双槽配置及四张 LUT，不主动加载模块 |

所有证明都绑定源码和输入散列。修改源码后重新运行对应测试及依赖构建；不要手动将旧证明改成通过。`ready_for_staging` 只允许安装文件，真机运行和冷启动验收单独记录。

安装工具默认只做校验，明确指定写入操作才会修改相机：

```sh
python3 -m camera.native_install --offline
python3 -m camera.native_activate --offline
python3 -m camera.native_status --offline
# 首次文件安装；安装日志已存在时不要重复执行
python3 -m camera.native_install stage --write-device
# 同一连接先完成只读预检，再激活入口
python3 -m camera.native_activate activate --write-device
# 已装第一版入口的本机修正；先处理旧启动快照，校验新目录
python3 -m camera.native_activate --setting-menu --offline
python3 -m camera.native_activate --setting-menu preflight
python3 -m camera.native_activate --setting-menu activate --write-device
# 冷启动、操作机身菜单并接回后，读取真实运行状态
python3 -m camera.native_status
```

连接需要既有 UTM / Sony 服务模式交接环境。第一次物理冷启动后检查菜单和保存，再次冷启动后检查配置及 LUT 是否恢复；必须读取状态 JSON 的实际字段，不能仅凭命令退出码判断功能通过。

## 保存与恢复

自有配置使用 `/setting/A7FL0.CFG` 和 `A7FL1.CFG` 两个 128 字节记录，包含版本、原厂 LUT 身份、代数、开关、参数和校验。新记录同步并回读后才作为已保存设置；未知文件不会被覆盖。断写后可以读取上一份有效记录，损坏槽位需要明确恢复才能继续保存。

LUT 写入使用原厂 Backup 接口，写后核对完整 1280 字节。恢复时要求机型、内部版本及另外三张原厂表一致，并将当前表逐字节识别为本模块生成的候选；未知校准数据会被拒绝。不能假设不调用显式保存就永远不会被其他原厂保存操作带入存储。

系统分区使用内核文件接口安装完整候选文件，通过链接保留旧资源、重命名发布、同步和回读，最后恢复只读。原来的小扇区写入器没有新文件分配能力，不适用于这一步。安装日志存在时先检查状态，禁止盲目重复安装或删除日志。

Sony 的 Warm Boot Image 位于独立非易失分区，取出电池不会丢弃它。新增文件或重命名目录项后，需要检查启动快照是否恢复了旧 inode/目录缓存；原始目录与 VFS 不一致时不得重复安装。原厂小版本升级流程会使 WBI 头失效。本项目工具先完整备份并绑定实际 1024 字节，只清零 `/dev/nflasha5` 开头的 512 字节，再确认相邻 512 字节不变；不自动恢复旧快照。`camera.native_wbi` 默认只读，`camera.native_wbi_write` 需要经过核对的绑定包和 `--write-device`。此次失效及独立回读通过，随后冷启动确认新资源可见，WBI 头仍为零。

最终验收需要断电重启后检查：入口可见、FL 开关有效、五个参数可调、保存后重启保留、关闭后恢复原厂色彩、原 RW 功能正常，以及正常 JPEG 拍摄和回放。
