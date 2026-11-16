# 配方：SD 导入与独立风格

**当前已验收功能和操作以 [完整包说明](custom-look-release.md) 为准。** 新增外观使用 `A7FL-LOOK/1`；下方包含早期六套参数覆盖工具及历史研究记录，不代表当前同级入口仍使用旧 PATCH 格式。

配方 JSON 只保存当前风格及 FL 到 FL6 的 96 个控制值（每套 16 项），不带机身身份、固件内容、照片或存档代数。可以分享或手工编辑；同一配方能否在另一机型呈现相同颜色，取决于该机型的色表和图像处理。A7C 尚未接通。

`tools/look_recipes.py` 用 A7 III 4.04 六风格版的两份 schema 6 设置快照生成离线候选及菜单差异。导入真机使用下方单独的命令，无需重刷固件，不直接复制候选文件。

命令在仓库根目录执行；`snapshot` 指向最近一次只读工具导出的两个配置文件，`build` 是对应的六风格构建目录。默认原厂数据目录是 `.lab/native-fl-01`，其他位置使用 `--bundle`。导出只需要 Python；导入准备另需 C 编译器以及匹配的本地构建；预览另需 Pillow 和字体。

```sh
snapshot=/path/to/settings-snapshot
build=.lab/native-module-six-auto-size
python3 tools/look_recipes.py export \
  --slots "$snapshot/preference-0.bin" "$snapshot/preference-1.bin" \
  --out looks.json

# 编辑 looks.json 后生成色卡和导入差异。
python3 tools/look_recipes.py preview --recipe looks.json \
  --build "$build" --out looks.png
python3 tools/look_recipes.py import --recipe looks.json --build "$build" \
  --slots "$snapshot/preference-0.bin" "$snapshot/preference-1.bin" \
  --out import-trial
```

预览用机内相同的色表生成代码展示前五项色彩调节和五点曲线。色卡采用近似显示模型，不包含颗粒、光晕或暗角。导入拒绝重复字段、缺项、未知字段和越界值；核对原机配置、色表 CRC 后才生成 `candidate.cfg`。`plan.json` 列出改动的风格、参数和目标值，也记录候选对应的旧配置散列。

首次试验从真机备份导出六组设置，修改 FL6 的色彩、曲线和三项拍后参数，然后重新生成候选。原生配置解码器确认全部 96 个控制值正确，其余五组保持原值。

## 导入到 A7 III

适用已经装有 v0.01 L／M／S 六风格模块的 ILCE-7M3 4.04。需要现有 UTM USB 实验环境、ARM 工具链、该模块的本地构建、部署绑定及只读检查器。先在机身保存或取消当前未保存的创意外观改动，再在大容量存储模式下分配给 UTM。

```sh
python3 tools/import_look_device.py --recipe looks.json \
  --build "$build" --binding /path/to/binding/18 \
  --probe .lab/native-inspect-auto-size
```

默认只预检，输出改动的风格和 `ready`。已保存配置和当前运行状态一致、确认配方是要导入的内容后，使用相同命令加 `--write`。工具在本机完整备份两个设置槽和两个工作记录，再使用机身与原保存功能相同的写入器更新较旧的设置槽。它会核对四份前像，保留当前已保存槽，完整回读新槽和其余记录。若失败，按证据检查后再处理，不重复写入。

只想导入一项时，可加 `--only FL6.grain`（以 FL6 颗粒为例）。工具以机身本次读出的已保存设置为底稿，只替换指定数值，保留当前已保存的风格和其余设置。

看到 `IMPORT_VERIFIED_REBOOT_REQUIRED` 表示设置文件写入并回读一致。重启前不要继续编辑或保存创意外观。关机再开机后，进菜单核对导入值；冷启动加载仍需单独验证。如果菜单值不符，先不要再次保存或重写，重新运行只读预检，对比两份设置槽、运行代数和菜单值。`IMPORT_SAVED_VALUES_MATCH` 只表示当前设置文件的值与配方相符，不代表取景、菜单或拍摄端已经加载。预检和备份存放在 `.lab/recipe-device-import/`。

### SD 卡导入原型

