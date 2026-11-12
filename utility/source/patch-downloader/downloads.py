"""Resumable transfers with Microsoft digest verification and atomic completion."""
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request

from catalog import Cancelled, make_opener, microsoft_url


def digest_file(path, algorithm, cancel):
    digest = hashlib.new(algorithm)
    with path.open('rb') as stream:
        while True:
            if cancel.is_set():
                raise Cancelled('작업을 중단했습니다.')
            chunk = stream.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class FolderLock:
    def __init__(self, directory):
        self.path = directory / '.kj-download.lock'

    def __enter__(self):
        self.stream = self.path.open('a+b')
        self.stream.seek(0)
        self.stream.write(b'0')
        self.stream.flush()
        self.stream.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.stream.close()
            raise ValueError('다른 KJ 다운로드 작업이 이 폴더를 사용하고 있습니다.')
        return self

    def __exit__(self, *args):
        self.stream.close()


def download_one(item, folder, cancel, progress, opener=None):
    opener = opener or make_opener()
    target = folder / item['name']
    if target.is_symlink():
        raise ValueError('저장 위치에 심볼릭 링크가 있습니다. 다른 폴더를 선택해 주세요.')
    if target.is_file():
        progress('기존 파일 검증 · ' + target.name, 0, 0)
        if digest_file(target, item['algorithm'], cancel) == item['digest']:
            return '기존 파일 검증 완료'
    partial_dir = folder / '.kj-partial'
    partial_dir.mkdir(exist_ok=True)
    if partial_dir.is_symlink():
        raise ValueError('임시 저장 폴더가 심볼릭 링크입니다.')
    partial = partial_dir / (item['key'] + '.part')
    if partial.is_symlink():
        raise ValueError('임시 파일이 심볼릭 링크입니다.')
    error = None
    for attempt in range(3):
        if cancel.is_set():
            raise Cancelled('작업을 중단했습니다.')
        offset = partial.stat().st_size if partial.exists() else 0
        headers = {'User-Agent': 'KJ-Patch-Downloader/1.0', 'Accept-Encoding': 'identity'}
        if offset:
            headers['Range'] = 'bytes=' + str(offset) + '-'
        try:
            request = urllib.request.Request(microsoft_url(item['url']), headers=headers)
            with opener.open(request, timeout=35) as response:
                status = response.status
                if status == 206:
                    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', response.headers.get('Content-Range', ''))
                    if not match or int(match[1]) != offset:
                        raise ValueError('다운로드 이어받기 범위가 일치하지 않습니다.')
                    total = int(match[3])
                    mode = 'ab'
                elif status == 200:
                    offset = 0
                    total = int(response.headers.get('Content-Length', 0))
                    mode = 'wb'
                else:
                    raise ValueError('예상하지 못한 다운로드 응답입니다.')
                received = offset
                with partial.open(mode) as stream:
                    last_report = 0
                    while True:
                        if cancel.is_set():
                            raise Cancelled('작업을 중단했습니다.')
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        stream.write(chunk)
                        received += len(chunk)
                        if time.monotonic() - last_report > 0.2:
                            progress(item['name'], received, total)
                            last_report = time.monotonic()
                    stream.flush()
                    os.fsync(stream.fileno())
                if total and received != total:
                    raise OSError('파일 수신이 완료되지 않았습니다.')
            progress('파일 무결성 검증 · ' + item['name'], received, received)
            if digest_file(partial, item['algorithm'], cancel) != item['digest']:
                partial.unlink()
                raise ValueError('Microsoft 검증값과 일치하지 않아 다시 받습니다.')
            os.replace(partial, target)
            return '다운로드·검증 완료'
        except urllib.error.HTTPError as exc:
            error = exc
            if exc.code == 416 and partial.exists():
                if digest_file(partial, item['algorithm'], cancel) == item['digest']:
                    os.replace(partial, target)
                    return '이어받기·검증 완료'
                partial.unlink()
        except (OSError, ValueError) as exc:
            error = exc
        progress('재시도 ' + str(attempt + 1) + '/3 · ' + item['name'], 0, 0)
        if cancel.wait(attempt + 1):
            raise Cancelled('작업을 중단했습니다.')
    raise RuntimeError(str(error))


def download_all(items, folder, cancel, progress, report):
    folder = Path(folder).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    results = []
    with FolderLock(folder):
        for index, item in enumerate(items):
            if cancel.is_set():
                break
            def notify(message, received, total):
                progress(message, received, total, index, len(items))
            try:
                status = download_one(item, folder, cancel, notify)
                result = dict(item, status=status, success=True)
            except Cancelled:
                results.append(dict(item, status='중단됨 · 다음 다운로드에서 이어받기', success=False))
                report(results)
                break
            except Exception as exc:
                result = dict(item, status='실패 · ' + str(exc), success=False)
            results.append(result)
            report(results)
        stamp = time.strftime('%Y%m%d-%H%M%S')
        path = folder / ('KJ-download-' + stamp + '.json')
        path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        with (folder / ('KJ-download-' + stamp + '.csv')).open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['KB', '파일명', '선행/권장', '게시·갱신일', '결과', '해시 방식', '해시', '원본 URL'])
            for r in results:
                writer.writerow([r['kb'], r['name'], r['prerequisite'], r['date'], r['status'], r['algorithm'], r['digest'], r['url']])
    return results
