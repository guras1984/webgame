import base64
import hashlib
import io
import tempfile
import threading
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog import Catalog, Cancelled, parse_files, matches_product, prerequisite_section, microsoft_url
from downloads import download_one, FolderLock


class Response(io.BytesIO):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {'Content-Length': str(len(data))}


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.body = b'example update bytes' * 100
        digest = hashlib.sha256(self.body).hexdigest()
        self.item = dict(name='test-kb1234567-x64.msu', key=digest, digest=digest, algorithm='sha256', url='https://download.microsoft.com/test.msu')
        self.cancel = threading.Event()

    def tearDown(self):
        self.tmp.cleanup()

    def run_download(self, response):
        class Opener:
            def open(inner, request, timeout):
                inner.request = request
                return response
        opener = Opener()
        result = download_one(self.item, self.folder, self.cancel, lambda *a: None, opener)
        return result, opener

    def test_atomic_verified_download_and_skip(self):
        self.run_download(Response(self.body))
        self.assertEqual((self.folder / self.item['name']).read_bytes(), self.body)
        result, _ = self.run_download(None)
        self.assertIn('기존 파일', result)

    def test_resume(self):
        part = self.folder / '.kj-partial' / (self.item['key'] + '.part')
        part.parent.mkdir(); part.write_bytes(self.body[:25])
        _, opener = self.run_download(Response(self.body[25:], 206, {'Content-Range': f'bytes 25-{len(self.body)-1}/{len(self.body)}'}))
        self.assertEqual(opener.request.headers['Range'], 'bytes=25-')
        self.assertEqual((self.folder / self.item['name']).read_bytes(), self.body)

    def test_ignored_range_restarts_cleanly(self):
        part = self.folder / '.kj-partial' / (self.item['key'] + '.part')
        part.parent.mkdir(); part.write_bytes(b'wrong prefix')
        self.run_download(Response(self.body))
        self.assertEqual((self.folder / self.item['name']).read_bytes(), self.body)

    def test_cancellation(self):
        self.cancel.set()
        with self.assertRaises(Cancelled):
            self.run_download(Response(self.body))
        self.assertFalse((self.folder / self.item['name']).exists())

    def test_lock_rejects_concurrent_writer(self):
        with FolderLock(self.folder):
            with self.assertRaises(ValueError):
                with FolderLock(self.folder):
                    pass


class CatalogTests(unittest.TestCase):
    def test_checkpoint_and_hash(self):
        sha = base64.b64encode(bytes(32)).decode()
        source = '\n'.join(f"downloadInformation[0].files[{i}].url = 'https://download.microsoft.com/windows11.0-kb{kb}-x64.msu';\ndownloadInformation[0].files[{i}].sha256 = '{sha}';" for i,kb in enumerate(['5131080', '5043080']))
        result = parse_files(source, dict(kb='KB5131080', title='Cumulative Update 24H2', date='2026-11-10', url='https://example.test'))
        self.assertFalse(result[0]['prerequisite']); self.assertTrue(result[1]['prerequisite'])

    def test_exact_product(self):
        u = dict(title='2026-11 Update for Windows Server 2008 R2 x64', products='Windows Server 2008 R2', classification='Updates')
        self.assertFalse(matches_product(u, '2025'))
        u['title'] = '2026-11 Cumulative Update for Microsoft server operating system version 24H2 for x64-based Systems'
        self.assertTrue(matches_product(u, '2025')); self.assertFalse(matches_product(u, '2022'))

    def test_prerequisites_exclude_sidebar_and_superseded(self):
        section, kbs = prerequisite_section('<nav>KB9999999</nav><h2>Before installing this update</h2><p>Install SSU KB5005112.</p><h2>Install this update</h2><p>Replaces KB8888888</p>')
        self.assertEqual(kbs, ['KB5005112'])

    def test_url_validation(self):
        with self.assertRaises(ValueError): microsoft_url('https://microsoft.com.evil.test/a.msu')
        self.assertEqual(microsoft_url('http://download.microsoft.com/a.msu'), 'https://download.microsoft.com/a.msu')

    def test_date_boundaries(self):
        c = Catalog()
        c.query = lambda *a: [dict(id='1', title='Windows Server 2022 x64', products='', classification='Updates', date='2026-11-10')]
        self.assertEqual(len(c.search('2022','2026-11-01','2026-11-09')), 0)
        with self.assertRaises(ValueError): c.search('2022','2026-11-12','2026-11-09')


if __name__ == '__main__': unittest.main()