补充接口验收：`.lab/sd-fsys-probe/1794815389677695000`。
三个盘符目录结束返回 2；读取 25 字节后再读一个字节，
EOF 为 1、PrFILE 错误码为 8（正常 EOF），关闭返回 0。
外部 Fsys 盘符会随重连变化，而且不能直接当作 pf2 的内部盘符。
通过原厂 `GetDriveInfoFromFindInfo` 获取目录所属设备，再按原厂
`fsys_CreatePathInfo` 使用设备记录偏移 10 的内部盘符，测试文件读取成功。
后续菜单必须保留选中项所属设备，不得用显示盘符直接调用 pf2。
通用读取模块已接入此映射；确认前重新检查设备映射和文件内容。

真机读卡证据（2026-11-16）：`.lab/sd-fsys-probe/1794815080545852000`。
原厂 Fsys 根目录枚举确认 B 盘包含 `FL6-grain-1.a7look`，
随后用已加载库的 `pf2_fopen("B:/FL6-grain-1.a7look","rb")`、
`pf2_fread(buffer,1,25,file)`、`pf2_fclose(file)` 读取并关闭，
返回读取数 25、关闭结果 0，内容与测试配方逐字节一致。
这证明维护连接下原厂长文件名读取可用，尚不代表正常拍摄模式菜单线程
中的锁、上下文及重复导入已经验证。生产读取需在选卡后建立对应上下文，
不能固定 B 盘，也不能用测试的定长 25 字节读取替代有上限的完整读取。
文件列表排除 Mac 生成的 `._` 元数据文件。

当前目标格式：卡根目录中任意文件名、后缀为 `.a7look`（大小写不敏感）。
菜单应列出匹配文件，让用户选择并确认改动。文件只覆盖列出的参数；
未列出的参数及当前风格保持原值。例如 `recipes/FL6-grain-1.a7look`
只指定 `FL6.grain=1`。格式首行为 `A7FL-PATCH/1`，后续为
`风格.字段=整数`，拒绝未知字段、重复项及越界值。
`tools/sd_look_recipes.py` 已实现电脑端列举、解析和合并；
机身 C 解析器与动态文件选择已接通，最多列举 32 个配方，每个文件不超过 16 KiB。
只扫描已挂载盘的根目录；文件名后缀大小写不敏感。

2026-11-16：现有 USB 单项导入已通过完整断电验收。用户取出电池后确认
FL6 颗粒显示 1；回读运行代数 70，内核运行约 58 秒，运行与保存值均一致。
与导入前逐项比较，仅 FL6 颗粒 0→1，其余 95 项不变。
证据 `.lab/auto-size-resident-read/1794813644523737000/auto-size-status.json`。
此前显示 0 时运行代数仍是 69、内核运行约 78 分钟，不能视为冷启动失败。
上述断电验收属于 USB 导入，不代表 SD 菜单已在真机验收。

当前 SD 候选增加「创意外观」第 4 页的「从 SD 卡导入」。
弹框显示含盘符的实际文件名，左右选择，确认选中文件后再确认导入；
成功显示「完成」。MENU 取消不写设置。确认前重读文件并检查内容与设置代数，
拒绝读卡错误、未知字段、重复字段、越界值和未保存的当前修改。
沿用机内保存事务，保持当前风格及未指定参数不变。

`research/native_sd_integration_test.py` 构建并运行 ARM QEMU：
真实原厂节点/按键指令与模拟文件系统结合，覆盖动态文件名、选择、确认、
取消、读取失败、确认前文件改变，以及 FL6 grain=1 只改指定字段；
六风格、曲线、拍后参数回归及已有配置启动恢复通过。
这仍是离线测试，正常拍摄模式与物理断电验收单独记录。
`research/native_fl_sd_strings.py` 追加四条中英文资源，入口 ID 0x0204fdb5；
原厂 ARM 资源解析器检查 91,289 项通过。其余旧条目保持一致。

安装入口为 `deploy_sd_import.py`，仅用于当前匹配前像的候选试装，
不自动重试已有日志；先追加两份资源，最后替换模块，每个文件保留独立备份、
执行完整回读，配置槽与工作记录安装前后字节比对。
候选包 `.lab/native-fl-releases/update-v001-sd-import-zgow4zto`。
用户已明确同意先安装候选，再进行机内菜单验证。
目前不得把此候选写成已通过正常拍摄模式验收的正式版本。

历史维护模式挂载记录仅显示内部闪存与临时文件系统，没有 SD 卡。
因此不能据此指定卡路径；还需要正常拍摄模式下的存储卡访问证据，
不能使用 Alpine 虚拟机的挂载表代替机身挂载表。

