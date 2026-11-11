# FL Inspired v0：本地算法与快速验证

2026-11-11。已实现可运行的桌面实验算法和 3D LUT 导出；原厂一维采样器也已在 QEMU 中处理过它的明暗曲线。**尚未接入真机照片处理，尚未新增 FL 菜单或烧录 FL。** 它是本项目自制的近似效果，没有 Sony FL LUT 或 A7 IV 对照实拍，不能标为原版 FL。

## 改一次配方，快速生成

在仓库根目录运行，沿用项目的 Python/Pillow 环境：

```sh
python3 research/fl_look.py build
```

修改 `recipes/fl-inspired-v0.json` 后重复命令即可，默认输出 `.lab/fl-v0/`：

| 文件 | 用途 |
| --- | --- |
| `fl-inspired.cube` | 完整 RGB 变换，默认 33³ 节点，可选 `--size 17/33/65` |
| `tone-u16le-1025.bin` | 只有标量明暗曲线，供离线原厂采样器实验；不含矩阵和色相调整，不是烧录包 |
| `recipe.json` | 本次参数快照 |
| `proof.json` | 输入输出空间、插值、源代码及产物散列，明确机内接入和烧录状态为 false |

对已经解码为 sRGB 的 JPEG/PNG 做前后对比：

```sh
python3 research/fl_look.py preview \
  --input /absolute/path/photo.jpg \
  --out .lab/fl-photo
```

有 ICC 时先转换为 sRGB；无 ICC 时拒绝猜测，确认像素已是 sRGB 后加 `--assume-srgb`。输出 `fl-preview.png`、`comparison.png`，均嵌入 sRGB ICC。保留输入文件，不复制原图 EXIF；这不是 RAW 解码器，不可直接输入 ARW、S-Log 或 HLG。预览支持 8 位 RGB 图像。

## 算法顺序和调节项

输入输出均为显示用途的 sRGB，归一化 0–1，D65。先执行 sRGB 逆传递函数，在线性 RGB 中应用曝光和 3×3 矩阵，再限制到 0–1 并重新编码 sRGB。矩阵每行和为 1，使中性灰保持中性；超出范围的颜色在这里裁切。

随后在编码后的 RGB 上做 HSV 色相与饱和度调整。三条平滑色相权重分别面向橙色、绿色、蓝色区域；它们只是颜色范围选择，不识别人脸、衣物或天空。初版整体降低饱和度，绿色向青色微调，橙色区域减弱去饱和的程度。最后按每个 RGB 通道应用单调分段线性曲线：轻抬黑位、增强中间调对比、收住最亮端。

`strength` 在编码后的 sRGB 中混合原始和处理结果；为 0 时参考算法逐值恒等。配置中的 `exposure_ev`、`linear_matrix`、`saturation`、`hue_bands`、`tone_curve` 是独立参数。没有调用机身的对比度、饱和度、锐度三个设置，也没有加入空间颗粒、光晕或锐化。

完整变换采样成 RGB 3D LUT；导出顺序为红最快、绿其次、蓝最慢，符合 [Adobe Cube 1.0 规格（镜像）](https://kono.phpage.fr/images/a/a1/Adobe-cube-lut-specification-1.0.pdf)。图片预览使用 [Pillow Color3DLUT](https://pillow.readthedocs.io/en/stable/reference/ImageFilter.html#PIL.ImageFilter.Color3DLUT) 的三线性插值，测试另有独立三线性参考计算。

## 本轮验证

```sh
python3 -m unittest discover -s research -p test_fl_look.py -v
python3 research/gamma_avcam.py --avcam \
  "$A7M3_FIRMWARE_ROOT/0700_part_image/dev/nflasha3_unpacked/av-cam.bin"
```

8 项桌面测试通过：sRGB 传递函数往返、灰阶单调与中性、强度零时恒等、错误参数拒绝、Cube 通道顺序、端点、插值、可重复构建、原厂格式表长度与单调性，以及图像 ICC / 输出尺寸。33³ LUT 相对浮点直接计算，在固定种子的 6000 个 RGB 输入上，归一化通道最大误差为 `0.01751823`，RMS 为 `0.00108709`；这是采样集误差，不是全色域上界。Pillow 与独立三线性计算差异不超过 1 个 8 位码值。

AV-CAM 测试运行原厂接收、采样、插值和除法机器码，包含本配方的 1025 节点明暗表。2560 组接收检查和 1,049,088 次采样比较通过。其证明范围见 [机内接口研究](color-interface.md)：只确认原厂函数能处理这份标量表，**没有把整个 3D LUT 交给相机，也没有证明最终 JPEG 被改变**。

当前仅用合成灰阶、色相渐变及色块验证生成和预览流程，还没有实拍效果验收。下一步机内工作是查明扩展 Gamma 指针的消费者、内存约定和照片路径，并寻找颜色矩阵或多维颜色表入口；单独一条 Gamma 曲线无法承载本算法的全部 RGB 色彩变化。
