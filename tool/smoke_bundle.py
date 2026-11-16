"""Start a freshly unpacked native bundle and exercise its HTTP/SD workflow."""
import hashlib
import json
from pathlib import Path
import queue
import re
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile


def verify(archive_path):
    with tempfile.TemporaryDirectory(prefix='a7-tool-smoke-') as temp:
        root = Path(temp).resolve()
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                target = (root/info.filename).resolve()
                if not target.is_relative_to(root):
                    raise ValueError('Archive path escaped test directory')
                archive.extract(info,root)
                if not info.is_dir() and sys.platform != 'win32':
                    target.chmod((info.external_attr >> 16) & 0o777 or 0o644)
        app = root/'A7M3-Tool'
        for line in (app/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
            checksum, name = line.split('  ',1)
            if hashlib.sha256((app/name).read_bytes()).hexdigest() != checksum:
                raise ValueError('Bundle checksum mismatch: '+name)
        executable = app/('A7M3-Tool.exe' if sys.platform == 'win32' else 'A7M3-Tool')
        runtime = subprocess.run([str(executable),'--usb-runtime-check'],cwd=root,
                                 capture_output=True,check=True,timeout=30)
        runtime_status = json.loads(runtime.stdout)
        assert runtime_status == dict(libusb_loaded=True,crypto_loaded=True,
                                      protocol_imported=True,devices_enumerated=False)
        process = subprocess.Popen([str(executable),'--no-browser'], cwd=root,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        lines = queue.Queue()
        threading.Thread(target=lambda: [lines.put(line) for line in iter(process.stdout.readline,b'')],daemon=True).start()
        try:
            # Match the ASCII URL even when a Windows console uses a legacy code page.
            address = None
            for _ in range(30):
                line = lines.get(timeout=30)
                match = re.search(rb'(http://127\.0\.0\.1:\d+)/#([A-Za-z0-9_-]+)',line)
                if match:
                    address,token = [v.decode('ascii') for v in match.groups()]
                    break
            if address is None:
                raise RuntimeError('Native process did not start')
            def post(route, data):
                req = urllib.request.Request(address+'/api/'+route,
                    data=json.dumps(data).encode('utf-8'),method='POST',
                    headers={'Origin':address,'X-A7-Token':token,'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=20) as response:
                    return json.load(response)
            status = post('status',{})
            assert len(status['recipes']) == 12 and status['install_enabled'] is False
            assert all(status['usb_dependencies'].values()),status['usb_dependencies']
            assert post('first-install/status',{})['phase']=='idle'
            card = root/'test-card'; card.mkdir(); (card/'DCIM').mkdir()
            result = post('copy',{'path':str(card),'records':[status['recipes'][0]]})
            assert result['ok'] is True and len(result['files']) == 1
            assert post('card',{'path':str(card)})['files'][0]['recipe'] == status['recipes'][0]['recipe']
            post('quit',{})
            process.wait(timeout=10)
            assert process.returncode == 0
            print(json.dumps({'archive':str(archive_path),'platform':sys.platform,
                              'native_start':True,'recipe_count':12,'copy_readback':True,'shutdown':True}))
        finally:
            if process.poll() is None:
                process.kill(); process.wait()
            process.stdout.close()


if __name__ == '__main__':
    source = Path(sys.argv[1])
    archives = sorted(source.glob('Sony_A7M3-Tool-*-*.zip')) if source.is_dir() else [source]
    if not archives:
        raise SystemExit('No native bundles found')
    for archive in archives:
        verify(archive)
