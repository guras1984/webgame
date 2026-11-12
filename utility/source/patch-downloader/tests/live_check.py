"""Opt-in live integration test against Microsoft, downloads one small package."""
import json
from pathlib import Path
import sys
import threading
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from catalog import Catalog
from downloads import download_all

target = Path(sys.argv[1])
catalog = Catalog(progress=lambda text: print(text, flush=True))
summary = {}
for version in ['2016','2019','2022','2025']:
    updates = catalog.search(version, '2026-10-01', '2026-11-12')
    assert updates, version
    assert all('2026-10-01' < r['date'] <= '2026-11-12' for r in updates)
    summary[version] = len(updates)
    print(version, len(updates), flush=True)
updates = catalog.search('2025', '2026-11-01', '2026-11-12')
cumulative = next(r for r in updates if r['kb'] == 'KB5131080')
plan = catalog.plan([cumulative], '2025')
assert any(f['kb'] == 'KB5043080' and f['prerequisite'] for f in plan['files'])
assert any(f['kb'] == 'KB5131080' and not f['prerequisite'] for f in plan['files'])
small = min(updates, key=lambda u: u['size'])
files = catalog.files(small)
result = download_all(files, target, threading.Event(), lambda *a: None, lambda *a: None)
assert all(r['success'] for r in result), result
again = download_all(files, target, threading.Event(), lambda *a: None, lambda *a: None)
assert all('기존 파일' in r['status'] for r in again)
summary.update(checkpoint=[f['kb'] for f in plan['files']], downloaded=[r['name'] for r in result], warnings=plan['warnings'])
print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
