#!/usr/bin/env python3
"""Build the stand-alone ILCE-7M3 UI verification guest."""
from io import BytesIO
import argparse
import json
import os
from pathlib import Path
import re
import shutil
from struct import unpack
import subprocess

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FW = Path(os.environ.get("A7M3_FIRMWARE_ROOT",
          str(HERE.parent / ".lab/firmware.tar_unpacked")))
APP = FW / "0700_part_image/dev/nflasha15_unpacked/share/app"

def embedded_font(path):
    data = path.read_bytes()
    start, size = (int(re.search(k + rb"=(\d+)", data[:8192]).group(1))
                   for k in (b"embeddedoffset", b"embeddedsize"))
    font = data[start:start+size]
    if len(font) != size or font[:4] != b"\0\1\0\0":
        raise ValueError(f"Invalid embedded font in {path}")
    return font

def firmware_geometry():
    xy = rb"\x08\x00\x00(..)\x08\x00\x00(..)"
    def pairs(view, key):
        blob = (APP / f"{view}.uxc").read_bytes()
        return [unpack("<hh", x + y) for x, y in re.findall(key + xy, blob, re.S)]

    pos = rb"\x1b\x57\x22\x04\x01\x0e"
    size = rb"\x1f\x02\x80\x55\x02"
    fn_pos, fn_size = pairs("viewFnMenu", pos), pairs("viewFnMenu", size)
    quick_pos, quick_size = pairs("viewQuickNavi", pos), pairs("viewQuickNavi", size)
    master_pos, master_size = pairs("LayoutMaster_Menu", pos), pairs("LayoutMaster_Menu", size)
    global_size = pairs("viewGlobalMenu", size)
    assert (640, 66) in master_size and (640, 52) in global_size and (0, 428) in master_pos
    assert fn_size.count((105, 58)) == 12
    fn_grid = [p for p in fn_pos if p[1] in (307, 369)]
    assert fn_grid == [(x, y) for y in (307, 369) for x in range(0, 536, 107)]
    quick_grid = sorted({p for p in quick_pos if p[0] in (460, 551) and p[1]%68 == 1},
                        key=lambda p: (p[1], p[0]))
    assert quick_grid == [(x, y) for y in range(1, 410, 68) for x in (460, 551)]
    assert (88, 65) in quick_size and (458, 258) in quick_size
    return ("#define MENU_HEADER_H 66\n#define SCREEN_FOOTER_Y 428\n"
            "#define FN_CELL_W 105\n#define FN_CELL_H 58\n"
            "static const uint16_t fn_positions[12][2] = {" +
            ",".join(f"{{{x},{y}}}" for x, y in fn_grid) + "};\n"
            "#define QUICK_PANEL_W 458\n#define QUICK_CELL_W 88\n#define QUICK_CELL_H 65\n"
            "static const uint16_t quick_positions[12][2] = {" +
            ",".join(f"{{{x},{y}}}" for x, y in quick_grid[:12]) + "};\n")

def native_headings(chinese_blob=None):
    # The matching IDs in the two firmware string tables are locale independent.
    def read(blob):
        return {int.from_bytes(i, "little"): v.decode("utf-8", "replace")
                for i, v in re.findall(rb"(.[\xf7\xf8]\x04)\x1e([^\0]+)\0", blob, re.S)
                if 0x4F7D8 <= int.from_bytes(i, "little") <= 0x4F806}
    english = read((APP / "string_english.uxc").read_bytes())
    chinese = read((APP / "string_simplifiedchinese.uxc").read_bytes()
                   if chinese_blob is None else chinese_blob)
    names = {line.split("|", 1)[0] for line in read_lines(HERE / "pages.txt") if "|" in line}
    out = {}
    for key, heading in english.items():
        if key not in chinese:
            continue
        for n in range(1, 15) if "${v1}" in heading else (0,):
            s = heading.replace("${v1}", str(n))
            if s in names:
                out[normalize(s)] = normalize(chinese[key].replace("${v1}", str(n)))
    return out

