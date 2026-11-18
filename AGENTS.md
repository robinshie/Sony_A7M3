# A7M3 默认开发和发布流程

**2026-11-18 用户授权发布 FL7 湿版黑白完整包。** 用户要求提交、同步 main、用完整包覆盖同一个 v0.01，不单独发 r；最后重启状态回读已明确选择稍后，不再联系相机。`tools/package_wet_release.py` 检查此前完整安装回读、原配置保留、同一内核 L/M/S JPEG 和用户冷启动／开关确认，清单明确 `post_boot_status_readback_verified=false`。当前模块 ece2cf2c、内核 a5ef0861；本次只发布读取验收过的模块和公开素材，不上传 .lab、照片、个人配方或机身备份。发布步骤：提交后生成同名 ZIP，同步 main／开发分支和 v0.01，覆盖固件附件并回下载校验；保留已有电脑工具附件及其独立版本说明。

**2026-11-18 湿版黑白已获用户实机验收，最后只读状态核对待 USB 重连。** 用户明确确认「FL7 黑白正常，原有风格开关正常，重启保留」。验收记录 `.lab/wet-plate-acceptance/1795004610806491000/user-acceptance.json`。最后只读工具在正常USB接口初始查询时遇到 Pipe error，尚未进入服务模式、未回读新状态，无持久写入；不要将此错误当作黑白功能失败，也不要声称已读回重启后的错误计数。用户已选择「稍后再回读」，停止相机操作；后续用户愿意接回时再运行下方 wet_plate_acceptance 命令，无需重复拍照。安装本身此前已经全文件回读通过，本轮不再次刷写。未提交或发布。

**2026-11-18 湿版黑白完整菜单候选已写入，等待用户冷启动验收。** 用户刚完成同一内核临时 L→M→S 实拍，三张均为黑白、拍摄回放正常；实际源帧样本与三张 JPEG 核对通过，completed3/failed0，三图 RGB 通道差均0。内核 `.lab/capture-kernel/1795003342232639000/a7capwet.ko` SHA `a5ef08615a085f3c33940ad0f5081a5910498e58534fe9dfcae27b4bfa8f54fa`。临时回调在采集后已停用，新持久模块需彻底断电后加载。不要把临时拍照通过等同完整菜单冷启动通过。

已执行 `.lab/native-fl-releases/update-v001-wet-plate-6pocs7rl`；证据 `write-1795004322417930000/verified.json`、`catalog-preserved.json`。模块 SHA `ece2cf2c868ddb66cc3c18265abcdc398909e4796cc3c7836e63c47eac99ae31`（159528字节），简中 `1753d4bb32a1def8ba58b58804bf51224249f2191bdf30619fe31889c9b39be0`、英文 `9ac34660932e91e8af98cc0e690180b26a522aed085e42fbf076e81d6a82bb4b` 完整回读一致。原A7FL、A7FW四槽及A7CU两槽安装时逐字节未变，view/WBI不变、/usr恢复只读。禁止重放这个包，也不得再使用旧30474345前像写入。

功能：新增独立 FL7 湿版黑白，原六个FL及已导入风格各自新增默认关的「湿版黑白（拍后）」；第三页末尾开关、第四页保存、第五页删除，同级SD导入保留。FL7固定开启，既有16项参数不改。A7CU在首次启动迁移schema3/同长度2848字节，追加一次FL7，不复活已删除内置风格；旧模块不能直接读取新schema，回退需配套备份。实际安装前独立库gen41/count9/active14/hidden_builtin63，含9套用户配方；迁移测试保留9套和删除位图，只追加FL7成为10套，所有旧开关默认0。原六套A7FL仍schema6/gen72。

本轮3文件原子替换核心故障测试、主机保护测试、原厂ARM菜单/保存/冷启动模拟、当前真实配方迁移测试通过。完整候选 `.lab/native-module-wet-candidate/proof.json`；`normal_mode_verified=false`，需用户冷启动验证。用户已收到FL7拍照、原有风格黑白开关、保存重启步骤。未提交或发布，不覆盖稳定v0.01。

