# 真机「创意外观」实验模块

构建范围是自有 ARM 驻留模块、菜单资源和原厂加载入口补丁。Sony 固件主体使用经过散列校验的 ILCE-7M3 4.04 二进制，内部版本为 `37114_13.2026020901`。固件、相机备份、照片和生成的安装包只保存在忽略提交的 `.lab/`。

## 入口与功能

首版目标入口：**MENU → 拍摄设置 1 → 第 14 页 → 创意外观**。它与创意风格同级，保留原页的防闪烁拍摄、人脸登记及登记人脸优先三个项目，也保留已有「复古衣橱」和 RW 图标修改。

选择关或「FL（实验版）」；对比度、高光、阴影、褪色、饱和度直接生成机内 LUT 的变化。修正版分成两页：第一页为开关和五项色彩调节，第二页为三个尚未实现、保持置灰的空间调节项及「保存」。调节先预览，选择「保存」才提交自有配置。r3 在提交成功后把按钮文字变为「完成」，新修改产生未保存设置时恢复「保存」，提交失败显示「未完成」；使用现有中英文文字资源。首版只接入静态拍摄菜单，使用已验证的表 0 通路；图片配置文件和照片效果应保持关闭。

这是自制近似 FL。原厂非线性色度编解码、节点格式及 LUT 写入路径已有验证；A7 IV 的完整色彩算法和 ISP 处理没有复现。菜单和参数的 ARM 组件测试，也不等于模拟了相机传感器或 ISP。

## 当前安装记录（2026-11-11）

- 真机已更新 `/usr/lib/a7fl.so` 为 r3，大小 43,160 字节，SHA-256 `f3e2d657a83569f19ddafcd843a40601f1d953da0a20a8f8617c5e299e73a063`。r2 模块（42,812 字节，SHA-256 `e64867d24764725dfaf621e2ab9611f6d389f15b21cf6dad7daacd1c618492e1`）保存在 `/usr/lib/.a7fl-e64867d2.orig`，更早的 `/usr/lib/.a7fl-2478cec2.orig` 也保留。
- 简体中文和英文资源已写入，原资源分别链接为 `.a7fl-zh.orig`、`.a7fl-en.orig`。启动快照曾带回旧目录缓存：raw 目录使用新 inode 16687/16688，VFS 却恢复旧 inode 16523/16411。按原厂升级步骤使旧 WBI 头失效后，用户断电重启，新目录与两份完整语言资源校验均通过。没有在旧缓存视图中重复安装文件。
- 文件安装器完成阶段 100，三份文件均发布，两个原资源备份均存在，`/usr` 已恢复只读。安装日志位于 `/setting/A7FL.INSTALL`。
- r2 机身按键测试后只读确认：`/setting/A7FL1.CFG` 为 generation 2、FL 开启、对比度 +1，其余参数默认；运行状态 `dirty=0, fault=0, last_error=0`，与保存配置及实际 LUT 一致，另外三张 LUT 为原厂值。旧 generation 1 关闭配置仍保存在另一个槽位。
- 分页菜单修正版已写入：完整 `viewUnified2.so`（10,854,816 字节）SHA-256 为 `a1c4d8e88f54f71786ff53bc15a59c32a2969a6ffc934ef77728123d8af172a7`。修正日志 `/setting/A7FL.RETARGET` 完成阶段 100，3 个当前执行页面保留旧私有副本，`/usr` 恢复只读。保留已验证的启动钩子，恢复旧 GlobalMenu 调用，改接 SettingMenu 构造入口。用户随后冷启动确认入口可见。
- 首次 GlobalMenu 版本曾正常开机但未出现入口；只读状态确认模块加载和颜色初始化成功，配置为关闭、四张 LUT 保持原厂值。已据此改接实际分页 SettingMenu，并执行原始构造函数及初始化至菜单树深度初始化调用的 ARM 验证。
- 用户已确认入口出现，但调节/保存无法使用，后续页面出现数值列表。回读为 `installed=1, fault=0, mode=0, dirty=0, generation=1`，LUT 仍为原厂。已定位缺少原厂子菜单 Page 层，以及负数不能直接作为界面枚举值。旧树经原厂分页函数会被解释为九页；旧 Save 节点经原厂选中行访问器得到空子项。
- r2 新增 Page 层，原厂访问器与动作处理函数能派发第二页第四项 Save；界面使用非负枚举，后端参数与存储仍为有符号值。颜色算法、保存格式及 LUT 基表未变。单模块更新日志 `/setting/A7FLUP1.LOG` 已完成阶段 100，新模块及旧备份完整回读通过，加载器与 WBI 均不变，`/usr` 恢复只读；后续调节及保存回读结果见下。
- 更新器预检曾错误要求所有文件归 root 所有，因而在阶段 1006 拒绝原厂目录，没有开始写入。依据已有真机元数据修正为按路径核对所有者后，r1b 更新器通过预检并完成上述更新；没有修改相机文件权限。
- 用户对 r2 反馈「点保存没有反应，其它正常」。回读证实 Save 已成功写入配置，问题是没有显示反馈。r3 只补按钮反馈，不改变 LUT 算法或配置格式；`/setting/A7FLUP2.LOG` 完成阶段 100，新模块、r2 备份和原加载器完整回读通过，WBI 不变，`/usr` 恢复只读。
- **r2 的调节及保存已获用户操作和回读证据；r3 的可见反馈及保存后冷启动恢复仍待机身验收。**

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
| 已装模块更新 | `research/native_module_replace_bind.py`、`camera/native_module_replace.py` | 仅在已知旧模块和加载器基线上，用新 inode 原子替换模块，保留旧模块备份 |
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

