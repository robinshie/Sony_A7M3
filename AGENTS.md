# A7M3 默认开发和发布流程

用户要求日常功能改动完成后直接走单模块烧录。对已配置的 ILCE-7M3 4.04，优先在 `a7fl.so` 内实现功能，沿用已验证的加载器、菜单入口、语言资源和配置格式。

1. 用 `research/native_module.py --with-bootstrap` 构建并验证候选模块。使用本机已有的原厂固件和私有 LUT 输入。
2. 候选通过验证且相机接入 UTM 后，使用与当前已验收前像匹配的部署工具完成预检、备份、写入和回读。`deploy_fl.py` 及各版本专用工具都有基线约束，不直接对新基线套用历史命令；离线准备时省略写入参数。
3. 回读成功后冷启动并验收。以实际通过真机验收的模块作为下次更新基线；每版保留独立备份和日志。写入或回读失败时先检查相机状态与日志，再决定如何恢复。

具体命令见 [机内菜单模块](docs/native-creative-look.md#构建与验证顺序)。涉及加载器、语言资源或配置格式的改动单独验证。生成的更新包、固件、相机备份和照片保存在忽略提交的 `.lab/` 中。

当前本机验收基线为 **r16 正负暗角**（2026-11-15）。模块 `9fcaf13e5bcc5914d5721d797f16c3b059dc6f9b0cb99c94eda7632176306fe8`，120,468 字节；简中 `99c3292522faeb0bcd6e8ede63cc2da41baf54ff572901273007fbc2eef9d611`，英文 `4e797657592371db1eb1912e73e9c928ac7dbbe93df0d711b26ce5c86f6f47d0`。用户确认冷启动入口、三个 FL、正负暗角效果正常，+9 重启保留，随后主动改回 −9 并保存。只读核对 resident-ready、无错误、内核 diagnostic=0，处理成功 2 张、失败 0 张；generation 55 / schema 5 的 FL3 颗粒 0、光晕 0、暗角 −9 与运行状态一致，上一槽 generation 54 保留 +9。保留用户当前设置，不擅自改回默认值。验收仅覆盖全画幅 3:2 JPEG L 拍后暗角，不声称实时、RAW 或其它几何已验证。最终证据 `.lab/vignette-resident-read/1794733214834355000/acceptance-final.json`。

包 `.lab/native-fl-releases/update-r16-vignette-21etjldm/` 已执行，写入证据 `write-1794732914378618000/verified.json`；三个文件完整回读一致，安装过程用户配置未变。禁止再次执行此包或按旧 r15 前像直接重刷。后续只读使用 `research/vignette_resident_read.py`、检查器 `.lab/native-inspect-vignette-r16` 和同内核 `.lab/capture-kernel/1794730878828623000`。详见 [暗角记录](docs/vignette.md)。

上一验收基线 r15 光晕模块 `a44876fb9136b4fe31c9d82ad143bf87d9b10c3d05fc8b0ba77f0348a6c3324d`，115,120 字节，已由 r16 取代。历史证据 `.lab/film-resident-read/1794721916077782000/acceptance-final.json`，语言资源散列及三档光晕 JPEG 证据见 `docs/fl3-film-controls.md`。

本机已执行 `.lab/native-fl-releases/update-r15-halation-haw04xx1/`，写入证据 `write-1794721551114287000/verified.json`；禁止重复执行该包。下次更新必须绑定当前模块及语言资源前像，不再使用旧 r14→r15 或颗粒 r15→光晕 r15 的安装包。

旧颗粒 r15 模块 `33d103c891660cf9521a7661a31c114252070bd2c49c92f930079bc10c15c49d` 的验收保留在 `.lab/grain-resident-read/1794714565483365000/acceptance-final.json` 和 `docs/grain-research.md`，仅为历史记录。公开发布沿用 v0.01，清单以 `feature_revision=r16-vignette` 区分旧包。使用 `tools/package_release.py` 从验收回读生成公开ZIP，不上传包含设置与备份的本机私有升级归档。发布后核对 main、v0.01 标签、ZIP清单源码提交及远端附件散列一致。
