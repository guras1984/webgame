"""Microsoft Update Catalog reader. No third-party runtime dependencies."""
from __future__ import annotations

import base64
import datetime as dt
import html
from html.parser import HTMLParser
import json
import re
import ssl
import time
import urllib.parse
import urllib.request

CATALOG = 'https://www.catalog.update.microsoft.com/'
PRODUCTS = {
    '2016': ['"Windows Server 2016" "x64"'],
    '2019': ['"Windows Server 2019" "x64"'],
    '2022': ['"Microsoft server operating system" "21H2"', '"Windows Server 2022" "x64"'],
    '2025': ['"Microsoft server operating system" "24H2"', '"Windows Server 2025" "x64"'],
}


class Cancelled(Exception):
    pass


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return ' '.join(c.text() if isinstance(c, Node) else c for c in self.children)

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'wbr'}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                del self.stack[index:]
                break

    def handle_data(self, data):
        if self.stack[-1].tag not in {'script', 'style'}:
            self.stack[-1].children.append(data)

    def by_id(self, ident):
        return next((n for n in self.root.walk() if n.attrs.get('id') == ident), None)


def clean(node):
    return re.sub(r'\s+', ' ', node.text()).strip() if node else ''


def parse_search(source):
    doc = Document(source)
    summary = clean(doc.by_id('ctl00_catalogBody_searchDuration'))
    match = re.search(r'(\d+)\s*-\s*(\d+) of (\d+) \(page (\d+) of (\d+)\)', summary)
    if not match:
        if 'did not find any results' in clean(doc.root).lower():
            return [], 0
        raise ValueError('Microsoft 검색 결과 형식을 확인할 수 없습니다. 잠시 후 다시 조회해 주세요.')
    if 'over 1000 matching updates' in clean(doc.root):
        raise ValueError('Microsoft 검색 한도 1,000건을 초과했습니다. 전체 결과 확인이 필요합니다.')
    table = doc.by_id('ctl00_catalogBody_updateMatches')
    if table is None:
        raise ValueError('Microsoft 업데이트 목록이 없습니다.')
    updates = []
    for row in table.walk():
        if row.tag != 'tr' or not re.fullmatch(r'[a-f0-9-]{36}_R\d+', row.attrs.get('id', '')):
            continue
        cells = [n for n in row.children if isinstance(n, Node) and n.tag == 'td']
        if len(cells) != 8:
            raise ValueError('Microsoft 업데이트 표의 열 구성이 변경되었습니다.')
        uid = row.attrs['id'][:36]
        title = clean(cells[1])
        kb = re.search(r'KB\d{6,8}', title, re.I)
        size = doc.by_id(uid + '_originalSize')
        updates.append(dict(id=uid, title=title, products=clean(cells[2]), classification=clean(cells[3]),
                            date=dt.datetime.strptime(clean(cells[4]), '%m/%d/%Y').date().isoformat(),
                            size=int(clean(size)), kb=kb[0].upper() if kb else '',
                            url=CATALOG + 'ScopedViewInline.aspx?updateid=' + uid))
    if not updates:
        raise ValueError('검색 건수와 실제 업데이트 목록이 일치하지 않습니다.')
    return updates, int(match[5])


def matches_product(update, version):
    title = update['title'].lower()
    products = update['products'].lower()
    if any(term in title for term in ['arm64', 'x86', 'azure', 'hotpatch', 'driver']):
        return False
    if 'drivers' in update['classification'].lower():
        return False
    alias = {'2022': '21h2', '2025': '24h2'}.get(version)
    if 'windows server ' + version in title:
        return True
    if alias and 'microsoft server operating system' in title and alias in title:
        return True
    allowed = ['windows server ' + version]
    if alias:
        allowed += ['microsoft server operating system-' + alias, 'microsoft server operating system - ' + alias]
    return any(p.strip() in allowed for p in products.split(',')) and 'x64' in title


def microsoft_url(url):
    parsed = urllib.parse.urlsplit(url)
    host = (parsed.hostname or '').lower()
    if parsed.scheme not in ('https', 'http') or not (host == 'microsoft.com' or host.endswith('.microsoft.com') or host.endswith('.windowsupdate.com')):
        raise ValueError('Microsoft 공식 다운로드 주소가 아닙니다.')
    return urllib.parse.urlunsplit(('https', parsed.netloc, parsed.path, parsed.query, ''))


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(req, fp, code, msg, headers, microsoft_url(newurl))


