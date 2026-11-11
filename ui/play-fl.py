#!/usr/bin/env python3
"""Build and launch the FL RGB experiment in the independent ARM UI model."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build-only', action='store_true')
parser.add_argument('--qemu', help='QEMU binary; otherwise uses A7M3_QEMU or PATH')
args = parser.parse_args()
subprocess.run([sys.executable, str(root/'build.py'), '--fl'], check=True)
if not args.build_only:
    command = [sys.executable, str(root/'run-ui.py'), '--guest',
               str(root/'build/fl-demo/a7m3-ui.elf'), '--name', 'Sony A7 III - FL 实验模拟']
    if args.qemu:
        command.extend(['--qemu', args.qemu])
    os.execv(sys.executable, command)
