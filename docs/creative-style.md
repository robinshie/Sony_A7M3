# 「复古衣橱」创意风格实验

**状态：QEMU 界面原型已验证，原厂固件功能尚未实现，未烧录此功能。** 已完成的真机菜单标题补丁是另一项修改，不能证明新增创意风格或 JPEG 成像链路已经接通。`a7m3.py flash` 仍只写标题补丁。

目标是在「创意风格」中新增「复古衣橱」，保留原有选项，并在机身中实际应用、保存以下设置。配方在 [`recipes/retro-wardrobe.json`](../recipes/retro-wardrobe.json)。这是基于 Sony 现有调节项的实验配方，尚无实拍对比，不声称复现某款富士胶片模拟。

| 参数 | 值 |
| --- | --- |
| 基础风格 | 中性 Neutral |
| 对比度 | +1 |
| 饱和度 | −1 |
| 锐度 | −1 |
| 白平衡 | 日光 |
| 图片配置文件 / 照片效果 | 关 / 关 |

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

静态分析还定位到 `CautionConfig.so` 中的 `CmnViewSettingNodeCreativeStyle::_getSubNode()`（`0x0069335c`）。它读取设置 ID `0x01070316`，再选择不同的节点数组。已有机身备份中此值为 `0x3e`，按静态分支对应 `cmnViewSettingNodesCreativeStyleTypeEmnt`，含 91 个节点引用。该结论来自既有备份与二进制分析，本轮没有重新读取或改写机身设置。

报告包含 99 份导出的 CreativeStyle 属性表及各节点数组的重定位名称。属性表中的数字键、UI 编号、底层风格值和设置备份 ID 不能互相混用。库里出现 `CreativeStyleReal` 名称，也不能据此认定有可直接启用的隐藏风格。

## 真机烧录尚缺的实现

1. 在该机型实际使用的节点数组中添加入口、字符串与属性，并验证列表长度、索引和返回导航。
2. 追踪选择入口到机身设置服务的完整调用，确认中性风格、对比度、饱和度、锐度的类型、范围和提交顺序。
3. 实现选择、取消、旧风格切换及参数保存；验证开关机后恢复，避免覆盖其他设置与校准数据。
4. 对最终文件和分区差异构建补丁及恢复载荷，验证当前含标题补丁的前置镜像，再验证写入/恢复路径。
5. 真机临时加载验证生效后，才烧录并回读；断电重启、菜单检查和同场景 JPEG 实拍对比均需完成。

当前没有生成可烧录的创意风格镜像，也没有把 UI 原型当作真机固件上传。`native_integration_verified: false` 明确记录这一状态。