def make_opener():
    context = ssl.create_default_context()
    try:
        import certifi
        context.load_verify_locations(certifi.where())
    except ImportError:
        pass
    return urllib.request.build_opener(SafeRedirect(), urllib.request.HTTPSHandler(context=context))


def parse_files(source, update):
    groups = {}
    pattern = r"downloadInformation\[0\]\.files\[(\d+)\]\.(\w+)\s*=\s*'((?:\\.|[^'\\])*)'"
    for index, field, value in re.findall(pattern, source):
        value = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m[1], 16)), value)
        value = value.replace('\\/', '/').replace("\\'", "'").replace('\\\\', '\\')
        groups.setdefault(int(index), {})[field] = html.unescape(value)
    if not groups:
        raise ValueError(update['kb'] + ' 다운로드 파일 정보를 확인하지 못했습니다.')
    result = []
    for index in sorted(groups):
        item = groups[index]
        url = microsoft_url(item['url'])
        name = urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit('/', 1)[-1])
        if not re.fullmatch(r'[A-Za-z0-9_.()+ -]+\.(?:msu|cab|exe|msi|zip)', name, re.I) or '..' in name:
            raise ValueError('지원하지 않는 파일 이름입니다.')
        kb = re.search(r'kb\d{6,8}', name, re.I)
        checksum = item.get('sha256') or item.get('digest')
        algorithm = 'sha256' if item.get('sha256') else 'sha1'
        if not checksum:
            raise ValueError('Microsoft 파일 검증값이 없습니다.')
        expected = base64.b64decode(checksum, validate=True).hex()
        if len(expected) != {'sha256': 64, 'sha1': 40}[algorithm]:
            raise ValueError('파일 검증값 형식이 잘못되었습니다.')
        file_kb = kb[0].upper() if kb else update['kb']
        # Only checkpoint bundles use additional KB-labelled MSUs as prerequisites.
        prerequisite = bool(file_kb and file_kb != update['kb'] and name.lower().endswith('.msu')
                            and 'cumulative update' in update['title'].lower()
                            and '24h2' in update['title'].lower())
        result.append(dict(key=expected, url=url, name=name, kb=file_kb, algorithm=algorithm,
                           digest=expected, prerequisite=prerequisite, parents=[update['kb']],
                           date='' if prerequisite else update['date'], source=update['url']))
    if not any(not f['prerequisite'] for f in result):
        raise ValueError('선택한 업데이트의 대상 파일을 식별하지 못했습니다.')
    return result


def prerequisite_section(source):
    text = clean(Document(source).root)
    start = re.search(r'Before (?:you install|installing) this update|Prerequisites', text, re.I)
    if not start:
        return '', []
    tail = text[start.end():]
    end = re.search(r'Install this update|To install this update|Release Channel|Restart requirement|Removal information', tail, re.I)
    section = tail[:end.start()] if end else tail[:2000]
    return section[:4000], list(dict.fromkeys(re.findall(r'KB\d{6,8}', section, re.I)))


