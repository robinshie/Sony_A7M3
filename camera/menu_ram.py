"""Guarded, temporary native menu experiment. Does not write firmware or settings."""
import io
import json
import os
import struct
import time

from pmca.backup import BackupFile

from local import LAB, ROOT, require, sha

EXPECTED = {
    0x01070175: b"\x03", 0x01070178: b"\x01",
    0x01070187: b"\xff", 0x0107018a: b"\xff",
    0x01070762: b"\x02", 0x0107075e: b"\x03",
    0x01070a11: b"\x01", 0x01070a17: b"\xff", 0x01070a1d: b"\xff",
}
SOURCES = ("payloads/a7-menu-ram.c", "payloads/a7-runtime-probe.c",
           "research/menu_dispatch.S", "research/menu_ram_harness.c", "research/menu_ram.py")


def payload(name):
    require(name in ("install", "inspect", "restore"), "未知内存实验动作。")
    directory = ROOT / ".lab/menu-ram"
    proof = json.loads((directory / "proof.json").read_text())
    require(proof["view_sha256"] == "f561a1e5fa0d10d55727dd4a10ced97c9613b698a40b489ff9317634485e5129",
            "测试使用的原厂库版本不符。")
    for source in SOURCES:
        require(sha((ROOT / source).read_bytes()) == proof["source_sha256"].get(source),
                f"{source} 在 QEMU 测试后发生变化。")
    data = (directory / f"{name}.so").read_bytes()
    require(data[:7] == b"\x7fELF\x01\x01\x01" and 0 < len(data) <= 16384 and
            sha(data) == proof["payloads"][name], "载荷与通过 QEMU 测试的版本不符。")
    return data


def save(path, contents):
    with path.open("xb") as stream:
        stream.write(contents)
        stream.flush()
        os.fsync(stream.fileno())


def perform(camera, factory, name):
    data = payload(name)
    directory = LAB / "menu-ram-live"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    stem = directory / f"{name}-{time.time_ns()}"
    if name == "install":
        settings = camera.getBackupPresetData(True)
        backup = BackupFile(io.BytesIO(settings))
        require(backup.revision == 4 and backup.size == len(settings), "设置备份不完整。")
        save(stem.with_suffix(".settings.bin"), settings)
        mismatch = [f"{key:08x}" for key, value in EXPECTED.items()
                    if backup.getProperty(key).data != value]
        require(not mismatch, "风格槽 3 或当前参数已变化，暂不添加入口：" + ", ".join(mismatch))
        print(f"LIVE_EXISTING_RECIPE_MATCH settings_sha256={sha(settings)}", flush=True)
    raw = factory.run(data, "a7menu.bin")
    save(stem.with_suffix(".bin"), raw)
    require(len(raw) == 48, "内存菜单报告长度异常。")
    fields = ("magic", "action", "status", "base", "allocation", "code_changed", "count",
              "calls", "last_id", "last_style", "last_box", "error")
    result = dict(zip(fields, struct.unpack("<11Ii", raw)))
    result.update(payload_sha256=sha(data), scope="temporary RAM menu route, existing slot 3")
    save(stem.with_suffix(".json"), (json.dumps(result, indent=2) + "\n").encode())
    print("LIVE_MENU_RAM_REPORT " + json.dumps(result), flush=True)
    expected_action = ("install", "inspect", "restore").index(name)
    require(result["magic"] == 0x41374d54 and result["action"] == expected_action and
            result["error"] == 0, "内存实验未通过，保留报告供定位。")
    require((result["status"], result["count"], result["code_changed"]) in
            ({(1, 20, 1), (2, 20, 1)} if name == "install" else
             {(2, 20, 1)} if name == "inspect" else {(3, 19, 0)}), "内存菜单状态异常。")
    print(f"LIVE_MENU_RAM_{name.upper()}_VERIFIED report={stem.with_suffix('.json')}", flush=True)
