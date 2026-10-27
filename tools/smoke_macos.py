#!/usr/bin/env python3
"""Exercise the packaged helper, private session, uploads and update-safe data."""
import argparse
import http.cookiejar
from io import BytesIO
import os
from pathlib import Path
import secrets
import selectors
import sqlite3
import subprocess
import tempfile
import urllib.error
import urllib.request
from PIL import Image


def start(app, data):
    token = secrets.token_hex(32)
    env = dict(os.environ, CABINET_DATA_DIR=str(data), CABINET_DESKTOP_TOKEN=token,
               CABINET_PARENT_PID=str(os.getpid()))
    executable = app / 'Contents/Helpers/CabinetServer.app/Contents/MacOS/CabinetServer'
    error_log = open(data / 'test-server.log', 'ab')
    process = subprocess.Popen([str(executable)], env=env, stdout=subprocess.PIPE, stderr=error_log)
    ready = selectors.DefaultSelector()
    ready.register(process.stdout, selectors.EVENT_READ)
    if not ready.select(25):
        process.terminate()
        raise RuntimeError('Packaged backend did not become ready')
    line = process.stdout.readline().decode().strip()
    ready.close()
    if not line.startswith('CABINET_READY '):
        process.terminate()
        raise RuntimeError('Invalid packaged backend startup')
    base = f'http://127.0.0.1:{int(line.split()[1])}'
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    with_error = lambda url: urllib.request.urlopen(base + url, timeout=10)
    try:
        with_error('/')
        raise AssertionError('An unauthenticated page was exposed')
    except urllib.error.HTTPError as error:
        assert error.code == 403
    opener.open(base + '/desktop/session?token=' + token, timeout=10).read()
    return process, error_log, opener, base


def stop(process, log):
    process.terminate()
    process.wait(timeout=8)
    log.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--app', type=Path, default=Path('dist/Cabinet.app'))
    args = parser.parse_args()
    app = args.app.resolve()
    with tempfile.TemporaryDirectory(prefix='cabinet-packaged-smoke-') as directory:
        data = Path(directory)
        process, log, opener, base = start(app, data)
        try:
            photo = BytesIO()
            Image.new('RGB', (16, 16), '#234c3c').save(photo, format='PNG')
            boundary = 'CabinetSmokeMultipart'
            chunks = []
            for key, value in dict(name='打包后保留的藏品', category='其他', date_year='2020', country_code='CN', place_id='1816670').items():
                chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode())
            chunks.append(f'--{boundary}\r\nContent-Disposition: form-data; name="image"; filename="photo.png"\r\nContent-Type: image/png\r\n\r\n'.encode() + photo.getvalue() + f'\r\n--{boundary}--\r\n'.encode())
            request = urllib.request.Request(base + '/objects/new', data=b''.join(chunks),
                headers={'Content-Type':f'multipart/form-data; boundary={boundary}', 'Origin':base})
            assert '打包后保留的藏品'.encode() in opener.open(request, timeout=10).read()
        finally:
            stop(process, log)
        images = list((data / 'storage').iterdir())
        assert len(images) == 1 and images[0].read_bytes() == photo.getvalue()
        # Simulate opening an older schema: migration must back up first.
        with sqlite3.connect(data / 'museum.db') as db:
            db.execute('PRAGMA user_version = 0')
        process, log, opener, base = start(app, data)
        try:
            assert '打包后保留的藏品'.encode() in opener.open(base + '/').read()
            assert opener.open(base + '/storage/' + images[0].name).read() == photo.getvalue()
            assert list((data / 'backups').glob('*.db'))
        finally:
            stop(process, log)
    print('PASS: packaged backend, private access, photo upload, restart persistence, migration backup')


if __name__ == '__main__':
    main()
