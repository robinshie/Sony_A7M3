#!/usr/bin/env python3
"""Loopback-only GUI; Python 3.10+, standard library only."""
import argparse
import base64
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import secrets
import sys
import threading
import webbrowser

from backend import (HOME, MAX_ZIP, INSTALL_REASON, FIELDS, LABELS, LOW, HIGH, LOOKS,
                     bundled_recipes, discover_cards, read_card, recipe_record,
                     encode, filename, copy_plan, copy_recipes, inspect_package)


class AppServer(ThreadingHTTPServer):
    def __init__(self, address):
        super().__init__(address, Handler)
        self.token = secrets.token_urlsafe(32)
        self.origin = f'http://127.0.0.1:{self.server_port}'
        self.copy_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, *args):
        pass  # Do not log tokens, recipe contents or local paths.

    def send(self, code, data, kind='application/json; charset=utf-8'):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(data)

    def permitted_host(self):
        return self.headers.get('Host') == self.server.origin.removeprefix('http://')

    def do_GET(self):
        if not self.permitted_host():
            return self.send(403, {'error': 'Host rejected'})
        assets = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8')}
        if self.path not in assets:
            return self.send(404, {'error': 'Not found'})
        name, kind = assets[self.path]
        self.send(200, (HOME / 'web' / name).read_bytes(), kind)

    def do_POST(self):
        if (not self.permitted_host() or self.headers.get('Origin') != self.server.origin or
                not secrets.compare_digest(self.headers.get('X-A7-Token', ''), self.server.token)):
            return self.send(403, {'error': '请求未授权，请通过工具启动的窗口操作。'})
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_ZIP * 4 // 3 + 4096:
                return self.send(413, {'error': '请求太大或没有内容。'})
            self.connection.settimeout(30)
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise ValueError('请求未完整接收')
            data = json.loads(raw)
            route = self.path
            if route == '/api/status':
                result = {'platform': sys.platform, 'python': sys.version.split()[0],
                          'cards': discover_cards(), 'recipes': bundled_recipes(),
                          'fields': [dict(key=k, label=l, low=a, high=b) for k,l,a,b in zip(FIELDS,LABELS,LOW,HIGH)],
                          'bases': LOOKS, 'install_enabled': False, 'install_reason': INSTALL_REASON}
            elif route == '/api/card':
                result = read_card(data['path'])
            elif route == '/api/recipe':
                result = recipe_record(data['filename'], data['text'].encode('utf-8'))
            elif route == '/api/encode':
                result = {'text': encode(data['recipe']).decode('utf-8'), 'filename': filename(data['filename'])}
            elif route == '/api/plan':
                card, plan = copy_plan(data['path'], data['records'])
                result = {'card': str(card), 'files': [{k:v for k,v in row.items() if k != 'data'} for row in plan]}
            elif route == '/api/copy':
                with self.server.copy_lock:
                    result = copy_recipes(data['path'], data['records'])
            elif route == '/api/package':
                result = inspect_package(base64.b64decode(data['base64'], validate=True), data.get('expected', ''))
            elif route == '/api/quit':
                result = {'ok': True}
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                return self.send(404, {'error': 'Not found'})
            self.send(200, result)
        except Exception as exc:
            self.send(400, {'error': str(exc) or type(exc).__name__})


def main():
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        raise SystemExit('需要 Python 3.10 或更新版本。')
    with AppServer(('127.0.0.1', args.port)) as server:
        url = server.origin + '/#' + server.token
        print('A7M3 Tool 本地窗口：' + url, flush=True)
        print('关闭工具请点界面右上角「退出工具」，或在终端按 Ctrl+C。', flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == '__main__':
    main()