原厂 4.04 的更新脚本 `udtrbody.bin_unpacked/bin/startupdate.sh` 明确先将
`/dev/nflasha1` 挂到 `/mnt`，再复制 dat2/dat3 作为机型和区域数据；
因此 `/mnt/dat2`、`/mnt/dat3` 已排除，不能作为 SD 卡目录。
`libmintx.so` 的 `PplFileOpen`（0xd6ab8）直接调用 libc open，
`PplFileRead`（0xd6b42）直接调用 read；它们不是已确认的存储卡专用接口。
`libmpr.so` 的 SD 卡判断与文件管理日志仍仅为线索。

进一步找到原厂相机配置读卡调用链：`libInfraCameraProfile.so` 的
`DataBaseCameraProfile::CacheProfileData` 在 0x800c 调用
`Fsys_Open(path, &handle, 1)`，在 0x804e 调用
`Fsys_Read(handle, buffer, length, &handle)`（第四寄存器是否为有效
参数仍需核对被调用函数），0x8086 调用 `Fsys_Close(handle)`。
这些接口由 `libInfraFsys.so` 导出；盘符查询为 `Fsys_GetDriveLetter`，
函数内部使用设备锁和设备到盘符映射。因此应验证原厂 Fsys 路线，
不能继续把 POSIX 挂载路径当作读卡前提。尚未在真机调用这些候选接口，
尚未确认设备 ID、读返回值及正常拍摄时的调用线程要求。
`AvbbcFileReader` 同时用于系统声音，因此它的存在不能证明可访问存储卡。
不得把这些字符串直接绑定为已验证的 SD 路径。

2026-11-16 候选安装完成：`write-1794816564912805000/verified.json`
记录三个目标文件及旧文件备份完整回读一致；四份配置未变，/usr 只读。
已请用户完成机内选择、确认、保存及两次彻底断电验证，尚未收到结果。
导入前 FL6 颗粒原本已经为 1，应核对代数 70 是否因机内导入增加，
并逐项比较其余参数；仅显示 1 不能单独证明本轮导入执行。

2026-11-16 正常模式验收完成：用户确认文件可选、确认导入显示完成，
再次取出电池后 FL6 颗粒仍为 1。只读证据
`.lab/sd-import-acceptance/1794816787209226000/acceptance.json`：
保存代数 70→72，运行与保存同为 72，mode6，无未保存修改或故障，
内核运行时间约 135 秒。三文件散列匹配，全部 96 项参数与安装前一致。
本次为相同值导入（原来已为 1），不是数值从 0 改为 1 的测试；
代数推进及用户机内操作反馈共同证明走过保存流程，不推断精确操作次数。
只读复核工具 `research/sd_import_acceptance.py` 不写设置或固件。

### 下一阶段：导入为新增独立风格（尚未装机）

用户明确修正目标：入口放在「创意外观」上一级，导入后增加独立风格，
不能再以覆盖 FL1～FL6 的参数冒充新增。现有已验收 SD 导入仅是参数补丁。

`tools/custom_look_recipes.py` 新增独立格式 `A7FL-LOOK/1` 的主机原型：
稳定配方 ID、自定义显示名称、基础色彩风格和完整 16 项独立参数。
导入分配从 7 开始的独立编号，重复 ID 明确拒绝，不隐式覆盖；配方库
进行内容校验，序列化后可恢复。原型暂设 16 个扩展项上限，非真机容量结论。
旧 `A7FL-PATCH/1` 不会作为新增配方接受。主机回归测试已通过。

新增风格引用现有六个色彩基底，携带独立名称和16项参数，不包含自定义 LUT。
原 schema6 六风格配置仍保留在 A7FL0/1.CFG；新增库单独使用
`/setting/A7CU0.CFG`、`A7CU1.CFG` 双槽，包含选中编号和保存代数。
重复配方 ID 拒绝覆盖。导入不自动切换当前风格；选择新增风格后需要保存。
存在未保存修改时先保存或取消，不能隐式丢弃修改后导入。

2026-11-16 已整合并安装候选，正在等待正常拍摄模式验收：

- 同级「从 SD 卡导入」动作接入原厂菜单；任意文件名、`.a7look` 后缀。
- 导入 `A7FL-LOOK/1` 后追加原厂选择节点，独立编号从7开始；旧
  `A7FL-PATCH/1` 参数补丁不当作新增风格导入。
