#!/usr/bin/env python3
"""Prepare signed release assets. Publishing is deliberately a separate step."""
import argparse
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
from urllib.parse import urlsplit
from xml.etree import ElementTree as ET
from build_macos import ROOT, sparkle, run

SPARKLE_NS = 'http://www.andymatuschak.org/xml-namespaces/sparkle'
ET.register_namespace('sparkle', SPARKLE_NS)


def prepare(app, output, prefix, notes=''):
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    tools = sparkle() / 'bin'
    account = info['CFBundleIdentifier']
    public = subprocess.check_output([str(tools / 'generate_keys'), '--account', account, '-p'], text=True).strip()
    if public != info['SUPublicEDKey']:
        raise RuntimeError('The signing key in Keychain does not match this app. Nothing was published.')
    run('codesign', '--verify', '--deep', '--strict', app)
    output.mkdir(parents=True, exist_ok=True)
    filename = f"Cabinet-{info['CFBundleShortVersionString']}-arm64.zip"
    archive = output / filename
    if archive.exists():
        raise RuntimeError(f'Release archive already exists: {archive}')
    run('ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', app, archive)
    appcast = output / 'appcast.xml'
    # One Keychain read signs the archive and the feed in the same pass.
    # Do not export the private key or repeatedly request it for verification.
    run(tools / 'generate_appcast', '--account', account, '--download-url-prefix', prefix.rstrip('/') + '/',
        '--maximum-deltas', '0', '-o', appcast, output)
    document = ET.parse(appcast)
    enclosure = document.find('./channel/item/enclosure')
    if enclosure is None:
        raise RuntimeError('The generated update feed has no release archive')
    signature = enclosure.attrib[f'{{{SPARKLE_NS}}}edSignature']
    run('swift', ROOT / 'desktop/macos/VerifyArchive.swift', info['SUPublicEDKey'], signature, archive)
    # Keep the installer outside the appcast input: automatic updates use the ZIP.
    installer = output / f"Cabinet-{info['CFBundleShortVersionString']}-arm64.dmg"
    if installer.exists():
        raise RuntimeError(f'Installer already exists: {installer}')
    with tempfile.TemporaryDirectory(prefix='cabinet-dmg-') as temporary:
        staging = Path(temporary)
        shutil.copytree(app, staging / 'Cabinet.app', symlinks=True)
        (staging / 'Applications').symlink_to('/Applications')
        run('hdiutil', 'create', '-fs', 'HFS+', '-volname', 'Cabinet', '-srcfolder', staging,
            '-format', 'UDZO', installer)
    manifest = dict(version=info['CFBundleShortVersionString'], build=info['CFBundleVersion'],
                    archive=filename, installer=installer.name, feed='appcast.xml',
                    download_url=prefix.rstrip('/') + '/' + filename)
    (output / 'release.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, default=ROOT / 'dist/Cabinet.app')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--download-url-prefix')
    parser.add_argument('--allow-local-feed', action='store_true', help='For the isolated update test only')
    args = parser.parse_args()
    info = plistlib.loads((args.app / 'Contents/Info.plist').read_bytes())
    prefix = args.download_url_prefix or f"https://github.com/hhaolinh/museum/releases/download/v{info['CFBundleShortVersionString']}"
    parsed = urlsplit(prefix)
    if parsed.scheme != 'https' and not (args.allow_local_feed and parsed.scheme == 'http' and parsed.hostname == '127.0.0.1'):
        parser.error('Release URLs must use HTTPS')
    output = args.output or ROOT / 'dist/release' / f"v{info['CFBundleShortVersionString']}"
    manifest = prepare(args.app.resolve(), output.resolve(), prefix)
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
