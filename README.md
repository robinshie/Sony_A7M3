# Sony A7 III 4.04 菜单实验

针对 Sony α7 III（**ILCE-7M3**）4.04 的中文菜单修改、QEMU 验证和本地 USB 更新工具。示例将「影像质量/影像尺寸」改为「我的相机/固件实验」。这个改动已在一台实机上完成烧录、断电重启、菜单目视确认和 USB 回读。

| 要做什么 | 从这里开始 |
| --- | --- |
| 在 QEMU 看菜单、调显示和试改标题 | [QEMU 菜单实验](docs/ui.md) |
| 查看「复古衣橱」原型和原厂组件测试（尚未烧录） | [创意风格实验](docs/creative-style.md) |
| 在本地构建镜像、备份、烧录、回读或恢复 | [真机操作手册](docs/updater.md) |
| 查看测试覆盖范围和官方更新器限制 | [验证记录](docs/validation.md) |
| 研究原厂内核启动和启动图 | [原厂启动实验](boot-lab/README.md) |

本地工具从该相机的原始备份构建 300 MiB 的完整 `/usr` 分区镜像。示例镜像有 **44 字节**不同，真机只写入包含它们的一个 **512 字节扇区**。这不是整机闪存镜像，也不生成 Sony 官方签名的 DAT。镜像构建和 QEMU 菜单实验都可以在不连接相机的情况下完成。

仓库只包含源码、文档和补丁。请从 [Sony 官网](https://www.sony.com/electronics/support/e-mount-body-ilce-7-series/ilce-7m3/downloads) 获取原始 4.04，所需的固件、字体和图标均从本地副本读取。请把相机设置备份、分区镜像、虚拟机、编译产物和日志放在忽略目录 `.lab/`，不要提交到 GitHub。

项目源码采用 [MIT 许可证](LICENSE)。对 QEMU 的 [机器补丁](boot-lab/a7m3-qemu.patch) 和 [Cocoa 补丁](boot-lab/cocoa-retina-fit.patch) 分别遵循其上游文件的 [GPL-2.0-or-later](licenses/GPL-2.0.txt) 和 [MIT 条款](licenses/QEMU-Cocoa.txt)。