- 动态 UTF-8 名称通过原厂 `GEN_Label::setTextDirect` 绘制，限定自己菜单的
  控件和新增资源编号；保留资源身份用于后续刷新。
- 生产 `model_write` / `film_change` 使用新风格的独立工作副本，调用已有
  取景/CAP配色生成及颗粒、光晕、暗角适配器，不借写原 FL6 保存槽。
- `commit_checked` 将新风格及选中状态保存到独立双槽；启动时先恢复原六套
  配置，再恢复独立风格。返回原 FL 时恢复原参数。
- 独立存储校验普通文件、大小、CRC、完整前像及写后回读，fsync文件及新目录项。
  一个槽损坏时只读恢复另一个槽，拒绝自动覆盖损坏槽。

测试入口 `research/native_custom_integration_test.py`：原厂 ARM 节点选择、
同级导入→确认→追加→独立选择→实际配色函数→独立保存、冷启动恢复；
原六套配置字节不变。原厂弹框生命周期测试及动态文字测试中，控件和绘制仍有
模型依赖，不能替代相机 LCD 验收。`custom_look_posix_test.c` 在本机实际临时
文件上测试写入、前像、fsync失败、符号链接和超长文件拒绝。

候选模块 SHA-256 `fc25a8f9f430c01f1f8c6f130ebf1d603d815c8041401712bec6ec1697c447e2`，
149344字节。安装包 `.lab/native-fl-releases/update-v001-custom-looks-gw1l8spw`；
`write-1794819564533584000/verified.json` 记录三文件完整回读通过，原六套配置
及工作记录字节不变，/usr恢复只读、view及WBI未变。禁止重放此包。

卡根目录测试文件 `Portrait-grain-1.a7look`，显示名「人像颗粒 1」，复制安装前
FL6的16项参数并指定grain=1（原FL6已为1）；不以该值证明发生0→1。
应检查确实新增独立选项、保存代数、断电后选中编号，以及原六套记录保持不变。
正常取景/JPEG及实际中文名称仍须用户冷启动试用和只读回读共同验收。

2026-11-16 真机异常与修正：首个独立风格候选 fc25a8f9 在用户进入
创意外观时整机重启，未通过验收。回读原六风格配置未变，新库尚不存在。
原动态文字实现遍历底层子控件，并错误使用 PAS_LabelCustom 的类型转换
处理异构节点；改为只访问原厂分类菜单七行内已核对的内嵌 GEN_Label。
这是已确认的实现错误，因重启后没有保留崩溃栈，不声称是唯一故障原因。
新回归测试禁止调用异构树遍历，检查行内文字偏移和原菜单隔离，完整
导入/配色/保存/冷启动回归通过。修正版模块87e8f719（149632字节）已安装
并完整回读，等待用户再次验证。独立库、六风格配置及工作记录不改动。

2026-11-16 新增删除与下拉名称候选：模块2e13c731，153104字节，已安装并
回读一致，等待真机验收。原厂 popup 的文字行与分类菜单主行不同，新增对
嵌入 popup 六个 GEN_Label 的定点名称更新，继续禁止异构控件遍历。

在「创意外观」选中新增外观，第4页点「删除」；确认页显示准确名称。
取消保持原状态，确认后删除该外观及其未保存调整，并返回原内置风格。
内置 FL～FL6 的删除行不可用，SD上的.a7look文件保留，可再次导入。
独立库保存代数递增，剩余自定义列表按顺序排列；内部位置编号会压紧，
配方字符串ID不变。主机及原厂ARM整合测试覆盖取消、确认、原六套保留、
删除后冷启动、连续删除和再次导入。正常模式表现仍需用户反馈。

## 下拉名称修正的最新真机状态

**2026-11-16 最新安装：下拉文字设置回调修正版，待冷启动名称验收。** 上一版删除已获用户确认，且 `.lab/custom-delete-acceptance/1794821408695896000/acceptance.json` 只读核对：独立库 generation4/count0/active0，原六套 generation72 不变、运行正常；但用户仍报告下拉占位名，故不能宣称上一名称修复有效。本版对原厂 GEN_Label::setText 数据虚表槽进行精确前像核对并接入回调，先运行原厂设置，再仅对已存在自定义资源编号使用配方名称；覆盖下拉独立重设文字路径，保留原删除功能。离线 NATIVE_POPUP_TEXT_DISPATCH_PASSED、导入/删除/冷启动链路和 47796 项更新核心检查通过，尚不是实际显示验收。

