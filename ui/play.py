#!/usr/bin/env python3
"""Build and open the separate A7 III modification playground."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--build-only", action="store_true", help="build without opening QEMU")
args = parser.parse_args()
subprocess.run([sys.executable, str(root / "build.py"), "--playground"], check=True)
if not args.build_only:
    os.execv(sys.executable, [sys.executable, str(root / "run-ui.py"),
                             "--guest", str(root / "build/playground/a7m3-ui.elf")])
