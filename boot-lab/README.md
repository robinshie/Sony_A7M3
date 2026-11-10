# 原厂内核启动实验

这里的 QEMU 实验板实现了部分 RAM 映射、中断、定时器、串口和一个用于显示测试图的 LCD。原厂更新模式内核能启动诊断 Shell；主固件已进入 init，随后在 eMMC 初始化阶段失败。它没有完整模拟 Sony 的存储控制器、取景、显示和按键硬件。要操作菜单请使用[独立界面模型](../docs/ui.md)。

将 `a7m3-qemu.patch` 应用于 [QEMU 11.1.3](https://www.qemu.org/download/) 的源码根目录。macOS 可以另外应用 `cocoa-retina-fit.patch`，修复初次打开时 Retina 缩放没有正确匹配帧缓冲的问题。构建 `arm-softmmu`，按需启用 Cocoa、Pixman、PNG 和系统 libfdt。

```sh
git apply /path/to/Sony_A7M3/boot-lab/a7m3-qemu.patch
git apply /path/to/Sony_A7M3/boot-lab/cocoa-retina-fit.patch
./configure --target-list=arm-softmmu
ninja -C build
```

回到仓库根目录，准备 [本地解包目录](../docs/updater.md#1-准备本地资料) 后运行：

```sh
python boot-lab/run-camera.py updater --firmware "$A7M3_FIRMWARE_ROOT" \
  --qemu /path/to/qemu/build/qemu-system-arm
```

加 `--show-boot-logo` 可用本地资源显示静态启动图，需要 ImageMagick；改成 `main` 可观察主固件引导。脚本不连接宿主磁盘、网络或相机。实验运行文件默认在 `.lab/run-*`。