已执行包 `.lab/native-fl-releases/update-v001-custom-text-0xpff8wf`，证据 `.lab/native-fl-releases/update-v001-custom-text-0xpff8wf/write-1794821851625217000/verified.json` 与 `catalog-preserved.json`。模块 `a820f62cbea336e16b945f95278ed760a1b0190ca97e6576e23113ac2991cdf9`（153424 字节），完整回读一致，四份原设置及两独立库槽保持不变，语言/view/WBI 不变、/usr只读。禁止重放包。首次预检因 /usr 仅剩117KB停止，未发送替换载荷；已将旧崩溃候选 `.a7fl-fc25a8f9.orig` 完整归档到 `.lab/custom-failed-backup-archive/1794821829570873000`，散列校验后仅移除该机内副本，当前及最近备份保留。随后正常预检与写入通过。下一步冷启动，重新导入 SD 上 Portrait-grain-1.a7look 后检查下拉名称与滚动返回；不再要求重复删除验收。


## 选定值名称修正

**2026-11-16 最新安装：选定值名称修正，待冷启动验收。** 用户确认上一版下拉名称正确，但选定后仍显示自定义占位名称。补接 viewUnified2 的 GEN_Label::setText 直接导入槽和 setVariantInfo 导入槽，严格核对指针前像，先执行原厂函数，仅对当前自定义资源编号恢复配方名称；下拉虚表回调和删除功能保留。离线 NATIVE_SELECTED_TEXT_DISPATCH_PASSED 覆盖选中值、格式化覆盖、切回内置项；下拉/导入/删除/保存/启动回归通过，49683项更新核心检查通过。尚未证明真机选定名称已修复。

包 `.lab/native-fl-releases/update-v001-custom-selected-hfjp6yjd` 已执行，证据 `.lab/native-fl-releases/update-v001-custom-selected-hfjp6yjd/write-1794822281280608000/verified.json`、`catalog-preserved.json`；新模块 `b3d387dfb2dbfa3d58adbcb5bcc8a07df4bb80339c74fbf2ed38bdeb47c31fe3`（153740字节），完整回读一致、四份原设置和两份独立库不变、view/WBI/语言不变、/usr恢复只读。禁止重放。为留出空间，较早备份 `.a7fl-87e8f719.orig` 已完整归档校验至 `.lab/custom-old-backup-archive/1794822262331409000` 后才移出机身；当前前像a820f62c和上一个2e13c731回退副本保留。等待用户冷启动后选人像颗粒1、收起列表、切回FL再选回、保存重启验收。只读后验工具 `research/custom_selected_acceptance.py`，要求用户已选择新项并保存。


## 名称修复验收

**2026-11-16 名称修正已验收。** 用户确认下拉和选定后均显示正确名称，重启正常；删除功能此前也已验收。只读证据 `.lab/custom-look-incident/1794822522384389000/name-acceptance.json`：当前模块 b3d387dfb2dbfa3d58adbcb5bcc8a07df4bb80339c74fbf2ed38bdeb47c31fe3 正常加载、fault0/last_error0，原六套双槽与安装前逐字节一致；独立库 generation7/count1，名称「人像颗粒 1」和全部配方参数保留。保存 active0、运行dirty1；用户已明确确认测试后又切换或未保存选中状态，属于预期操作，不将其当作恢复缺陷，也不宣称当前保存的选中项是自定义。只读过程中未修改设置。初版后验脚本误拒绝合法空旧槽，已修正；其 active7 特定测试条件本轮不满足，所以最终验收按用户实际状态另行记录，未绕过或伪造该条件。未提交或发布本轮改动。

## 原六套删除候选（未发布）

**2026-11-16 最新安装：原 FL～FL6 可删除候选，待真机验收。** 用户要求原六套也支持删除，并清理 SD 旧测试配方、放入六份供手动导入。已安装 `.lab/native-fl-releases/update-v001-builtin-delete-det1551f`，完整写入回读 `.lab/native-fl-releases/update-v001-builtin-delete-det1551f/write-1794823873424896000/verified.json`、`catalog-preserved.json`；模块 `a6545d1306c78872b2b28acecb3640d139cd6919a5818e5aa3de4ecb4870e927`（155148 字节），原四份设置与独立库安装时逐字节未变，view/WBI/语言不变、/usr只读。未自动删除任何风格。禁止重放包。

