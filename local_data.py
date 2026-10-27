"""Writable data lives outside a packaged application's resources."""
import os
from pathlib import Path
import secrets
import sqlite3
from datetime import datetime, timezone

SCHEMA_VERSION = 1


def runtime_config(base_dir):
    directory = os.environ.get('CABINET_DATA_DIR')
    if not directory:
        return dict(DATABASE=base_dir / 'museum.db', UPLOAD_FOLDER=base_dir / 'storage',
                    SECRET_KEY=os.environ.get('SECRET_KEY', 'dev-change-me'), DESKTOP_TOKEN='')
    root = Path(directory).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    (root / 'storage').mkdir(exist_ok=True, mode=0o700)
    key_path = root / '.secret-key'
    try:
        descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, 'w') as handle:
            handle.write(secrets.token_hex(32))
    secret = key_path.read_text().strip()
    if len(secret) < 32:
        raise RuntimeError('The local session key is damaged; personal data was not changed.')
    return dict(DATABASE=root / 'museum.db', UPLOAD_FOLDER=root / 'storage', SECRET_KEY=secret,
                DESKTOP_TOKEN=os.environ.get('CABINET_DESKTOP_TOKEN', ''), DATA_DIRECTORY=root,
                SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Strict', TRUSTED_HOSTS=['127.0.0.1'])


def prepare_database(config):
    """Back up an older desktop database before changing its schema."""
    path = Path(config['DATABASE'])
    if not config.get('DATA_DIRECTORY') or not path.exists():
        return
    with sqlite3.connect(path) as source:
        version = source.execute('PRAGMA user_version').fetchone()[0]
        if version > SCHEMA_VERSION:
            raise RuntimeError('This collection needs a newer version of Cabinet.')
        if version < SCHEMA_VERSION:
            directory = config['DATA_DIRECTORY'] / 'backups'
            directory.mkdir(exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
            with sqlite3.connect(directory / f'museum-before-schema-{SCHEMA_VERSION}-{timestamp}.db') as target:
                source.backup(target)