安装空间不足时，仅将四个更旧语言备份 `.a7six-zh/en.orig`、`.a7sd-zh/en.orig` 完整归档校验后移出机身，证据 `.lab/wet-old-locale-archive/1795004194875080000/verified.json`。当前及最近模块备份、最近语言备份保留。安装前配置快照 `.lab/custom-look-incident/1795003175402079000` 与候选包catalog-backup目录均在。后续研究见 `docs/wet-plate-jpeg.md`。冷启动只读核对用 `research/wet_plate_acceptance.py --package .lab/native-fl-releases/update-v001-wet-plate-6pocs7rl --before .lab/custom-look-incident/1795003175402079000 --live`；当前用户操作尚待反馈，不提前运行或重写。

**首装工具三平台构建通过。** 开发分支 `codex/stock-404-installer`，实现提交 `b45ecb2`；Actions `43866534385` 的 Windows x64/macOS arm64/Linux x64 均通过 34 测试、原生构建和解压后启动、libusb/认证依赖加载、临时配方回读。没有相机 USB 枚举或实机刷写。含候选的本地包目录 `.lab/stock-tool-dist`；main 与稳定 v0.01 未改，硬件验证仍空缺。不要混淆 Windows EXE 能加载驱动库与实际 Sony USB/原厂首次安装验收。

**2026-11-16 首装实验 GUI 已接入真实后端，禁止连接当前相机。** 用户明确要求继续原厂 4.04 首装与 Windows USB，但先别动现有改装机；本轮未枚举/连接任何相机。`tool/first_install.py` 串联单一 USB 会话、逐机备份、单独确认、暂存、图标/配置/加载器激活、WBI 绑定和完整回读；`tool/usb_transport.py` 使用固定上游最小源码和 libusb，Windows 普通/服务两模式仍待实物测试。GUI 启动不枚举 USB，`--usb-runtime-check` 仅加载动态库及认证依赖，不枚举设备。

最终候选 `.lab/stock-gui-package-final/Sony_A7M3-Stock404-Experimental.zip` SHA256 `fdf9b39de2de1fa03b3b4c19907f1ee606b233b8e7399e7910d5206ac79373b6`。绑定 `.lab/stock-first-install-final-20261116/arm-stage-v2` 与 `.lab/stock-activation-v3`；后者 ARM Linux 真实映射/VFS 测试 134 项通过，但挂载及故障由 shim 提供。GUI/USB 模拟 34 测试、差分 5 测试通过。前一段“尚未接通”是历史开发状态。新代码仍没有原厂 Sony 内核实机安装/冷启动、Windows 实物 USB 或完整断电恢复验收；不能据此覆盖 v0.01 稳定附件。真实写入候选不等于只读工具，必须保留实验标记与逐文件前像限制。当前改装机因已有模块/配置会被首装工具拒绝，不为测试将其恢复原厂。

**2026-11-16 原厂 4.04 首装开发：只有现有改装机，用户没有原厂测试机。** 本轮未连接或写入相机，不把现有机恢复原厂。新增 `research/stock_first_install.py`、`research/stock_stage_build.py`、`tools/stock_install_bundle.py`，说明在 `docs/stock-first-install.md`。最终离线候选 `.lab/stock-first-install-final-20261116`：原厂至当前模块30474345及五个资源文件的差分、镜像安装/恢复、873个文件核对、独立debugfs回读和e2fsck通过。ARM文件事务核心160故障点/18980检查通过，当前模块重新构建散列不变，菜单/启动回归通过。候选不是完整实机安装器；原厂加载器/配置/图标的在线激活、WBI处理、Windows USB和原厂机冷启动仍未接通/验收。`stock-stage-only.so`只处理模块和语言，不能单独完成安装。旧试构建目录`.lab/stock-first-install-20261116`的暂存程序证明已因模块证明重建而过期，不使用。所有生成物留在.lab，当前公开v0.01未替换；不得把离线安装或可编译ARM载荷描述为实机首装已通过。