class Catalog:
    def __init__(self, cancel=None, progress=None):
        self.cancel = cancel
        self.progress = progress or (lambda message: None)
        self.opener = make_opener()
        self.cache = {}

    def check(self):
        if self.cancel and self.cancel.is_set():
            raise Cancelled('작업을 중단했습니다.')

    def fetch(self, url, data=None):
        url = microsoft_url(url)
        key = (url, json.dumps(data, sort_keys=True))
        if key in self.cache:
            return self.cache[key]
        error = None
        for attempt in range(3):
            self.check()
            try:
                body = urllib.parse.urlencode(data).encode() if data else None
                req = urllib.request.Request(url, data=body, headers={'User-Agent': 'KJ-Patch-Downloader/1.0', 'Accept-Language': 'en-US,en;q=0.9'})
                with self.opener.open(req, timeout=35) as response:
                    text = response.read(12 * 1024 * 1024).decode('utf-8-sig')
                self.cache[key] = text
                return text
            except (OSError, ValueError) as exc:
                error = exc
                if self.cancel:
                    self.cancel.wait(attempt + 1)
                else:
                    time.sleep(attempt + 1)
        raise RuntimeError('Microsoft 연결 실패. 인터넷·프록시 설정을 확인해 주세요. ' + str(error))

    def query(self, query, cutoff=None, inclusive=False):
        page, pages, result, seen = 0, 1, [], set()
        while page < pages:
            self.check()
            self.progress('Microsoft 목록 조회 · ' + str(page + 1) + ' 페이지')
            url = CATALOG + 'Search.aspx?' + urllib.parse.urlencode(dict(q=query, scol='DateComputed', sdir='desc', p=page))
            rows, pages = parse_search(self.fetch(url))
            if not rows:
                break
            signature = tuple(r['id'] for r in rows)
            if signature in seen:
                raise ValueError('Microsoft 페이지 이동이 반복되었습니다. 다시 조회해 주세요.')
            seen.add(signature)
            result.extend(rows)
            # The request explicitly sorts by the Catalog's Last Updated field.
            if cutoff and max(r['date'] for r in rows) < cutoff:
                break
            page += 1
        if cutoff:
            result = [r for r in result if r['date'] > cutoff or (inclusive and r['date'] == cutoff)]
        return result

    def search(self, version, since, until, inclusive=False, dotnet=True, preview=False):
        if version not in PRODUCTS:
            raise ValueError('지원하는 서버 버전을 선택해 주세요.')
        first, last = dt.date.fromisoformat(since), dt.date.fromisoformat(until)
        if first > last:
            raise ValueError('기준일이 종료일보다 늦습니다.')
        found = {}
        for query in PRODUCTS[version]:
            for update in self.query(query, since, inclusive):
                title = update['title'].lower()
                if not matches_product(update, version) or update['date'] > until:
                    continue
                if not dotnet and '.net' in title:
                    continue
                if not preview and 'preview' in title:
                    continue
                found[update['id']] = update
        return sorted(found.values(), key=lambda r: (r['date'], r['title']), reverse=True)

    def files(self, update):
        payload = json.dumps([dict(size=0, updateID=update['id'], uid=update['id'])])
        return parse_files(self.fetch(CATALOG + 'DownloadDialog.aspx', {'updateIDs': payload}), update)

    def plan(self, updates, version):
        files, warnings, notes, visited = {}, [], [], set()
        selected = {u['kb'] for u in updates}

        def add(item, optional):
            item['prerequisite'] = optional and item['kb'] not in selected
            old = files.get(item['key'])
            if old:
                old['prerequisite'] = old['prerequisite'] and item['prerequisite']
                old['parents'] = sorted(set(old['parents'] + item['parents']))
            else:
                files[item['key']] = item

        def visit(update, optional=False, depth=0):
            self.check()
            if update['id'] in visited:
                return
            visited.add(update['id'])
            self.progress(update['kb'] + ' · 다운로드 파일 및 선행 패치 확인')
            for item in self.files(update):
                is_extra = item['prerequisite']
                if is_extra:
                    try:
                        candidates = self.query(item['kb'])
                        dates = [r['date'] for r in candidates if r['kb'] == item['kb'] and 'x64' in r['title'].lower()]
                        item['date'] = min(dates) if dates else ''
                    except (RuntimeError, ValueError) as exc:
                        warnings.append(item['kb'] + ' 날짜 확인 실패 · ' + str(exc))
                add(item, optional or is_extra)
            if not update['kb']:
                warnings.append(update['title'] + ' · KB 문서가 없어 추가 설치 조건을 확인하지 못했습니다.')
                return
            try:
                source = self.fetch('https://support.microsoft.com/help/' + update['kb'][2:])
                section, kbs = prerequisite_section(source)
                if section:
                    notes.append(dict(kb=update['kb'], text=section, url='https://support.microsoft.com/help/' + update['kb'][2:]))
                else:
                    warnings.append(update['kb'] + ' · 공식 문서의 선행 조건 구간을 자동 확인하지 못했습니다. KB 문서를 확인해 주세요.')
                for kb in kbs:
                    kb = kb.upper()
                    if kb == update['kb'] or kb in {f['kb'] for f in files.values()}:
                        continue
                    candidates = [r for r in self.query(kb) if r['kb'] == kb and matches_product(r, version)]
                    if not candidates or depth >= 5:
                        warnings.append(update['kb'] + ' · 문서에 언급된 ' + kb + '의 해당 서버 패키지를 자동 확정하지 못했습니다.')
                        continue
                    if len(candidates) > 1:
                        warnings.append(update['kb'] + ' · ' + kb + '에 여러 패키지가 있어 공식 문서에서 확인이 필요합니다.')
                        continue
                    visit(candidates[0], True, depth + 1)
            except (RuntimeError, ValueError) as exc:
                warnings.append(update['kb'] + ' · 추가 선행 조건 확인 실패 · ' + str(exc))

        for update in updates:
            visit(update)
        return dict(files=sorted(files.values(), key=lambda f: (not f['prerequisite'], f['date'], f['name'])),
                    warnings=list(dict.fromkeys(warnings)), notes=notes)
