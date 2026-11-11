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

FL 色彩模拟：运行 `python3 ui/play-fl.py`（可加 `--qemu /path/to/qemu-system-arm`），从与「创意风格」同级的「创意外观」进入，再选择「FL（实验版）」。Fn 也分别保留风格和外观入口。确认后模拟取景色块会经过 ARM 端 3D LUT，详情见 [FL 预览与代码位置](fl-look.md#启动可操作的-qemu-模拟)。FL 模型为容纳新增行拆分了色彩页，共 39 页；这是独立 UI 模型中的像素处理，不代表已接入 Sony ISP。

FL 自动测试（另开一个 headless 模拟实例）：

```sh
python3 ui/play-fl.py --build-only
python3 ui/run-ui.py --headless --guest ui/build/fl-demo/a7m3-ui.elf \
  --qmp /tmp/a7m3-fl-test.sock --serial .lab/fl-test-serial.log
# 另一终端：
python3 ui/verify-fl.py /tmp/a7m3-fl-test.sock .lab/fl-test-serial.log .lab/fl-ui-shots
```

八项调节页面：左右切换项目，上下修改数值，C/Delete 重置，Enter 确认，Esc 取消。确认后的设置保留到本次 QEMU 退出，调节名称与范围见 [FL 调节说明](fl-look.md#八项调节与作用)。数值测试需要另一个刚启动的 FL 实例：

```sh
python3 ui/run-ui.py --headless --guest ui/build/fl-demo/a7m3-ui.elf \
  --qmp /tmp/a7m3-adjust-test.sock --serial .lab/adjust-test-serial.log
# 另一终端：
python3 ui/verify-fl-adjust.py /tmp/a7m3-adjust-test.sock .lab/adjust-test-serial.log .lab/adjust-ui-shots
# 可选：宿主内存和算法检查（需先 build --fl）
clang -std=c11 -O1 -g -fsanitize=address,undefined -I ui/build/fl-demo \
  ui/test_fl_adjust.c -o .lab/test-fl-adjust
.lab/test-fl-adjust
```

自动测试：

```sh
mkdir -p .lab
python ui/run-ui.py --headless --qmp .lab/ui.sock --serial .lab/ui-serial.log
# 在另一终端执行；完成后终止上面的 QEMU。
python ui/verify-ui.py .lab/ui.sock .lab/ui-serial.log .lab/ui-shots
```

参考资料：[Sony 实拍菜单](https://www.sony.jp/ichigan/products/ILCE-7M3/feature_5.html)、[MENU 操作](https://helpguide.sony.net/ilc/1720/v1/zh-cn/contents/TP0001663893.html)、[菜单和默认设置](https://helpguide.sony.net/ilc/1720/v1/zh-cn/contents/TP0001668562.html)、[Fn 按键](https://helpguide.sony.net/ilc/1720/v1/zh-cn/contents/TP0001631340.html)。
