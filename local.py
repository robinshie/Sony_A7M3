"""Shared local paths and immutable identifiers for the verified 4.04 layout."""
import hashlib
import os
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parent
LAB = Path(os.environ.get("A7M3_LAB", ROOT / ".lab")).expanduser().resolve()
BACKUP = LAB / "a7m3-live-usr-nflasha15.bin"
SETTINGS = LAB / "a7m3-settings-backup.bin"
IMAGE = LAB / "a7m3-4.04-usr-custom.img"
TOTAL = 300 * 1024 * 1024
PREFIX = 217267200
STOCK_SHA = "f92837a9fd3819628b8eeb27c1be1af9bc9f338ca9e2053c0c4e45a2aedb322c"
STOCK_MENU_SHA = "61ce4af838a991ad02d89726c0bee3f0aa443ac4421b1d9edff07fe55c0dd249"
BUILD_ID = b"37114_13.2026020901"
MENU_PATH = "/usr/share/app/string_simplifiedchinese.uxc"
OFFSET = 0x8e4f * 512


def require(test, message):
    if not test:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path, limit=None):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        while limit is None or limit > 0:
            block = stream.read(4 * 1024 * 1024 if limit is None else min(limit, 4 * 1024 * 1024))
            if not block:
                break
            h.update(block)
            if limit is not None:
                limit -= len(block)
    return h.hexdigest()


def atomic(path, data):
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)