删除原风格使用独立库的 hidden_builtin 位图移除其菜单项，保留基础配色算法及原银行参数以支持 SD 重新导入；删除当前项立即转关，重启继续过滤已删除项。稳定内部编号与可见下标分离，名称/拍摄选择不随列表缩短串位。原 A7CU schema1 兼容读取；首次删除内置项时写同长度2848字节 schema2（count低8位，hidden_builtin高位六位），旧模块不支持该格式，不直接回退而不处理配置。离线真实 ARM 菜单删除/重新导入/两处位置压缩、冷启动恢复、六套全部删除后导入配方、失败路径通过，更新核心51570项检查通过。尚未实际验收机内原 FL 删除。

SD 卡120.6GB根目录已写入 FL.a7look、FL2.a7look 至 FL6.a7look，来自安装前 generation72 六套实际参数（不是重置默认）。本地 `.lab/sd-six-look-export/export-manifest.json` 记录散列。两份旧测试 FL6-grain-1.a7look、Portrait-grain-1.a7look 和对应 AppleDouble 元数据在 `.lab/sd-recipe-cleanup/1794823525354038000` 完整备份后移除；照片不动。六份新文件已回读校验、安全推出，用户接回UTM。Mac自动生成的 `._FL*.a7look` 已由原解析器明确过滤。用户准备自行导入，不代其执行。安装前较旧2e13c731副本归档校验后移出机身以腾空间，证据 `.lab/custom-old-backup-archive/1794823847948598000`；b3d387df和a820f62c回退副本仍在。此候选未提交或更新公开v0.01。

## 即时列表及连续选择修正（未发布）

**2026-11-16 最新安装：导入即时列表与连续选择修正，待用户验收。** 原可删除候选 a6545d13 验收失败：用户报告导入后需重启才能看到，导入后无法选择其它。只读 `.lab/custom-look-incident/1794824196048816000` 确认运行无fault、dirty1；独立库schema2/gen12/count2/hidden6（原FL2、FL3已删除），存在导入FL2和FL3。不得把该候选作为已验收版发布。

现候选跟踪原厂模式节点副本，在列表变化时更换其独立指针数组、同步数量和选中位置；原厂克隆仅浅复制子指针，销毁旧数组时剔除借用的嵌入节点，避免清掉模板父关系，析构注销注册。取消切换时必须先保存的条件；未保存自定义参数保留在工作库，回到内置风格后保存也提交工作库；切入自定义前保留内置工作参数。真实ARM测试新增预先打开的列表副本经历导入/删除/再次导入、析构和连续未保存切换，NATIVE_LIVE_CLONE_SELECTION_PASSED；冷启动、拍摄源表、原菜单树回归通过。不是实机验收。

已执行 `.lab/native-fl-releases/update-v001-live-list-zp6tdr0i`，证据 `.lab/native-fl-releases/update-v001-live-list-zp6tdr0i/write-1794824541467165000/verified.json` 与 `catalog-preserved.json`。新模块 `30474345352eaed6b1feb8f33e389278febaeb6c3fc493dc2355ab560ca591a4`（155840字节），完整回读通过，四份原配置和两份独立库字节不变，view/WBI/语言不变、/usr只读。禁止重放。较早a820f62c副本归档于 `.lab/custom-old-backup-archive/1794824518165258000` 后移出机身腾空间，当前前像a6545d13和b3d387df备份保留。等待冷启动后先连续选择FL/已导入FL2/FL3，再从卡导入FL4.a7look检查不重启立即可见、可切换。不擅自清除用户配方或参数。尚未提交或发布。

## 即时列表真机验收

**2026-11-16 即时列表与连续切换修正已获真机验收。** 用户确认导入后立即出现、连续切换正常。只读 `.lab/custom-look-incident/1794824744407403000/live-list-acceptance.json`：模块30474345正常加载，fault0/last_error0；独立库schema2/gen14/count3，FL2、FL3、FL4独立配方已保存；hidden_builtin=14，对应原FL2/3/4已移除。原六套A7FL双槽与本次安装前逐字节一致。当前运行base4、dirty1，保存active0，因此只确认配方内容与删除位图持久化，不宣称最后选中项已保存；无需为界面验收强制用户额外操作。此轮未写入相机，只读取记录；尚未提交或覆盖v0.01，公开包仍为0eab97e版。