**2026-11-16 即时列表与连续切换修正已获真机验收。** 用户确认导入后立即出现、连续切换正常。只读 `.lab/custom-look-incident/1794824744407403000/live-list-acceptance.json`：模块30474345正常加载，fault0/last_error0；独立库schema2/gen14/count3，FL2、FL3、FL4独立配方已保存；hidden_builtin=14，对应原FL2/3/4已移除。原六套A7FL双槽与本次安装前逐字节一致。当前运行base4、dirty1，保存active0，因此只确认配方内容与删除位图持久化，不宣称最后选中项已保存；无需为界面验收强制用户额外操作。此轮未写入相机，只读取记录；尚未提交或覆盖v0.01，公开包仍为0eab97e版。

**2026-11-16 最新安装：导入即时列表与连续选择修正，待用户验收。** 原可删除候选 a6545d13 验收失败：用户报告导入后需重启才能看到，导入后无法选择其它。只读 `.lab/custom-look-incident/1794824196048816000` 确认运行无fault、dirty1；独立库schema2/gen12/count2/hidden6（原FL2、FL3已删除），存在导入FL2和FL3。不得把该候选作为已验收版发布。

现候选跟踪原厂模式节点副本，在列表变化时更换其独立指针数组、同步数量和选中位置；原厂克隆仅浅复制子指针，销毁旧数组时剔除借用的嵌入节点，避免清掉模板父关系，析构注销注册。取消切换时必须先保存的条件；未保存自定义参数保留在工作库，回到内置风格后保存也提交工作库；切入自定义前保留内置工作参数。真实ARM测试新增预先打开的列表副本经历导入/删除/再次导入、析构和连续未保存切换，NATIVE_LIVE_CLONE_SELECTION_PASSED；冷启动、拍摄源表、原菜单树回归通过。不是实机验收。

已执行 `.lab/native-fl-releases/update-v001-live-list-zp6tdr0i`，证据 `.lab/native-fl-releases/update-v001-live-list-zp6tdr0i/write-1794824541467165000/verified.json` 与 `catalog-preserved.json`。新模块 `30474345352eaed6b1feb8f33e389278febaeb6c3fc493dc2355ab560ca591a4`（155840字节），完整回读通过，四份原配置和两份独立库字节不变，view/WBI/语言不变、/usr只读。禁止重放。较早a820f62c副本归档于 `.lab/custom-old-backup-archive/1794824518165258000` 后移出机身腾空间，当前前像a6545d13和b3d387df备份保留。等待冷启动后先连续选择FL/已导入FL2/FL3，再从卡导入FL4.a7look检查不重启立即可见、可切换。不擅自清除用户配方或参数。尚未提交或发布。

**2026-11-16 最新安装：原 FL～FL6 可删除候选，待真机验收。** 用户要求原六套也支持删除，并清理 SD 旧测试配方、放入六份供手动导入。已安装 `.lab/native-fl-releases/update-v001-builtin-delete-det1551f`，完整写入回读 `.lab/native-fl-releases/update-v001-builtin-delete-det1551f/write-1794823873424896000/verified.json`、`catalog-preserved.json`；模块 `a6545d1306c78872b2b28acecb3640d139cd6919a5818e5aa3de4ecb4870e927`（155148 字节），原四份设置与独立库安装时逐字节未变，view/WBI/语言不变、/usr只读。未自动删除任何风格。禁止重放包。

删除原风格使用独立库的 hidden_builtin 位图移除其菜单项，保留基础配色算法及原银行参数以支持 SD 重新导入；删除当前项立即转关，重启继续过滤已删除项。稳定内部编号与可见下标分离，名称/拍摄选择不随列表缩短串位。原 A7CU schema1 兼容读取；首次删除内置项时写同长度2848字节 schema2（count低8位，hidden_builtin高位六位），旧模块不支持该格式，不直接回退而不处理配置。离线真实 ARM 菜单删除/重新导入/两处位置压缩、冷启动恢复、六套全部删除后导入配方、失败路径通过，更新核心51570项检查通过。尚未实际验收机内原 FL 删除。

