# QEMU 菜单实验

这是独立的 ARM 界面模型，使用本地解包的 4.04 字体、部分图标及布局数据。模拟 LCD 为 **640×480**，默认简体中文，可切换英文。它覆盖六个标签、38 个分页及常见主操作入口；没有运行 Sony 原厂界面，也没有连接真机、真实取景传感器、存储卡或网络。

先按[真机手册第 1 节](updater.md#1-准备本地资料)准备工具和本地解包目录。仅运行菜单实验无需 UTM、相机备份或相机连接。

```sh
export A7M3_FIRMWARE_ROOT="$PWD/.lab/sony-4.04/firmware.tar_unpacked"
python ui/build.py
python ui/run-ui.py
```

macOS 使用 Cocoa 的 Zoom to Fit。若启动窗口仍被 Retina 裁切，参考[原厂启动实验](../boot-lab/README.md)中的 Cocoa 修复补丁，然后用 `--qemu /path/to/qemu-system-arm` 指定构建后的 QEMU。也可通过 `--display` 选用该 QEMU 支持的其他图形后端。

| 键 | 操作 |
| --- | --- |
| M / Esc | 菜单 / 返回 |
| 方向键 / Enter | 导航 / 确认 |
| 1–6 / Page Up、Page Down | 快速选择标签 / 翻页 |
| F | 菜单里切换标签；取景中打开 Fn 或 Quick Navi |
| L / D | 中英文切换 / 改变 DISP 显示 |
| Space / R | 模拟拍摄 / 开始或停止模拟录像 |
| P / I / Z / Delete | 回放 / 索引 / 放大 / 删除测试图 |

编辑 `ui/playground.json`，运行 `python ui/play.py`。标题使用「四个汉字/四个汉字」；高亮色只作用于 QEMU 里的模型。运行 `python ui/run-ui.py` 可回到普通版。

自动测试：

```sh
mkdir -p .lab
python ui/run-ui.py --headless --qmp .lab/ui.sock --serial .lab/ui-serial.log
# 在另一终端执行；完成后终止上面的 QEMU。
python ui/verify-ui.py .lab/ui.sock .lab/ui-serial.log .lab/ui-shots
```

参考资料：[Sony 实拍菜单](https://www.sony.jp/ichigan/products/ILCE-7M3/feature_5.html)、[MENU 操作](https://helpguide.sony.net/ilc/1720/v1/zh-cn/contents/TP0001663893.html)、[菜单和默认设置](https://helpguide.sony.net/ilc/1720/v1/zh-cn/contents/TP0001668562.html)、[Fn 按键](https://helpguide.sony.net/ilc/1720/v1/zh-cn/contents/TP0001631340.html)。
