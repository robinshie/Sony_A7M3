#!/usr/bin/env python3
"""Validate and copy Creative Look recipes to an already mounted SD card."""
import argparse
import os
from pathlib import Path
import sys

from custom_look_recipes import MAX_BYTES, parse


def prepare(card, sources):
    card = card.resolve(strict=True)
    if not card.is_dir() or not any((card / name).is_dir() for name in ("DCIM", "AVF_INFO", "PRIVATE")):
        raise ValueError("Select the camera SD card root (the folder containing DCIM, AVF_INFO or PRIVATE).")
    existing = {p.name.casefold(): p for p in card.iterdir()
                if p.suffix.lower() == ".a7look" and not p.name.startswith("._")}
    planned = {}
    ids = set()
    for source in sources:
        if source.name.startswith("._") or source.suffix.lower() != ".a7look":
            raise ValueError(f"Expected a .a7look recipe: {source}")
        with source.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        recipe = parse(data)
        key = source.name.casefold()
        if key in planned or recipe["id"] in ids:
            raise ValueError(f"Duplicate input filename or recipe ID: {source.name}")
        ids.add(recipe["id"])
        if key in existing:
            old = existing[key]
            if old.is_symlink() or not old.is_file():
                raise ValueError(f"Destination is not a regular file: {old.name}")
            with old.open("rb") as stream:
                if stream.read(MAX_BYTES + 1) != data:
                    raise ValueError(f"Existing file differs; nothing overwritten: {old.name}")
            print(f"Already present: {old.name}")
        planned[key] = (source.name, data)
    if len(existing.keys() | planned.keys()) > 32:
        raise ValueError("The SD recipe list would exceed 32 entries. Move unused recipes off the card first.")
    for key, (name, data) in planned.items():
        if key in existing:
            continue
        dest = card / name
        stream = dest.open("xb")
        try:
            with stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        except OSError:
            dest.unlink(missing_ok=True)
            raise
        if dest.read_bytes() != data:
            dest.unlink()
            raise OSError(f"Readback failed: {name}")
        print(f"Copied and verified: {name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sd", type=Path, required=True, help="Mounted SD card root, e.g. E:/")
    parser.add_argument("recipes", type=Path, nargs="+", help="Recipe files or folders (no recursion)")
    args = parser.parse_args()
    sources = []
    for path in args.recipes:
        if path.is_dir():
            sources.extend(sorted(p for p in path.iterdir() if p.is_file()
                                  and p.suffix.lower() == ".a7look" and not p.name.startswith("._")))
        else:
            sources.append(path)
    if not sources:
        parser.error("No .a7look files found.")
    try:
        prepare(args.sd, sources)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print("Safely eject the card, then use ‘从 SD 卡导入’ on the camera.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
