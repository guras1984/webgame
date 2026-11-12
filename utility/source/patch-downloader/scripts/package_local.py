"""Package using supplied official Python runtimes and the local C toolchain."""
from pathlib import Path
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import tarfile
from urllib.parse import unquote
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
UPSTREAM = WORKSPACE / 'work/kj-toolbox-windows'
DIST = ROOT / 'dist'
BUILD = ROOT / 'build'
TC = WORKSPACE / 'work/kj-office-windows/toolchain/llvm-mingw-20261020-ucrt-macos-universal/bin'

def copy_app(destination):
    destination.mkdir(parents=True)
    for name in ['app.py','catalog.py','downloads.py','README.md']:
        shutil.copy2(ROOT / name, destination / name)
    for name in ['web','assets']:
        shutil.copytree(ROOT / name, destination / name)

def main():
    DIST.mkdir(exist_ok=True); BUILD.mkdir(exist_ok=True)
    win = DIST / 'KJ-Patch-Downloader-Windows'
    win.mkdir()
    meta = json.loads((UPSTREAM / 'metadata/windows-python.json').read_text())
    archive = UPSTREAM / 'downloads' / meta['url'].rsplit('/',1)[-1]
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == meta['sha256']
    with zipfile.ZipFile(archive) as z: z.extractall(win / 'Runtime')
    wheel = next((UPSTREAM / 'downloads/wheels').glob('certifi-*.whl'))
    with zipfile.ZipFile(wheel) as z: z.extractall(win / 'Runtime/Lib/site-packages')
    (win / 'Runtime/python313._pth').write_text('python313.zip\n.\n../App\nLib/site-packages\nimport site\n')
    copy_app(win / 'App'); shutil.copy2(ROOT / 'README.md', win / '사용방법.md')
    rc = BUILD / 'launcher.rc'; rc.write_text('1 ICON "' + str(ROOT/'assets/KJ-TOOL.ico') + '"\n')
    subprocess.run([str(TC/'x86_64-w64-mingw32-windres'),'-i',str(rc),'-o',str(BUILD/'launcher.o'),'-O','coff'],check=True)
    subprocess.run([str(TC/'x86_64-w64-mingw32-clang'),'-O2','-Wall','-Wextra','-Werror','-static','-municode','-mwindows',str(ROOT/'scripts/launcher.c'),str(BUILD/'launcher.o'),'-luser32','-o',str(win/'KJ Patch Downloader.exe')],check=True)
    mac = DIST / 'KJ Patch Downloader.app'
    resources = mac / 'Contents/Resources'; resources.mkdir(parents=True)
    executable = mac / 'Contents/MacOS'; executable.mkdir()
    meta = json.loads((UPSTREAM/'metadata/mac-python.json').read_text())
    archive = UPSTREAM/'downloads'/unquote(meta['url'].rsplit('/',1)[-1])
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == meta['sha256']
    with tarfile.open(archive) as t: t.extractall(BUILD/'mac-runtime')
    shutil.copytree(BUILD/'mac-runtime/python',resources/'Runtime',symlinks=True)
    site = resources/'Runtime/lib/python3.13/site-packages'
    with zipfile.ZipFile(wheel) as z: z.extractall(site)
    copy_app(resources/'App')
    shutil.copy2(ROOT/'assets/KJ-TOOL.icns',resources/'AppIcon.icns')
    (mac/'Contents/Info.plist').write_bytes(plistlib.dumps(dict(CFBundleIdentifier='local.kj.patchdownloader',CFBundleName='KJ Patch Downloader',CFBundleExecutable='KJPatchDownloader',CFBundleIconFile='AppIcon',CFBundlePackageType='APPL',CFBundleShortVersionString='1.0',CFBundleVersion='1',LSMinimumSystemVersion='13.0',NSHighResolutionCapable=True)))
    subprocess.run(['swiftc','-swift-version','5','-parse-as-library','-O','-target','arm64-apple-macosx13.0','-module-cache-path',str(BUILD/'swift-cache'),str(ROOT/'scripts/Launcher.swift'),'-o',str(executable/'KJPatchDownloader')],check=True)
    subprocess.run(['codesign','--force','--deep','--sign','-',str(mac)],check=True)
    with zipfile.ZipFile(DIST/'KJ-Patch-Downloader-Windows.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(win.rglob('*')):
            if p.is_file(): z.write(p,p.relative_to(DIST))
    subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(mac),str(DIST/'KJ-Patch-Downloader-Mac-AppleSilicon.zip')],check=True)
    with zipfile.ZipFile(DIST/'KJ-Patch-Downloader-Source.zip','w',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ROOT.rglob('*')):
            relative = p.relative_to(ROOT)
            if p.is_file() and not any(x in relative.parts for x in ['dist','build','__pycache__','.git']) and p.name != '.DS_Store': z.write(p,Path('KJ-Patch-Downloader')/relative)
    for archive in DIST.glob('*.zip'):
        with zipfile.ZipFile(archive) as z: assert z.testzip() is None
        print(archive.name,archive.stat().st_size,hashlib.sha256(archive.read_bytes()).hexdigest(),flush=True)

if __name__ == '__main__': main()