SD 卡120.6GB根目录已写入 FL.a7look、FL2.a7look 至 FL6.a7look，来自安装前 generation72 六套实际参数（不是重置默认）。本地 `.lab/sd-six-look-export/export-manifest.json` 记录散列。两份旧测试 FL6-grain-1.a7look、Portrait-grain-1.a7look 和对应 AppleDouble 元数据在 `.lab/sd-recipe-cleanup/1794823525354038000` 完整备份后移除；照片不动。六份新文件已回读校验、安全推出，用户接回UTM。Mac自动生成的 `._FL*.a7look` 已由原解析器明确过滤。用户准备自行导入，不代其执行。安装前较旧2e13c731副本归档校验后移出机身以腾空间，证据 `.lab/custom-old-backup-archive/1794823847948598000`；b3d387df和a820f62c回退副本仍在。此候选未提交或更新公开v0.01。

**2026-11-16 名称修正已验收。** 用户确认下拉和选定后均显示正确名称，重启正常；删除功能此前也已验收。只读证据 `.lab/custom-look-incident/1794822522384389000/name-acceptance.json`：当前模块 b3d387dfb2dbfa3d58adbcb5bcc8a07df4bb80339c74fbf2ed38bdeb47c31fe3 正常加载、fault0/last_error0，原六套双槽与安装前逐字节一致；独立库 generation7/count1，名称「人像颗粒 1」和全部配方参数保留。保存 active0、运行dirty1；用户已明确确认测试后又切换或未保存选中状态，属于预期操作，不将其当作恢复缺陷，也不宣称当前保存的选中项是自定义。只读过程中未修改设置。初版后验脚本误拒绝合法空旧槽，已修正；其 active7 特定测试条件本轮不满足，所以最终验收按用户实际状态另行记录，未绕过或伪造该条件。未提交或发布本轮改动。

**2026-11-16 最新安装：选定值名称修正，待冷启动验收。** 用户确认上一版下拉名称正确，但选定后仍显示自定义占位名称。补接 viewUnified2 的 GEN_Label::setText 直接导入槽和 setVariantInfo 导入槽，严格核对指针前像，先执行原厂函数，仅对当前自定义资源编号恢复配方名称；下拉虚表回调和删除功能保留。离线 NATIVE_SELECTED_TEXT_DISPATCH_PASSED 覆盖选中值、格式化覆盖、切回内置项；下拉/导入/删除/保存/启动回归通过，49683项更新核心检查通过。尚未证明真机选定名称已修复。

包 `.lab/native-fl-releases/update-v001-custom-selected-hfjp6yjd` 已执行，证据 `.lab/native-fl-releases/update-v001-custom-selected-hfjp6yjd/write-1794822281280608000/verified.json`、`catalog-preserved.json`；新模块 `b3d387dfb2dbfa3d58adbcb5bcc8a07df4bb80339c74fbf2ed38bdeb47c31fe3`（153740字节），完整回读一致、四份原设置和两份独立库不变、view/WBI/语言不变、/usr恢复只读。禁止重放。为留出空间，较早备份 `.a7fl-87e8f719.orig` 已完整归档校验至 `.lab/custom-old-backup-archive/1794822262331409000` 后才移出机身；当前前像a820f62c和上一个2e13c731回退副本保留。等待用户冷启动后选人像颗粒1、收起列表、切回FL再选回、保存重启验收。只读后验工具 `research/custom_selected_acceptance.py`，要求用户已选择新项并保存。

