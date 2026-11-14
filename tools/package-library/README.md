# A7M3 开发工具

适用于 macOS 13 或更新版本。应用内置 v0.01 的 r5、r6 和 r7 三份原始发布 ZIP，也能打开本地的 QEMU 菜单和 FL 仿真。

- **导出 ZIP**：按修订号另存为 `Sony_A7M3-v0.01-r5.zip`、`Sony_A7M3-v0.01-r6.zip` 或 `Sony_A7M3-v0.01-r7.zip`。只改文件名，内容保持原样。应用会先检查内置包的 SHA-256。
- **批量核对**：可以一次选择多份旧下载、独立模块或加载器回读；从不同文件夹添加的结果也会一起显示。按内容识别，不依赖文件名。工具不解压、不执行所选文件。
- **适用范围**：这些 ZIP 是创意外观模块的不同修订，不能叠加。r7 已验证的基线是匹配的 r6、机内加载器、菜单资源和机身色彩表。原厂 4.04 不能用这些 ZIP 初装。工具不连接相机或刷写。

## 本地开发与仿真

1. **实现功能**：相机端的改动在 `payloads/` 下编译成 ARM 模块 `a7fl.so`。菜单原型在 `ui/` 下单独编译成模拟用 ELF。两者不是同一个产物。
2. **看界面**：打开应用的「QEMU 仿真」，选择「原厂菜单模型」或「FL 创意外观模型」，点「启动 QEMU」。本机仓库的 `ui/build/` 已有模型时会自动找到；在别处打开应用时，可点「选择本地 ELF」手动指定。需要 Homebrew 安装的 `qemu-system-arm`，它在另一个窗口显示 640×480 LCD。
3. **核对发布物**：切到「发布包」，比对 ZIP、模块或已有回读，按修订号导出。QEMU 结果只能验证模拟模型，不能当作发布 ZIP 在 Sony 固件上运行的证据。

从源码生成模型需要本地已解包的 Sony 4.04 界面资源、Python Pillow 和 `arm-none-eabi-gcc`。从仓库根目录设置 `A7M3_FIRMWARE_ROOT` 指向解包目录，再运行 `python3 ui/build.py` 或 `python3 ui/build.py --fl`。更多按键和离线测试见 [QEMU 菜单实验](../../docs/ui.md)。应用 ZIP 不包含模型 ELF、Sony 资源或 QEMU。

QEMU 仿真禁用网络，不转发 USB。以前真机实验里的 UTM 承载 Linux USB 环境，与这里的菜单仿真是两回事。本工具不启动 UTM、不接管相机。

## 构建 macOS 应用

在装有 Swift 6 和 macOS SDK 的 Mac 上运行 `bash tools/package-library/build.sh`。默认从本地 `.lab/release-assets/` 取三份原始 ZIP；也可把具有相同子目录布局的目录传给构建脚本：

| 修订 | 目录内的相对路径 |
| --- | --- |
| r5 | `v0.01/Sony_A7M3-v0.01.zip` |
| r6 | `v0.01-r6/Sony_A7M3-v0.01.zip` |
| r7 | `v0.01-r7/Sony_A7M3-v0.01.zip` |

输出在 `.lab/package-library/`。构建会验证三份 ZIP，生成包含 arm64 和 x86_64 的应用及分发 ZIP；应用使用 ad hoc 签名，未做 Apple 公证。应用可执行文件支持 `--catalog` 和 `--check auto <文件路径>`，用于离线核对。
