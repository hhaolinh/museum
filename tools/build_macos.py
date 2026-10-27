#!/usr/bin/env python3
"""Build a self-contained Apple Silicon Cabinet.app; never package personal data."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SPARKLE_VERSION = '2.10.1'
SPARKLE_SHA256 = '1a856d2a9edb8e628de88121d7be04cf0e2167f8641650b78fca00b14244cf27'


def run(*args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, cwd=ROOT, **kwargs)


def sparkle():
    cache = ROOT / 'desktop/.cache'
    target = cache / f'sparkle-{SPARKLE_VERSION}'
    if (target / 'Sparkle.framework').exists():
        return target
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / f'Sparkle-{SPARKLE_VERSION}.tar.xz'
    url = f'https://github.com/sparkle-project/Sparkle/releases/download/{SPARKLE_VERSION}/Sparkle-{SPARKLE_VERSION}.tar.xz'
    urllib.request.urlretrieve(url, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SPARKLE_SHA256:
        raise RuntimeError('Sparkle archive checksum mismatch')
    target.mkdir(exist_ok=True)
    with tarfile.open(archive) as source:
        # Official archive is pinned above; its framework symlinks must be retained.
        source.extractall(target, filter='tar')
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--version')
    parser.add_argument('--build-number', type=int)
    parser.add_argument('--output', type=Path, default=ROOT / 'dist')
    parser.add_argument('--feed-url')
    parser.add_argument('--allow-local-feed', action='store_true', help='Development only: permit a loopback HTTP update feed')
    parser.add_argument('--reuse-backend', action='store_true', help='Development only: reuse a previously built backend')
    args = parser.parse_args()
    config = json.loads((ROOT / 'desktop/macos/version.json').read_text())
    version, build = args.version or config['version'], args.build_number or config['build']
    if not all(part.isdigit() for part in version.split('.')) or build < 1:
        parser.error('Version must be numeric and build number must be positive')
    feed = args.feed_url or config['feed_url']
    url = urlsplit(feed)
    if url.scheme != 'https' and not (args.allow_local_feed and url.scheme == 'http' and url.hostname == '127.0.0.1'):
        parser.error('Production update feeds must use HTTPS')
    public_key = (ROOT / 'desktop/macos/update-public-key.txt').read_text().strip()
    if len(base64.b64decode(public_key, validate=True)) != 32:
        parser.error('A valid Sparkle public key is required')
    framework = sparkle()
    backend_dist = ROOT / 'build/macos/backend-dist'
    if not args.reuse_backend or not (backend_dist / 'CabinetServer.app').exists():
        run(sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
            '--distpath', backend_dist, '--workpath', ROOT / 'build/macos/pyinstaller', ROOT / 'desktop/backend.spec')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    bundle = output / 'Cabinet.app'
    # Only a known build product under the requested output folder may be replaced.
    if bundle.is_symlink():
        raise RuntimeError('Refusing to replace a symlinked build bundle')
    if bundle.exists():
        shutil.rmtree(bundle)
    contents = bundle / 'Contents'
    for directory in ('MacOS', 'Resources', 'Frameworks', 'Helpers'):
        (contents / directory).mkdir(parents=True, exist_ok=True)
    shutil.copytree(backend_dist / 'CabinetServer.app', contents / 'Helpers/CabinetServer.app', symlinks=True)
    shutil.copytree(framework / 'Sparkle.framework', contents / 'Frameworks/Sparkle.framework', symlinks=True)
    (contents / 'Resources/Sparkle-LICENSE.txt').write_text((framework / 'LICENSE').read_text())
    run('swiftc', '-parse-as-library', '-swift-version', '5', '-O', '-target', 'arm64-apple-macos12.0',
        '-framework', 'AppKit', '-framework', 'WebKit', '-framework', 'Sparkle', '-F', framework,
        '-Xlinker', '-rpath', '-Xlinker', '@executable_path/../Frameworks',
        ROOT / 'desktop/macos/Cabinet.swift', '-o', contents / 'MacOS/Cabinet')
    plist = dict(CFBundleExecutable='Cabinet', CFBundleIdentifier=config['bundle_id'],
        CFBundleName='Cabinet', CFBundleDisplayName='藏阁 Cabinet', CFBundlePackageType='APPL',
        CFBundleShortVersionString=version, CFBundleVersion=str(build), CFBundleIconFile='Cabinet',
        LSMinimumSystemVersion=config['minimum_macos'], NSHighResolutionCapable=True,
        NSHumanReadableCopyright='Cabinet · A personal museum of objects and memories.',
        NSAppTransportSecurity={'NSAllowsLocalNetworking': True},
        SUFeedURL=feed, SUPublicEDKey=public_key, SUEnableAutomaticChecks=True,
        SUAutomaticallyUpdate=True, SUAllowsAutomaticUpdates=True, SUEnableSystemProfiling=False,
        SUScheduledCheckInterval=86400, SUVerifyUpdateBeforeExtraction=True, SURequireSignedFeed=True)
    (contents / 'Info.plist').write_bytes(plistlib.dumps(plist))
    icon_root = ROOT / 'build/macos/Cabinet.iconset'
    icon_root.mkdir(parents=True, exist_ok=True)
    large = ROOT / 'build/macos/icon-1024.png'
    run('swift', ROOT / 'desktop/macos/Icon.swift', large)
    for size in (16,32,128,256,512):
        for scale in (1,2):
            name = f'icon_{size}x{size}' + ('@2x' if scale == 2 else '') + '.png'
            run('sips', '-z', str(size*scale), str(size*scale), large, '--out', icon_root / name, stdout=subprocess.DEVNULL)
    run('iconutil', '-c', 'icns', icon_root, '-o', contents / 'Resources/Cabinet.icns')
    run('codesign', '--force', '--sign', '-', bundle)
    run('codesign', '--verify', '--deep', '--strict', '--verbose=2', bundle)
    forbidden = {'museum.db', '.secret-key', '.DS_Store'}
    assert not any(path.name in forbidden for path in bundle.rglob('*')), 'Personal files were accidentally packaged'
    print(f'Built {bundle} — version {version}, build {build}')


if __name__ == '__main__':
    main()
