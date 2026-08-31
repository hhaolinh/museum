import tempfile
from pathlib import Path

import pytest

import app as museum


@pytest.fixture()
def client():
    with tempfile.TemporaryDirectory() as tmp:
        museum.app.config.update(TESTING=True, DATABASE=Path(tmp) / "test.db")
        with museum.app.app_context():
            museum.g.pop("db", None)
            museum.init_db()
        with museum.app.test_client() as client:
            yield client


def test_collection_and_detail(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "蓝绿色变色织物".encode() in response.data
    assert client.get("/objects/1").status_code == 200


def test_add_object(client):
    response = client.post(
        "/objects/new",
        data={"name": "雕花木梳", "category": "装饰品", "country": "泰国"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "雕花木梳".encode() in response.data