**2026-11-16 最新安装：下拉文字设置回调修正版，待冷启动名称验收。** 上一版删除已获用户确认，且 `.lab/custom-delete-acceptance/1794821408695896000/acceptance.json` 只读核对：独立库 generation4/count0/active0，原六套 generation72 不变、运行正常；但用户仍报告下拉占位名，故不能宣称上一名称修复有效。本版对原厂 GEN_Label::setText 数据虚表槽进行精确前像核对并接入回调，先运行原厂设置，再仅对已存在自定义资源编号使用配方名称；覆盖下拉独立重设文字路径，保留原删除功能。离线 NATIVE_POPUP_TEXT_DISPATCH_PASSED、导入/删除/冷启动链路和 47796 项更新核心检查通过，尚不是实际显示验收。

已执行包 `.lab/native-fl-releases/update-v001-custom-text-0xpff8wf`，证据 `.lab/native-fl-releases/update-v001-custom-text-0xpff8wf/write-1794821851625217000/verified.json` 与 `catalog-preserved.json`。模块 `a820f62cbea336e16b945f95278ed760a1b0190ca97e6576e23113ac2991cdf9`（153424 字节），完整回读一致，四份原设置及两独立库槽保持不变，语言/view/WBI 不变、/usr只读。禁止重放包。首次预检因 /usr 仅剩117KB停止，未发送替换载荷；已将旧崩溃候选 `.a7fl-fc25a8f9.orig` 完整归档到 `.lab/custom-failed-backup-archive/1794821829570873000`，散列校验后仅移除该机内副本，当前及最近备份保留。随后正常预检与写入通过。下一步冷启动，重新导入 SD 上 Portrait-grain-1.a7look 后检查下拉名称与滚动返回；不再要求重复删除验收。

**当前磁盘为下拉名称修正及删除候选（2026-11-16），等待用户验收。** 包 `.lab/native-fl-releases/update-v001-custom-delete-n6h5xh_6` 已执行，`write-1794821118937025000/verified.json` 和 `catalog-preserved.json` 验证成功。当前模块 `2e13c731322960f5e46bd46f7112396ea5fa1ae78cff7e82d94819e5ea17c5c2`（153104字节），原六套、工作日志和独立配方库保持不变；独立库安装前备份在该包 `catalog-backup-*`。语言资源未改。禁止重放包或用87e8f719旧前像再次写入。

此前正确选新文件后用户实际反馈：新增项可见，但下拉显示「自定义外观1」，主行名称无此问题。只读 `.lab/custom-look-incident/1794820635339859000` 确认 A7CU0 格式1/gen1/count1/active0，名称「人像颗粒 1」，原配置未变；当时运行dirty1，选中新项未保存。当前候选补写原厂分类菜单内嵌 popup 的6个 GEN_Label，不遍历未知控件。第4页加入原厂「删除」行，仅自定义项可用；确认弹框显示名称，取消不改；确认删除当前新增项，回到原内置参数。不删除SD文件。其余新增项内部列表编号压紧，配方字符串ID不变。独立双槽保存、删除后重启和重新导入回归已通过。用户已收到真机名称/取消/删除/重启测试步骤，尚未收到结果。后验工具 `research/custom_delete_acceptance.py` 只读验证空库新代数、旧六套字节参数、运行状态和新模块；只有用户完成删除和冷启动后使用。

**最新诊断：用户报告“导入成功但无新增项”，尚未证明新增库保存成功。** 只读 `.lab/custom-look-debug/1794820472762381000/readback.json`：运行模块87e8f719，installed1/fault0；custom.ready1、count0、generation0、两独立槽不存在，sd_length0；真实读取缓冲是旧 `A7FL-PATCH/1\nFL6.grain=1\n`，不是新增格式。机内文件列表确有两项：`A:/FL6-grain-1.a7look`、`A:/Portrait-grain-1.a7look`，当前选中0。已请用户右键一次选第二项，确认文件名后再二次确认，仅单独“完成”算成功，然后检查新选项并接回UTM。本轮只读，未再刷写。不能把该反馈作为目录已导入或动态列表故障的证据。