def playground_settings(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or set(config) != {"menu_title", "highlight"}:
        raise ValueError("playground.json 需要 menu_title 和 highlight 两项")
    title, accent = config["menu_title"], config["highlight"]
    if not isinstance(title, str) or not re.fullmatch(r"[\u4e00-\u9fff]{4}/[\u4e00-\u9fff]{4}", title):
        raise ValueError("menu_title 请写成「四个汉字/四个汉字」，保持原字符串的字节长度")
    if not isinstance(accent, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", accent):
        raise ValueError("highlight 请用 #RRGGBB 格式，比如 #275BA8")
    src = (APP / "string_simplifiedchinese.uxc").read_bytes()
    patched = bytearray(src)
    old = "影像质量/影像尺寸".encode()
    new = title.encode()
    for key, suffix in ((0x4F7E6, b""), (0x4F7E7, b"${v1}")):
        record = key.to_bytes(3, "little") + b"\x1e" + old + suffix + b"\0"
        if src.count(record) != 1 or len(old) != len(new):
            raise ValueError(f"原厂资源记录 0x{key:X} 不符合预期，未生成实验副本")
        start = src.index(record) + 4
        patched[start:start+len(old)] = new
    return bytes(patched), int(accent[1:], 16)

def native_icons():
    # Target ink bounds measured from Sony's published rear LCD menu image.
    specs = {"camera1": (0xE594, 63, 38), "camera2": (0xE595, 63, 38),
             "network": (0xE612, 44, 44), "play": (0xE804, 48, 35),
             "star": (0xE5C2, 44, 44), "still": (0xE08C, 32, 29),
             "movie": (0xE08B, 32, 29), "menu": (0xE80A, 33, 27),
             "back": (0xE803, 25, 30), "next": (0xE808, 7, 12)}
    f = ImageFont.truetype(str(APP / "Sony_DI_Icons.ttf"), 100)
    out = []
    for name, (code, w, h) in specs.items():
        mask = f.getmask(chr(code), mode="L")
        glyph = Image.frombytes("L", mask.size, bytes(mask)).crop(mask.getbbox())
        glyph = glyph.resize((w, h), Image.Resampling.LANCZOS)
        out.append(f"static const uint8_t {name}_ink[] = {{\n")
        pixels = glyph.tobytes()
        for i in range(0, len(pixels), 32):
            out.append("  " + ",".join(map(str, pixels[i:i+32])) + ",\n")
        out.append(f"}};\nstatic const Icon ico_{name} = {{{name}_ink,{w},{h}}};\n")
    return "".join(out)

def read_lines(path):
    return [line.strip() for line in path.read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")]

def normalize(value):
    return (value.replace("±", "+/-").replace("→", ">").replace("–", "-")
            .replace("―", "-").replace("’", "'"))

def cstr(value):
    return json.dumps(normalize(value), ensure_ascii=False)

def make_tables(recipe=None):
    tabs, pages, names = [], [], []
    for line in read_lines(HERE / "pages.txt"):
        if line.startswith("@"):
            tabs.append((line[1:], len(pages)))
        else:
            title, rows = line.split("|")
            labels = rows.split(";")
            assert 1 <= len(labels) <= 6
            assert len(names) + len(labels) < 256
            pages.append((title, len(names), len(labels)))
            names.extend(labels)
    assert len(tabs) == 6 and len(pages) == 38
    assert len(set(names)) == len(names)
    default = json.loads((HERE / "defaults.json").read_text())
    options = {k: v.split(";") for k, v in
               (line.split("|") for line in read_lines(HERE / "choices.txt"))}
    if recipe:
        if recipe["name"] in options["Creative Style"]:
            raise ValueError("Recipe name conflicts with an original style")
        for field, item in (("base_style", "Creative Style"), ("white_balance", "White Balance"),
                            ("picture_profile", "Picture Profile"), ("picture_effect", "Picture Effect")):
            if recipe[field] not in options[item]:
                raise ValueError(f"Unknown {field}: {recipe[field]}")
        options["Creative Style"].append(recipe["name"])
    visible = {
        "Movie Exposure Mode": "Exposure Mode",
        "S&Q Exposure Mode": "Exposure Mode",
        "Movie File Format": "File Format",
        "Movie AF Track Sens": "AF Track Sens",
        "Still Custom Key": "Custom Key",
        "Movie Custom Key": "Custom Key",
        "Playback Custom Key": "Custom Key",
    }
    groups = (
        "File Format", "RAW File Type", "JPEG Quality", "JPEG Image Size", "Aspect Ratio",
        "Drive Mode", "Focus Mode", "Focus Area", "Exposure Comp.", "ISO", "Metering Mode",
        "White Balance", "DRO/Auto HDR", "Creative Style", "Picture Effect", "Picture Profile",
        "Movie File Format", "Record Setting", "Grid Line", "Audio Recording", "Silent Shooting",
        "SteadyShot", "Touch Operation", "Airplane Mode", "USB Connection", "Version",
        "Setting Reset", "Add Item", "Sort Item", "Delete Item", "Delete Page", "Delete All",
        "Flash Mode", "Flash Comp.", "Format", "Release w/o Card", "Language",
    )
    out = []
    def write(*a):
        out.append("".join(map(str, a)))
    for label in groups:
        key = "".join(c.upper() if c.isalnum() else "_" for c in label)
        write("#define ITEM_", key, " ", names.index(label))
    write("#define RETRO_STYLE_INDEX ", len(options["Creative Style"])-1 if recipe else -1)
    if recipe:
        for key in ("name", "base_style", "white_balance", "picture_profile", "picture_effect"):
            write("#define RETRO_", key.upper(), " ", cstr(recipe[key]))
        for key in ("contrast", "saturation", "sharpness"):
            write("#define RETRO_", key.upper(), " (", recipe[key], ")")
    strings = []
    rows = []
    for item in names:
        initial = default.get(item, "")
        vals = list(options.get(item, []))
        if not vals and initial in ("On", "Off"):
            vals = ["On", "Off"]
        if vals and initial and initial not in vals:
            vals.append(initial)
        rows.append((visible.get(item, item), initial, len(strings), len(vals),
                     vals.index(initial) if initial in vals else 0))
        strings.extend(vals)
    write("static const char *const choices[] = {")
    for value in strings:
        write("    ", cstr(value), ",")
    write("};")
    write("static const Item items[] = {")
    for name, default, first, count, initial in rows:
        write("    {", cstr(name), ",", cstr(default), f",{first},{count},{initial}}},")
    write("};")
    write("static const Page pages[] = {")
    for name, first, count in pages:
        write("    {", cstr(name), f",{first},{count}}},")
    write("};")
    write("static const Tab tabs[] = {")
    for t, (name, first) in enumerate(tabs):
        end = tabs[t+1][1] if t+1 < len(tabs) else len(pages)
        write("    {", cstr(name), f",{first},{end-first}}},")
    write("};")
    return "\n".join(out) + "\n"

def make_font(size, id, codes, latin_ttf, chinese_ttf):
    latin = ImageFont.truetype(BytesIO(latin_ttf), size)
    chinese = ImageFont.truetype(BytesIO(chinese_ttf), size)
    h = size + 12
    glyphs, data = [], []
    for code in codes:
        c = chr(code)
        f = latin if code < 127 else chinese
        a = max(1, int(f.getlength(c) + 0.5))
        x0, _, x1, _ = f.getbbox(c, anchor="ls")
        w = max(a, x1) + 2
        canvas = Image.new("L", (w, h))
        ImageDraw.Draw(canvas).text((0, size), c, font=f, fill=255, anchor="ls")
        glyphs.append((len(data), code, a, w))
        data.extend(canvas.tobytes())
    out = [f"static const uint8_t {id}_pixels[] = {{"]
    for i in range(0, len(data), 32):
        out.append("  " + ",".join(map(str, data[i:i+32])) + ",")
    out.append("};")
    out.append(f"static const Glyph {id}_glyphs[] = {{")
    for offset, code, advance, width in glyphs:
        out.append(f"  {{{offset},{code},{advance},{width}}},")
    out.append("};")
    out.append(f"static const Font {id} = {{{id}_pixels,{id}_glyphs,{len(codes)},{size},{h}}};")
    return "\n".join(out)

def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--playground", action="store_true", help="build the separate playground variant")
    cli.add_argument("--retro-wardrobe", action="store_true", help="build the independent creative-style UI prototype")
    args = cli.parse_args()
    os.chdir(HERE)
    out = HERE / "build"
    chinese_blob, accent = None, 0xe64c00
    recipe = None
    if args.retro_wardrobe:
        recipe = json.loads((HERE.parent / "recipes/retro-wardrobe.json").read_text())
        for key in ("contrast", "saturation", "sharpness"):
            if type(recipe[key]) is not int or not -3 <= recipe[key] <= 3:
                cli.error(f"{key} must be an integer between -3 and 3")
        if recipe["implementation"] not in ("qemu_ui_prototype", "native_menu_slot3"):
            cli.error("Unsupported recipe representation")
        # The UI guest always remains an independent model, even when the
        # same recipe has separately been implemented in the camera firmware.
    if args.playground:
        out /= "playground"
        try:
            chinese_blob, accent = playground_settings(HERE / "playground.json")
        except (OSError, ValueError) as error:
            cli.error(str(error))
    if recipe:
        out /= "retro-wardrobe"
    out.mkdir(parents=True, exist_ok=True)
    data = make_tables(recipe)
    dictionary = {normalize(k): normalize(v) for k, v in
                  json.loads((HERE / "zh-cn.json").read_text()).items()}
    dictionary.update(native_headings(chinese_blob))
    if recipe:
        dictionary[recipe["name"]] = recipe["name_zh"]
    translated = "static const Translation zh_strings[] = {\n" + "".join(
        f"    {{{cstr(k)},{cstr(v)}}},\n" for k, v in sorted(dictionary.items())) + "};\n"
    (out / "menu_data.h").write_text(data + translated)
    (out / "firmware_ui.h").write_text(f"#define HIGHLIGHT 0x{accent:06x}\n" +
                                     firmware_geometry() + native_icons())
    chars = set(range(32, 127)) | {ord(c) for c in data+translated if ord(c)>126}
    assert max(chars) < 65536
    codes = sorted(chars)
    latin = embedded_font(APP / "UniversOTS-SJ_wIcon.ltt")
    chinese = embedded_font(FW / "0800_appli/tmp/images/MYingHeiC-GB18030-SJ_wIcon.ltt")
    sizes = [(14, "micro"), (19, "small"), (25, "body"), (28, "compact"),
             (32, "menu_text"), (36, "title"), (42, "large")]
    (out / "fonts.h").write_text("\n".join(make_font(s, name, codes, latin, chinese)
                                           for s, name in sizes))
    gcc = shutil.which("arm-none-eabi-gcc") or "/opt/homebrew/bin/arm-none-eabi-gcc"
    subprocess.run([gcc, "-mcpu=cortex-a9", "-marm", "-mno-unaligned-access", "-Os", "-g", "-Wall", "-Wextra",
                    "-ffreestanding", "-fno-builtin", "-fdata-sections", "-ffunction-sections",
                    "-nostdlib", "-T", "guest.ld", "-I", str(out),
                    "-Wl,--gc-sections", "start.S", "ui.c", "-lgcc",
                    "-o", str(out / "a7m3-ui.elf")], check=True)
    if chinese_blob is not None:
        (out / "string_simplifiedchinese.uxc").write_bytes(chinese_blob)

if __name__ == "__main__":
    main()
