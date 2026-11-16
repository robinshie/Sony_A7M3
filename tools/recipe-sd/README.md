# Sony A7M3 SD 配方工具包

适用于已有「从 SD 卡导入」菜单的相机。需要 Python 3.10+，无需安装额外库。本工具只将配方复制到 SD 卡，不安装固件。

解压 ZIP，进入解压目录。用读卡器或相机的 USB 大容量存储模式连接 SD 卡，确认盘符或挂载路径。

**Windows（PowerShell 或命令提示符）：**

```powershell
py -3 prepare_recipe_sd.py --sd E:/ recipes
```

把 `E:/` 换成 SD 卡盘符。如果系统没有 `py`，试用 `python`。

**Mac（终端）：**

```sh
python3 prepare_recipe_sd.py --sd "/Volumes/Untitled" recipes
```

将路径改为自己的 SD 卡挂载路径。也可以把命令末尾的 `recipes` 换成一个或多个 `.a7look` 文件。工具会检查格式，拒绝覆盖同名不同内容的文件，并回读核对新文件。

复制成功后安全弹出 SD 卡，在相机选「从 SD 卡导入」并确认，然后进入「创意外观」选择配方并保存。包内有六套胶片风格示例。
