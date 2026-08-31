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
    assert b"Blue\xe2\x80\x93green woven textile" in response.data
    assert client.get("/objects/1").status_code == 200


def test_add_object(client):
    response = client.post(
        "/objects/new",
        data={"name": "Carved comb", "category": "Adornment", "country": "Thailand"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Carved comb" in response.data
