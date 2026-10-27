import sqlite3
from pathlib import Path
import pytest
import app as museum
from local_data import prepare_database, runtime_config, SCHEMA_VERSION


def test_desktop_data_and_secret_are_outside_bundle(tmp_path, monkeypatch):
    data = tmp_path / 'User Data'
    bundle = tmp_path / 'Cabinet.app'
    bundle.mkdir()
    monkeypatch.setenv('CABINET_DATA_DIR', str(data))
    monkeypatch.setenv('CABINET_DESKTOP_TOKEN', 'a' * 64)
    config = runtime_config(bundle)
    assert config['DATABASE'] == data / 'museum.db'
    assert config['UPLOAD_FOLDER'] == data / 'storage'
    assert len(config['SECRET_KEY']) == 64
    assert runtime_config(bundle)['SECRET_KEY'] == config['SECRET_KEY']
    assert (data / '.secret-key').stat().st_mode & 0o777 == 0o600
    assert list(bundle.iterdir()) == []


def test_backup_before_schema_migration(tmp_path):
    database = tmp_path / 'museum.db'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE objects (id INTEGER PRIMARY KEY, name TEXT, category TEXT, country TEXT)')
        db.execute("INSERT INTO objects VALUES (1, '保留的收藏', '其他', '中国')")
    config = dict(DATABASE=database, DATA_DIRECTORY=tmp_path)
    prepare_database(config)
    backup = list((tmp_path / 'backups').glob('*.db'))
    assert len(backup) == 1
    with sqlite3.connect(backup[0]) as db:
        assert db.execute('SELECT name FROM objects').fetchone()[0] == '保留的收藏'
    with sqlite3.connect(database) as db:
        db.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')
    prepare_database(config)
    assert len(list((tmp_path / 'backups').glob('*.db'))) == 1


def test_newer_database_is_not_modified(tmp_path):
    database = tmp_path / 'museum.db'
    with sqlite3.connect(database) as db:
        db.execute('PRAGMA user_version = 999')
    with pytest.raises(RuntimeError, match='newer version'):
        prepare_database(dict(DATABASE=database, DATA_DIRECTORY=tmp_path))
    assert not (tmp_path / 'backups').exists()


def test_loopback_requests_need_desktop_session(monkeypatch, tmp_path):
    token = 'b' * 64
    monkeypatch.setitem(museum.app.config, 'DESKTOP_TOKEN', token)
    monkeypatch.setitem(museum.app.config, 'DATABASE', tmp_path / 'desktop.db')
    with museum.app.app_context():
        museum.init_db()
    with museum.app.test_client() as client:
        assert client.get('/').status_code == 403
        assert client.get('/static/style.css').status_code == 403
        assert client.get('/desktop/session?token=wrong').status_code == 403
        assert client.get('/desktop/session?token=中文').status_code == 403
        assert client.get('/desktop/session?token=' + token).status_code == 302
        assert client.get('/').status_code == 200
        assert client.post('/objects/new', headers={'Origin':'https://example.com'}, data={}).status_code == 403
