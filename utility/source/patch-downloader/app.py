"""Local desktop application with a browser interface, Windows/macOS/Linux."""
import argparse
import copy
import datetime as dt
import json
import mimetypes
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from catalog import Catalog, Cancelled
from downloads import download_all

ROOT = Path(__file__).resolve().parent


class Application:
    def __init__(self):
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.token = secrets.token_urlsafe(32)
        self.catalog = Catalog(self.cancel, lambda text: self.set(message=text))
        self.state = dict(busy=False, operation='', message='서버와 기준일을 선택해 주세요.', error='',
                          updates=[], plan=None, results=[], received=0, total=0, index=0, count=0,
                          version='2022', folder=str(Path.home() / 'Downloads' / 'KJ-Patches'),
                          today=dt.date.today().isoformat())

    def set(self, **values):
        with self.lock:
            self.state.update(values)

    def start(self, operation, data):
        with self.lock:
            if self.state['busy']:
                raise ValueError('진행 중인 작업을 완료하거나 중단해 주세요.')
            self.cancel.clear()
            self.state.update(busy=True, operation=operation, error='', received=0, total=0)
        def run():
            try:
                if operation == 'search':
                    self.set(updates=[], plan=None, results=[])
                    updates = self.catalog.search(data['version'], data['since'], data['until'],
                                                  data.get('inclusive', False), data.get('dotnet', True), data.get('preview', False))
                    self.set(updates=updates, version=data['version'], message=str(len(updates)) + '건 조회 완료')
                elif operation == 'plan':
                    ids = set(data['ids'])
                    updates = [u for u in self.state['updates'] if u['id'] in ids]
                    if not updates or len(updates) != len(ids):
                        raise ValueError('조회된 업데이트를 선택해 주세요.')
                    self.set(plan=None, results=[])
                    plan = self.catalog.plan(updates, self.state['version'])
                    self.set(plan=plan, message='다운로드 파일을 확인하고 선행 패치 포함 여부를 선택해 주세요.')
                elif operation == 'download':
                    plan = self.state['plan']
                    if not plan:
                        raise ValueError('먼저 파일 목록을 확인해 주세요.')
                    keys = set(data['keys'])
                    items = [f for f in plan['files'] if f['key'] in keys]
                    if not items or len(items) != len(keys):
                        raise ValueError('다운로드할 파일을 선택해 주세요.')
                    folder = str(Path(data['folder']).expanduser().resolve())
                    self.set(folder=folder, results=[], count=len(items), index=0)
                    def progress(message, received, total, index, count):
                        self.set(message=message, received=received, total=total, index=index, count=count)
                    results = download_all(items, folder, self.cancel, progress, lambda results: self.set(results=copy.deepcopy(results)))
                    success = sum(r['success'] for r in results)
                    self.set(message='검증 완료 ' + str(success) + '/' + str(len(items)) + '개' + (' · 중단됨' if self.cancel.is_set() else ''), index=len(results))
            except Cancelled:
                self.set(message='작업을 중단했습니다.')
            except Exception as exc:
                self.set(error=str(exc), message='작업을 완료하지 못했습니다.')
            finally:
                self.set(busy=False)
        threading.Thread(target=run, daemon=True).start()


def choose_folder():
    if sys.platform == 'darwin':
        args = ['osascript', '-e', 'POSIX path of (choose folder with prompt "패치 저장 폴더 선택")']
    elif os.name == 'nt':
        command = ('Add-Type -AssemblyName System.Windows.Forms; '
                   '$d = New-Object System.Windows.Forms.FolderBrowserDialog; '
                   '$d.Description = "KJ Patch download folder"; '
                   'if ($d.ShowDialog() -eq "OK") { [Console]::OutputEncoding = [Text.Encoding]::UTF8; $d.SelectedPath }')
        args = ['powershell.exe', '-NoProfile', '-STA', '-Command', command]
    else:
        args = ['zenity', '--file-selection', '--directory']
    result = subprocess.run(args, capture_output=True, timeout=180)
    return result.stdout.decode('utf-8-sig').strip() if result.returncode == 0 else ''


def handler(app):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def send(self, value, status=200, content_type='application/json; charset=utf-8'):
            body = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; frame-ancestors 'none'")
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def authorized(self):
            host = '127.0.0.1:' + str(self.server.server_port)
            if self.headers.get('Host') != host:
                return False
            origin = self.headers.get('Origin')
            return (not origin or origin == 'http://' + host) and secrets.compare_digest(self.headers.get('X-KJ-Token', ''), app.token)

        def do_GET(self):
            route = urllib.parse.urlsplit(self.path).path
            if route == '/api/state':
                if not self.authorized():
                    return self.send({'error': '앱 실행 창에서 접속해 주세요.'}, 403)
                with app.lock:
                    return self.send(app.state)
            paths = {'/': ROOT / 'web/index.html', '/style.css': ROOT / 'web/style.css',
                     '/app.js': ROOT / 'web/app.js', '/icon.png': ROOT / 'assets/KJ-TOOL.png'}
            if route not in paths or self.headers.get('Host') != '127.0.0.1:' + str(self.server.server_port):
                return self.send({'error': 'Not found'}, 404)
            path = paths[route]
            self.send(path.read_bytes(), content_type=mimetypes.guess_type(str(path))[0] or 'application/octet-stream')

        def do_POST(self):
            if not self.authorized():
                return self.send({'error': '앱 실행 창에서 접속해 주세요.'}, 403)
            try:
                length = int(self.headers.get('Content-Length', 0))
                if length > 1024 * 1024:
                    raise ValueError('요청이 너무 큽니다.')
                data = json.loads(self.rfile.read(length) or '{}')
                route = self.path
                if route in ['/api/search', '/api/plan', '/api/download']:
                    app.start(route.rsplit('/', 1)[-1], data)
                elif route == '/api/cancel':
                    app.cancel.set()
                elif route == '/api/folder':
                    return self.send({'folder': choose_folder()})
                elif route == '/api/open-folder':
                    folder = Path(app.state['folder'])
                    if not folder.is_dir():
                        raise ValueError('다운로드 후 저장 폴더를 열 수 있습니다.')
                    if os.name == 'nt':
                        os.startfile(str(folder))
                    else:
                        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(folder)])
                elif route == '/api/quit':
                    if app.state['busy']:
                        raise ValueError('진행 중인 작업을 먼저 중단해 주세요.')
                    threading.Thread(target=self.server.shutdown, daemon=True).start()
                else:
                    return self.send({'error': 'Not found'}, 404)
                self.send({'ok': True})
            except Exception as exc:
                self.send({'error': str(exc)}, 400)
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=0)
    args = parser.parse_args()
    app = Application()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler(app))
    url = 'http://127.0.0.1:' + str(server.server_port) + '/#' + app.token
    print('KJ Patch Downloader\n' + url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        app.cancel.set()
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