**2026-11-16 当前已安装菜单重启修正候选，等待用户试用。** 上一 fc25a8f9 版用户报告导入后进入创意外观整机黑屏重启，验收失败，不得作为稳定版发布。只读 `.lab/custom-look-incident/1794819929775880000` 确认原 A7FL 两槽字节不变，A7CU 两槽均不存在；重启后内核日志未保留故障栈，不能断言崩溃唯一原因。已修正动态文字把通用子控件强转为 PAS_LabelCustom/GEN_Label 的错误，改成已核对的分类菜单行内嵌 GEN_Label，不遍历任意子控件。

修正包 `.lab/native-fl-releases/update-v001-custom-fix-76fa7b0p` 已执行；证据 `write-1794820078897767000/verified.json` 和 `catalog-preserved.json`。当前模块 `87e8f719baeeaf3e391c3607557037b4bdf28f984fa604707732a78230d90c8d`（149632字节）完整回读一致，原设置、工作记录和新库状态保持，/usr只读、view/WBI不变。只替换模块，语言仍为上一包2001/2002。禁止重复执行此包。先由用户验证打开创意外观不重启，再选 Portrait-grain-1.a7look 导入并看动态名称；尚未验收，不声称故障已在真机消失。

**2026-11-16 当前已安装独立风格导入候选，等待真机冷启动验收。** 执行包 `.lab/native-fl-releases/update-v001-custom-looks-gw1l8spw`；写入证据 `write-1794819564533584000/verified.json`。模块 `fc25a8f9f430c01f1f8c6f130ebf1d603d815c8041401712bec6ec1697c447e2`（149344字节），三文件完整回读通过，原六套配置和工作记录字节不变，view/WBI未变、/usr恢复只读。禁止重跑此包；下方 f40e4a64 已是历史前像。新库独立 A7CU0/1.CFG，测试配方卡根目录 Portrait-grain-1.a7look（人像颗粒 1），仅新增独立项，不覆盖FL6。离线完整链路与冷启动测试通过；尚未得到本候选正常模式中文名称、拍摄及断电保存验收。只读后验工具 `research/custom_look_acceptance.py`。

**2026-11-16 当前磁盘 SD 导入版已通过本轮真机菜单与断电验收。** 用户明确同意先安装候选再验证。已执行包 `.lab/native-fl-releases/update-v001-sd-import-zgow4zto`，写入证据 `write-1794816564912805000/verified.json`：三文件回读通过，四份配置字节不变，/usr 恢复只读，view/WBI 未变。禁止重跑该包或以旧 e5a530c3 前像再次写入。

- 模块 SHA-256 `f40e4a64cabd1f8d2a0c56c9bfa292bf9d780322f07814772bea0670a838dba7`，134452 字节。
- 简中 `1836c584333a0133107e15cda9d96e669d75c41fa4f13f2d71940e0e72154252`；英文 `7cb075ebf0ed4c2d9d262f5400c50b6882ca0a8952db86c582d5b8c2bbba313d`。
- 「创意外观」新增第 4 页「从 SD 卡导入」，左右选择根目录 `.a7look` 文件，选择后确认，再沿用机内保存事务。仅覆盖配方中指定字段。当前测试文件 `FL6-grain-1.a7look`，仅 FL6 grain=1。
- 安装前只读状态 generation70、mode6、dirty0、FL6 grain1，其他参数见 `.lab/auto-size-resident-read/1794816248518689000/auto-size-status.json`。这个值本来就是1，后续应同时核对保存代数是否增加，不能仅凭看到1就证明导入成功。
- 离线证据 `.lab/native-module-sd-candidate/proof.json`，包含原厂 ARM 菜单/弹框、文件读取事务模拟、六风格回归和保存启动测试。不是正常拍摄模式验收。用户已确认文件可选、导入完成、取出电池后 FL6 颗粒为 1。只读验收 `.lab/sd-import-acceptance/1794816787209226000/acceptance.json`：保存与运行代数均72（安装前70），mode6、dirty0、fault0、last_error0；运行约135秒。六套96项参数与安装前完全一致，FL6颗粒原本已经1，因此不声称本轮测试发生0→1。三文件散列与候选一致。当前验收覆盖此测试文件的机内导入和断电保留，不代表所有错误场景均已做真机测试。

