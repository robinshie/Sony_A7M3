#!/usr/bin/env python3
"""Perform the guest-to-host handoff using UTM's dedicated lab serial port."""
import base64
import fcntl
import os
from pathlib import Path
import re
import secrets
import select
import subprocess
import termios
import time
import tty

from local import LAB, ROOT

VM = os.environ.get('A7M3_VM', 'A7 III USB Lab')
CLI = Path(os.environ.get('A7M3_UTMCTL', '/Applications/UTM.app/Contents/MacOS/utmctl'))
SWITCH = ('PYTHONPATH=/lab/sony-pmca /bin/busybox timeout 25 '
          '/usr/bin/python3 -u /tmp/a7m3-guest-switch.py')
DETECT = (
    'n=0; for d in /sys/bus/usb/devices/*; do '
    '[ -r "$d/idVendor" ] && [ -r "$d/idProduct" ] || continue; '
    'read -r v < "$d/idVendor"; read -r p < "$d/idProduct"; '
    '[ "$v:$p" != 054c:0c02 ] || n=$((n+1)); done; test "$n" -eq 1'
)


def control(command, *args):
    if not CLI.is_file():
        raise OSError('Local utmctl not found.')
    return subprocess.run([str(CLI), command, *args, VM], check=True, timeout=12,
                          capture_output=True, text=True).stdout


def transmit(fd, line):
    pending = memoryview(line.encode('ascii') + b'\r')
    until = time.monotonic() + 2
    while pending:
        if not select.select([], [fd], [], max(0, until - time.monotonic()))[1]:
            raise OSError('VM serial port is not accepting commands.')
        pending = pending[os.write(fd, pending):]


def exchange(fd, guest_cmd, prefix, timeout):
    nonce = secrets.token_hex(6)
    marker = (prefix + nonce).encode()
    emit = f"printf '\\n%s%s\\n' '{prefix}' '{nonce}'"
    transmit(fd, f"({guest_cmd}) && {emit} || printf '\\n%s%s\\n' 'A7_FAILED_' '{nonce}'")
    fail = b'A7_FAILED_' + nonce.encode()
    deadline = time.monotonic() + timeout
    seen = b''
    while time.monotonic() < deadline:
        if not select.select([fd], [], [], max(0, deadline - time.monotonic()))[0]:
            break
        chunk = os.read(fd, 4096)
        if not chunk:
            raise OSError('VM serial connection closed.')
        seen = (seen + chunk)[-12000:]
        if b'\n' + marker in seen or b'\r' + marker in seen:
            return
        if b'\n' + fail in seen or b'\r' + fail in seen:
            raise OSError('Guest rejected operation: ' + seen.decode('ascii', 'replace')[-1800:])
    raise OSError('No acknowledgement received from the lab VM: ' + seen.decode('ascii', 'replace')[-1800:])


def handoff(action):
    if control('status').strip() != 'started':
        raise OSError(f'Open UTM and start "{VM}" first.')
    attached = control('attach', '--index', '1')
    serial = re.search(r'^PTTY: (/dev/ttys[0-9A-Fa-f]+)$', attached, re.M)
    if not serial:
        raise OSError('UTM did not return its dedicated serial device.')
    fd = os.open(serial[1], os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    paused = False
    original = None
    try:
        original = termios.tcgetattr(fd)
        tty.setraw(fd)
        exchange(fd, ':', 'A7_BRIDGE_', 6)
        print('VM_SERIAL_BRIDGE_OK', flush=True)
        if action == 'serial-check':
            return 0
        exchange(fd, DETECT, 'A7_CAMERA_', 6)
        print('VM_SONY_MSC_PRESENT', flush=True)
        if action == 'status':
            return 0
        exchange(fd, "PYTHONPATH=/lab/sony-pmca /usr/bin/python3 -c 'import usb, pmca.usb.sony'",
                 'A7_DEPS_', 8)
        source = (ROOT / 'camera/guest_switch.py').read_bytes()
        encoded = base64.b64encode(source).decode('ascii')
        exchange(fd, ': > /tmp/a7m3-guest-switch.b64', 'A7_PREP_', 6)
        for index in range(0, len(encoded), 240):
            chunk = encoded[index:index + 240]
            exchange(fd, f"printf '%s' '{chunk}' >> /tmp/a7m3-guest-switch.b64", 'A7_DATA_', 6)
        exchange(fd, '/bin/busybox base64 -d /tmp/a7m3-guest-switch.b64 '
                 '> /tmp/a7m3-guest-switch.py && /bin/busybox rm /tmp/a7m3-guest-switch.b64',
                 'A7_SCRIPT_', 6)
        print('REQUESTING_SONY_SERVICE_MODE', flush=True)
        exchange(fd, SWITCH, 'A7_SWITCH_ACK_', 37)
        start = time.monotonic()
        control('suspend')
        paused = True
        print(f'VM_PAUSED {time.monotonic() - start:.3f}s after guest ACK', flush=True)
        time.sleep(1.8)
        control('start')
        paused = False
        print('VM_RESUMED', flush=True)
    finally:
        try:
            if original is not None:
                termios.tcsetattr(fd, termios.TCSANOW, original)
        finally:
            os.close(fd)
            if paused:
                control('start')
                print('VM_RESUMED', flush=True)

    from camera.service import connect
    connect(action)
    return 0


def run(action):
    with (LAB / '.usb-transport.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return handoff(action)