以下为已执行的 r2 单模块更新记录；保留用于追溯，不重复执行首次安装、入口激活或已完成的更新：

```sh
python3 -m camera.native_module_replace replace --binding .lab/native-module-replace-bound-r1b --offline --write-device
python3 -m camera.native_module_replace replace --binding .lab/native-module-replace-bound-r1b --write-device
```

r3 使用已知 r2 模块作为原像，绑定 `--revision 2` 的更新器，保留上一轮日志与备份。以下写入已在本机完成，不要重复执行：

```sh
python3 -m camera.native_module_replace replace --binding .lab/native-module-replace-bound-r2 --write-device
# r3 当前只读状态检查
python3 -m camera.native_status --bundle .lab/native-install-bound-r3 --module-proof .lab/native-module/proof.json
```

该更新固定匹配旧模块 `2478cec2…`、新模块 `e64867d2…` 和加载器 `a1c4d8e8…`。同一认证会话核对机型、版本、旧完整文件及 WBI 为零，再原子发布 `/usr/lib/a7fl.so`；旧模块保存在 `/usr/lib/.a7fl-2478cec2.orig`。更新完成要求 `/setting/A7FLUP1.LOG` 完整、全文件回读一致、`/usr` 恢复只读。原进程仍映射旧 inode，新版在冷启动后加载；工具不会自动重试已有更新日志。

连接需要既有 UTM / Sony 服务模式交接环境。第一次物理冷启动后检查菜单和保存，再次冷启动后检查配置及 LUT 是否恢复；必须读取状态 JSON 的实际字段，不能仅凭命令退出码判断功能通过。

## 保存与恢复

自有配置使用 `/setting/A7FL0.CFG` 和 `A7FL1.CFG` 两个 128 字节记录，包含版本、原厂 LUT 身份、代数、开关、参数和校验。新记录同步并回读后才作为已保存设置；未知文件不会被覆盖。断写后可以读取上一份有效记录，损坏槽位需要明确恢复才能继续保存。

LUT 写入使用原厂 Backup 接口，写后核对完整 1280 字节。恢复时要求机型、内部版本及另外三张原厂表一致，并将当前表逐字节识别为本模块生成的候选；未知校准数据会被拒绝。不能假设不调用显式保存就永远不会被其他原厂保存操作带入存储。

系统分区使用内核文件接口安装完整候选文件，通过链接保留旧资源、重命名发布、同步和回读，最后恢复只读。原来的小扇区写入器没有新文件分配能力，不适用于这一步。安装日志存在时先检查状态，禁止盲目重复安装或删除日志。

Sony 的 Warm Boot Image 位于独立非易失分区，取出电池不会丢弃它。新增文件或重命名目录项后，需要检查启动快照是否恢复了旧 inode/目录缓存；原始目录与 VFS 不一致时不得重复安装。原厂小版本升级流程会使 WBI 头失效。本项目工具先完整备份并绑定实际 1024 字节，只清零 `/dev/nflasha5` 开头的 512 字节，再确认相邻 512 字节不变；不自动恢复旧快照。`camera.native_wbi` 默认只读，`camera.native_wbi_write` 需要经过核对的绑定包和 `--write-device`。此次失效及独立回读通过，随后冷启动确认新资源可见，WBI 头仍为零。

最终验收需要断电重启后检查：入口可见、FL 开关有效、五个参数可调、保存后重启保留、关闭后恢复原厂色彩、原 RW 功能正常，以及正常 JPEG 拍摄和回放。