下方的 v0.01 L/M/S 是上一已验收基线，已由本次候选替换磁盘文件，其历史验收证据保留。

**当前已安装并验收：v0.01 六风格 JPEG L/M/S 适配版（2026-11-15）。** 当前磁盘模块 SHA-256 `e5a530c3fe3790b829d3ee0cca7ff2628bf6a7a24f952c4f3cf46bcad8316feb`，126,480 字节。仅替换 a7fl.so；旧 5fb33e69 模块备份、完整新模块回读一致，四份配置字节不变，加载器、两种语言资源和 WBI 保持原值，/usr 已恢复只读。已执行 `.lab/native-fl-releases/update-v001-auto-size-xd7cs4kh`，证据 `write-1794742237131275000/verified.json`。禁止重复执行，也不能再按旧六风格前像重刷。

新内核 `.lab/capture-kernel/1794741362254373000`，`a7capauto` / SHA-256 `707362fc67da61b834757849fa056a2bb4c6d80a09f9469743e0a02e19f7bc0f`。同一二进制临时实拍 L/M/S 完成 3、失败 0，颗粒 9、光晕 +9、暗角 −9；自身源像素及 JPEG 对照通过。用户已确认冷启动六个 FL 和 M/S 拍摄回放正常。只读核对 resident-ready、无故障，内核 armed、diagnostic=0，当前开机累计处理完成 5 次、失败 0 次；最后源帧为 S 布局（3008×4000，stride 12000，offset 160）。保存与运行值一致：schema 6 / generation 66、FL、颗粒 3、光晕 +3、暗角 −3、dirty=0。验收证据 `.lab/auto-size-resident-read/1794742632436575000/acceptance-final.json`。回读工具 `research/auto_size_resident_read.py`：使用此包 `18` 绑定、`.lab/native-inspect-auto-size` 检查器及上述内核；只读，不重新加载。公开发布沿用同一个 GitHub v0.01 和同名 ZIP，发布包从完整回读的模块与冷启动验收记录生成。具体流程见 [尺寸适配](docs/jpeg-size-adaptation.md)。下方六风格为上一已验收基线。

**上一已验收基线：v0.01 六风格整合版（2026-11-15）。** 三个文件写入并完整回读通过；模块 `5fb33e6955b81e02144463e6fb7e09aaa042b3e4df536fd9523854a91d2fa6d5`，124,980 字节。简中 `741921ec85bd0eea18571479bdd5d0681f78a9d99bacff30305e8721792e40d6`，英文 `92843d50a15f6d94e95b51eaec0fba7a5a646366f7b954bac05f3c81b923e1f4`。两个设置槽及两个工作记录完整保留。用户保存后已迁移为 schema 6。已执行包 `.lab/native-fl-releases/update-v001-six-looks-3bxdg1m7`，证据 `write-1794736027226316000/verified.json`。禁止重复执行，也不能再按 r16 前像直接重刷。下文 r16 是上一已验收基线，不是当前磁盘内容。

用户已确认六个入口、FL4/5/6 拍照回放、独立参数保存重启正常。只读证据 `.lab/six-look-resident-read/1794736279562870000/six-look-status.json`：resident-ready、无错误、schema 6 / generation 61，最后保存 FL4，当前 FL 有未保存修改；用户确认这是测试后主动切换和修改。内核 armed、diagnostic=0、failed=0；最后重启后 completed=0，不据此声称重启后已拍摄。读取使用 `research/six_look_resident_read.py`、上述包的 `17` 绑定、`.lab/native-inspect-six-looks` 和同一内核 `.lab/capture-kernel/1794730878828623000`。公开版统一 v0.01，源码同步 main，不单独发布 r。完整附件使用 `tools/package_six_release.py`，需真实验收记录并在干净提交上打包。

