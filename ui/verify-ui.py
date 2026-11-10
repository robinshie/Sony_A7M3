#!/usr/bin/env python3
"""Send real virtual keyboard events, verify navigation, capture the guest LCD."""
import argparse
import json
import socket
import time
from pathlib import Path

COUNTS = [14, 9, 3, 4, 7, 1]
TABS = ["camera1", "camera2", "network", "playback", "setup", "my-menu"]

class Guest:
    def __init__(self, stream, serial):
        self.stream, self.serial = stream, serial
        self.offset = 0
        self.pending = ""
        self._read()
        self.qmp("qmp_capabilities")
    def _read(self):
        line = self.stream.readline()
        if not line:
            raise EOFError("QEMU closed its control socket")
        return json.loads(line)
    def qmp(self, command, **arguments):
        self.stream.write(json.dumps({"execute": command, "arguments": arguments}).encode()+b"\n")
        self.stream.flush()
        while True:
            reply = self._read()
            if "error" in reply:
                raise RuntimeError(reply["error"])
            if "return" in reply:
                return reply["return"]
    def expect(self, prefix):
        end = time.monotonic()+2
        while time.monotonic() < end:
            if "\n" not in self.pending:
                with self.serial.open("rb") as f:
                    f.seek(self.offset)
                    data = f.read()
                self.pending += data.decode("ascii")
                self.offset += len(data)
            if "\n" in self.pending:
                line, self.pending = self.pending.split("\n", 1)
                if not line.startswith(prefix):
                    raise AssertionError(f"expected {prefix!r}; received {line!r}")
                return line
            time.sleep(0.003)
        raise TimeoutError(f"waiting for {prefix!r}")
    def event(self, key, down):
        self.qmp("input-send-event", events=[
            {"type": "key", "data": {"down": down, "key": {"type": "qcode", "data": key}}}])
    def press(self, key, expected):
        self.event(key, True)
        self.event(key, False)
        return self.expect(expected)
    def shot(self, directory, name):
        self.qmp("screendump", filename=str(directory/name), format="png")

def verify(guest, shots):
    assert guest.expect("menu 1/1 File Format").endswith("[zh-CN]")
    assert guest.press("l", "menu 1/1 File Format").endswith("[en]")
    guest.shot(shots, "language-english.png")
    assert guest.press("l", "menu 1/1 File Format").endswith("[zh-CN]")
    guest.shot(shots, "language-chinese.png")
    for tab, count in enumerate(COUNTS, start=1):
        state = guest.press(str(tab), f"menu {tab}/1 ")
        for page in range(1, count+1):
            if page > 1:
                state = guest.press("pgdn", f"menu {tab}/{page} ")
            guest.shot(shots, f"{tab}-{TABS[tab-1]}-{page:02}.png")
            print(state)
    guest.press("1", "menu 1/1 File Format")
    guest.press("ret", "option File Format 2")
    guest.press("up", "option File Format 1")
    guest.shot(shots, "option-file-format.png")
    guest.press("ret", "menu 1/1 File Format")
    guest.press("ret", "option File Format 1")
    guest.press("esc", "menu 1/1 File Format")
    guest.press("up", "menu 1/1 tabs")
    guest.press("right", "menu 2/9 tabs")
    guest.press("f", "menu 3/3 tabs")
    guest.press("6", "menu 6/1 Add Item")
    guest.press("ret", "menu 1/1 File Format")
    guest.press("ret", "menu 6/1 File Format")
    guest.shot(shots, "my-menu-after-add.png")
    guest.press("m", "shoot")
    guest.shot(shots, "shooting-screen.png")
    guest.press("f", "fn 1")
    guest.shot(shots, "fn-grid.png")
    guest.press("down", "fn 7")
    guest.press("ret", "option ISO 0")
    guest.press("down", "option ISO 1")
    guest.press("ret", "fn 7")
    guest.press("esc", "shoot")
    for i in range(4):
        guest.press("d", "shoot")
    guest.press("f", "quick 1")
    guest.shot(shots, "quick-navi.png")
    guest.press("down", "quick 3")
    guest.press("up", "quick 1")
    guest.press("esc", "shoot")
    guest.press("spc", "shoot")
    guest.press("r", "shoot")
    guest.shot(shots, "recording-layout.png")
    guest.press("r", "shoot")
    guest.press("p", "play 2")
    guest.shot(shots, "playback-single.png")
    guest.press("d", "play 2")
    guest.press("d", "play 2")
    guest.shot(shots, "playback-histogram.png")
    guest.press("i", "index 2")
    guest.shot(shots, "playback-index.png")
    guest.press("ret", "play 2")
    guest.press("z", "play 2")
    guest.press("delete", "play 2")
    guest.shot(shots, "playback-delete.png")
    guest.press("down", "play 2")
    guest.press("ret", "play 1")
    guest.press("p", "shoot")
    guest.press("5", "menu 5/1 ")
    for i in range(2,5):
        guest.press("pgdn", f"menu 5/{i} ")
    for i in range(5):
        state = guest.press("down", "menu 5/4 ")
    assert "Language [zh-CN]" in state
    guest.press("ret", "option Language 0")
    guest.shot(shots, "language-selector.png")
    guest.press("down", "option Language 1")
    assert guest.press("ret", "menu 5/4 Language").endswith("[en]")
    guest.press("ret", "option Language 1")
    guest.press("up", "option Language 0")
    assert guest.press("ret", "menu 5/4 Language").endswith("[zh-CN]")
    assert (shots/"language-english.png").read_bytes() != (shots/"language-chinese.png").read_bytes()
    print("PASS: 38 menu pages; tabs; selection and return; My Menu add; Fn/ISO; Quick Navi; sample capture, recording, playback, index, zoom and delete.")
    print("PASS: Simplified Chinese default; keyboard and on-screen English/Chinese switching.")

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("socket",type=Path)
    p.add_argument("serial",type=Path)
    p.add_argument("shots",type=Path)
    a=p.parse_args()
    a.shots.mkdir(parents=True, exist_ok=True)
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
        s.settimeout(4)
        s.connect(str(a.socket))
        with s.makefile("rwb") as stream:
            verify(Guest(stream,a.serial), a.shots.resolve())

if __name__ == "__main__":
    main()