用户要求日常功能改动完成后直接走单模块烧录。对已配置的 ILCE-7M3 4.04，优先在 `a7fl.so` 内实现功能，沿用已验证的加载器、菜单入口、语言资源和配置格式。

1. 用 `research/native_module.py --with-bootstrap` 构建并验证候选模块。使用本机已有的原厂固件和私有 LUT 输入。
2. 候选通过验证且相机接入 UTM 后，使用与当前已验收前像匹配的部署工具完成预检、备份、写入和回读。`deploy_fl.py` 及各版本专用工具都有基线约束，不直接对新基线套用历史命令；离线准备时省略写入参数。
3. 回读成功后冷启动并验收。以实际通过真机验收的模块作为下次更新基线；每版保留独立备份和日志。写入或回读失败时先检查相机状态与日志，再决定如何恢复。

具体命令见 [机内菜单模块](docs/native-creative-look.md#构建与验证顺序)。涉及加载器、语言资源或配置格式的改动单独验证。生成的更新包、固件、相机备份和照片保存在忽略提交的 `.lab/` 中。

历史验收基线为 **r16 正负暗角**（2026-11-15）。模块 `9fcaf13e5bcc5914d5721d797f16c3b059dc6f9b0cb99c94eda7632176306fe8`，120,468 字节；简中 `99c3292522faeb0bcd6e8ede63cc2da41baf54ff572901273007fbc2eef9d611`，英文 `4e797657592371db1eb1912e73e9c928ac7dbbe93df0d711b26ce5c86f6f47d0`。用户确认冷启动入口、三个 FL、正负暗角效果正常，+9 重启保留，随后主动改回 −9 并保存。只读核对 resident-ready、无错误、内核 diagnostic=0，处理成功 2 张、失败 0 张；generation 55 / schema 5 的 FL3 颗粒 0、光晕 0、暗角 −9 与运行状态一致，上一槽 generation 54 保留 +9。保留用户当前设置，不擅自改回默认值。验收仅覆盖全画幅 3:2 JPEG L 拍后暗角，不声称实时、RAW 或其它几何已验证。最终证据 `.lab/vignette-resident-read/1794733214834355000/acceptance-final.json`。

包 `.lab/native-fl-releases/update-r16-vignette-21etjldm/` 已执行，写入证据 `write-1794732914378618000/verified.json`；三个文件完整回读一致，安装过程用户配置未变。禁止再次执行此包或按旧 r15 前像直接重刷。后续只读使用 `research/vignette_resident_read.py`、检查器 `.lab/native-inspect-vignette-r16` 和同内核 `.lab/capture-kernel/1794730878828623000`。详见 [暗角记录](docs/vignette.md)。

上一验收基线 r15 光晕模块 `a44876fb9136b4fe31c9d82ad143bf87d9b10c3d05fc8b0ba77f0348a6c3324d`，115,120 字节，已由 r16 取代。历史证据 `.lab/film-resident-read/1794721916077782000/acceptance-final.json`，语言资源散列及三档光晕 JPEG 证据见 `docs/fl3-film-controls.md`。

本机已执行 `.lab/native-fl-releases/update-r15-halation-haw04xx1/`，写入证据 `write-1794721551114287000/verified.json`；禁止重复执行该包。下次更新必须绑定当前模块及语言资源前像，不再使用旧 r14→r15 或颗粒 r15→光晕 r15 的安装包。

旧颗粒 r15 模块 `33d103c891660cf9521a7661a31c114252070bd2c49c92f930079bc10c15c49d` 的验收保留在 `.lab/grain-resident-read/1794714565483365000/acceptance-final.json` 和 `docs/grain-research.md`，仅为历史记录。公开发布沿用 v0.01，清单以 `feature_revision=r16-vignette` 区分旧包。使用 `tools/package_release.py` 从验收回读生成公开ZIP，不上传包含设置与备份的本机私有升级归档。发布后核对 main、v0.01 标签、ZIP清单源码提交及远端附件散列一致。
