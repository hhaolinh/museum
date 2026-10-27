import tempfile
from io import BytesIO
from PIL import Image
from pathlib import Path

import pytest

import app as museum


@pytest.fixture()
def client():
    with tempfile.TemporaryDirectory() as tmp:
        museum.app.config.update(TESTING=True, DATABASE=Path(tmp) / "test.db", UPLOAD_FOLDER=Path(tmp) / "storage", MAX_CONTENT_LENGTH=10 * 1024 * 1024)
        with museum.app.app_context():
            museum.g.pop("db", None)
            museum.init_db()
        with museum.app.test_client() as client:
            yield client


def test_collection_and_detail(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "这格藏柜还是空的".encode() in response.data
    with museum.app.app_context():
        museum.init_db()
        assert museum.get_db().execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 0
    assert client.get("/objects/1").status_code == 404
    created = client.post("/objects/new", data={"name": "测试藏品", "category": "陶瓷"})
    assert client.get(created.headers["Location"]).status_code == 200


def test_add_object(client):
    response = client.post(
        "/objects/new",
        data={"name": "雕花木梳", "category": "木器", "country_code": "TH"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "雕花木梳".encode() in response.data


def image_data():
    stream = BytesIO()
    Image.new("RGB", (8, 8), "green").save(stream, format="PNG")
    stream.seek(0)
    return stream


def test_uploaded_image_is_local_and_served(client):
    response = client.post("/objects/new", data={
        "name": "本地照片", "category": "织物", "image_url": "https://example.com/old.jpg",
        "image": (image_data(), "../../照片.png"),
    }, follow_redirects=True)
    assert response.status_code == 200
    files = list(Path(museum.app.config["UPLOAD_FOLDER"]).iterdir())
    assert len(files) == 1
    assert files[0].suffix == ".png"
    assert f"/storage/{files[0].name}".encode() in response.data
    image_response = client.get(f"/storage/{files[0].name}")
    assert image_response.status_code == 200
    assert image_response.mimetype == "image/png"
    assert image_response.data == files[0].read_bytes()
    assert client.get("/storage/../museum.db").status_code == 404


def test_fake_image_is_rejected(client):
    response = client.post("/objects/new", data={
        "name": "伪装图片", "category": "织物",
        "image": (BytesIO(b"<script>alert(1)</script>"), "fake.png"),
    })
    assert response.status_code == 400
    assert "无法读取".encode() in response.data
    assert not Path(museum.app.config["UPLOAD_FOLDER"]).exists()
    assert "伪装图片".encode() not in client.get("/").data


def test_large_upload_has_friendly_error(client):
    museum.app.config["MAX_CONTENT_LENGTH"] = 1024
    response = client.post("/objects/new", data={
        "name": "大图片", "category": "织物",
        "image": (BytesIO(b"x" * 2048), "large.png"),
    })
    assert response.status_code == 413
    assert b"10 MB" in response.data


def test_missing_name_does_not_save_upload(client):
    response = client.post("/objects/new", data={
        "category": "织物", "image": (image_data(), "photo.png"),
    })
    assert "请填写".encode() in response.data
    assert not Path(museum.app.config["UPLOAD_FOLDER"]).exists()


def test_image_url_still_works(client):
    response = client.post("/objects/new", data={
        "name": "外链照片", "category": "陶瓷", "image_url": "https://example.com/photo.jpg",
    }, follow_redirects=True)
    assert b"https://example.com/photo.jpg" in response.data


@pytest.mark.parametrize("format,extension", [("JPEG", ".jpg"), ("WEBP", ".webp"), ("GIF", ".gif")])
def test_supported_image_formats(client, format, extension):
    stream = BytesIO()
    Image.new("RGB", (8, 8), "green").save(stream, format=format)
    stream.seek(0)
    response = client.post("/objects/new", data={
        "name": "格式测试", "category": "其他", "image": (stream, "photo.bin"),
    })
    assert response.status_code == 302
    files = list(Path(museum.app.config["UPLOAD_FOLDER"]).iterdir())
    assert len(files) == 1
    assert files[0].suffix == extension


def test_failed_database_write_removes_uploaded_file(client, monkeypatch):
    def fail_db():
        raise RuntimeError("database unavailable")
    monkeypatch.setattr(museum, "get_db", fail_db)
    with pytest.raises(RuntimeError, match="database unavailable"):
        client.post("/objects/new", data={
            "name": "保存失败", "category": "其他", "image": (image_data(), "photo.png"),
        })
    assert list(Path(museum.app.config["UPLOAD_FOLDER"]).iterdir()) == []


def test_empty_journeys_and_no_default_year(client):
    page = client.get('/journeys').data.decode()
    assert '记录第一件藏品' in page
    assert '泰国' not in page and '日本' not in page
    assert '2026' not in client.get('/').data.decode()


def test_journeys_group_actual_objects_and_handle_unknown_dates(client):
    for name, date, precision, country, place in [
        ('旧木梳', '2018', 'year', '中国', '杭州'),
        ('茶杯', '2018-05', 'month', '中国', '杭州'),
        ('无日期石头', '', 'unknown', '', ''),
        ('待确认织物', '1990', 'unknown', '中国', '苏州'),
        ('日期写错', '2000-99-99', 'exact', '', ''),
    ]:
        # Legacy rows may contain incomplete or invalid dates; still render safely.
        with museum.app.app_context():
            db = museum.get_db()
            db.execute("INSERT INTO objects (name, category, acquired_date, date_precision, country, place) VALUES (?, ?, ?, ?, ?, ?)",
                       (name, '其他', date, precision, country, place))
            db.commit()
    response = client.get('/journeys')
    assert response.status_code == 200
    page = response.data.decode()
    assert page.count('<h3>杭州</h3>') == 1
    assert '2 件藏品' in page
    assert '日期待补' in page
    assert '1990' not in page and '2000' not in page
    assert '旧木梳' in page and '无日期石头' in page
    home = client.get('/').data.decode()
    assert '<b>2018</b> 最早入藏' in home
    assert '始藏' not in home


@pytest.mark.parametrize('extra', [
    {'country_code': 'ZZ'}, {'country_code': 'CN', 'place_id': '2643743'},
    {'place_id': 'not-a-city'}, {'country': '随便填'}, {'place': '随便填'},
    {'currency_code': 'ABC', 'price_amount': '12'}, {'currency_code': 'USD'},
    {'price_amount': '10'}, {'price_amount': '-1', 'currency_code': 'USD'},
    {'price_amount': 'NaN', 'currency_code': 'USD'}, {'price_amount': '1e3', 'currency_code': 'USD'},
    {'price_amount': '1.001', 'currency_code': 'USD'}, {'price_amount': '1.2', 'currency_code': 'JPY'},
    {'date_precision': 'exact', 'acquired_date': '2020-02-30'},
    {'date_precision': 'exact', 'acquired_date': '2020'},
    {'date_precision': 'year', 'acquired_date': '9999'},
    {'date_precision': 'unknown', 'acquired_date': '2020'},
    {'date_precision': 'made-up'}, {'knowledge_status': 'made-up'},
    {'category': 'made-up'}, {'condition': 'made-up'},
    {'image_url': 'javascript:alert(1)'}, {'price': '随便填'},
])
def test_structured_fields_reject_invalid_values(client, extra):
    data = dict(name='输入校验', category='其他')
    data.update(extra)
    response = client.post('/objects/new', data=data)
    assert response.status_code == 400
    with museum.app.app_context():
        assert museum.get_db().execute('SELECT COUNT(*) FROM objects').fetchone()[0] == 0


def test_structured_object_and_map_filters(client):
    response = client.post('/objects/new', data=dict(name='北京茶杯', category='陶瓷',
        country_code='CN', place_id='1816670', date_precision='year', acquired_date='2020',
        price_amount='12.50', currency_code='CNY', condition='良好'))
    assert response.status_code == 302
    with museum.app.app_context():
        item = museum.get_db().execute('SELECT * FROM objects').fetchone()
        assert item['country'] == '中国'
        assert 'Beijing' in item['place']
        assert item['price'] == '12.50 CNY'
    page = client.get('/journeys?view=map&year=2020').data.decode()
    assert 'data-location="1816670"' in page and '北京茶杯' in page
    client.post('/objects/new', data=dict(name='未知地点', category='其他'))
    unknown = client.get('/journeys?view=map&year=unknown').data.decode()
    assert 'data-location="1816670"' not in unknown
    assert '未知地点' in unknown and '1 件藏品待定位' in unknown


def test_places_search_and_country_boundary(client):
    response = client.get('/api/places?country=CN&q=北京')
    assert response.status_code == 200
    assert any(city['id'] == '1816670' for city in response.json['cities'])
    assert not any(city['id'] == '2643743' for city in response.json['cities'])
    assert client.get('/api/places?country=ZZ').status_code == 400
    assert client.get('/api/places?country=CN&q=nonexistent-city-xyz').json['cities'] == []


def test_existing_schema_is_migrated_without_losing_records(client, tmp_path):
    import sqlite3
    old = tmp_path / 'old.db'
    with sqlite3.connect(old) as db:
        db.execute('CREATE TABLE objects (id INTEGER PRIMARY KEY, name TEXT, category TEXT, country TEXT)')
        db.execute("INSERT INTO objects VALUES (1, '旧藏品', '其他', '中国')")
    previous = museum.app.config['DATABASE']
    try:
        museum.app.config['DATABASE'] = old
        with museum.app.app_context():
            museum.init_db()
            item = museum.get_db().execute('SELECT * FROM objects').fetchone()
            assert item['name'] == '旧藏品' and item['place_id'] == '' and item['currency_code'] == ''
            museum.init_db()
    finally:
        museum.app.config['DATABASE'] = previous


@pytest.mark.parametrize('amount,code,expected', [('0', 'USD', '0.00 USD'), ('12', 'JPY', '12 JPY'), ('1.234', 'KWD', '1.234 KWD')])
def test_currency_precision_and_zero_price(client, amount, code, expected):
    response = client.post('/objects/new', data=dict(name='价格测试', category='其他', price_amount=amount, currency_code=code))
    assert response.status_code == 302
    assert expected.encode() in client.get(response.headers['Location']).data


def test_map_groups_and_switch_preserve_year(client):
    for name, year in [('第一只杯子','2020'), ('第二只杯子','2020'), ('新杯子','2021')]:
        response = client.post('/objects/new', data=dict(name=name, category='陶瓷', country_code='CN', place_id='1816670', date_precision='year', acquired_date=year))
        assert response.status_code == 302
    page = client.get('/journeys?view=map&year=2020').data.decode()
    assert page.count('class="atlas-pin"') == 1
    assert '第一只杯子' in page and '第二只杯子' in page and '新杯子' not in page
    assert 'view=timeline&amp;year=2020' in page
    assert '2 件藏品' in page


def test_search_handles_latin_accents_and_invalid_dates_remain_rejected(client):
    data = client.get('/api/places?country=BR&q=sao paulo').json
    assert any('São Paulo' in city['label'] for city in data['cities'])
    response = client.post('/objects/new', data=dict(name='无效月份', category='其他', date_precision='month', acquired_date='2020-13'))
    assert response.status_code == 400


@pytest.mark.parametrize('parts,stored,precision', [
    ({'date_year':'','date_month':'','date_day':''}, '', 'unknown'),
    ({'date_year':'2020'}, '2020', 'year'),
    ({'date_year':'2020','date_month':'2'}, '2020-02', 'month'),
    ({'date_year':'2020','date_month':'2','date_day':'29'}, '2020-02-29', 'exact'),
])
def test_optional_date_parts_infer_precision(client, parts, stored, precision):
    response = client.post('/objects/new', data=dict(name='日期测试', category='其他', **parts))
    assert response.status_code == 302
    with museum.app.app_context():
        row = museum.get_db().execute('SELECT acquired_date, date_precision FROM objects').fetchone()
        assert (row['acquired_date'], row['date_precision']) == (stored, precision)


@pytest.mark.parametrize('parts', [
    {'date_month':'2'}, {'date_day':'3'}, {'date_year':'2020','date_day':'3'},
    {'date_year':'2021','date_month':'2','date_day':'29'},
    {'date_year':'2020','date_month':'13'}, {'date_year':'2020','date_month':'1','date_day':'32'},
    {'date_year':'123123'}, {'date_year':'202x'}, {'date_year':'9999'},
])
def test_date_parts_reject_gaps_and_invalid_calendar_dates(client, parts):
    response = client.post('/objects/new', data=dict(name='错误日期', category='其他', **parts))
    assert response.status_code == 400


def test_new_form_has_no_precision_mode_or_separate_city_search(client):
    page = client.get('/objects/new').data.decode()
    assert 'name="date_precision"' not in page
    assert 'id="city-search"' not in page
    assert page.count('data-search-select') == 3
    assert 'id="date-year"' in page and 'id="date-month"' in page and 'id="date-day"' in page
    assert 'id="currency-code" data-search-select disabled' in page


def test_city_labels_include_chinese_names(client):
    response = client.get('/api/places?country=CN&q=北京')
    assert any(city['label'] == '北京 · Beijing' for city in response.json['cities'])
    response = client.get('/api/places?country=CN&q=Shenzhen')
    assert any(city['label'].startswith('深圳 · Shenzhen') for city in response.json['cities'])


def test_existing_mapped_objects_get_localized_display(client):
    with museum.app.app_context():
        db = museum.get_db()
        db.execute("INSERT INTO objects (name, category, place, country, place_id, country_code) VALUES (?, ?, ?, ?, ?, ?)",
                   ('原有藏品', '其他', 'Beijing', '中国', '1816670', 'CN'))
        db.commit()
    assert '北京 · Beijing'.encode() in client.get('/objects/1').data
    assert '北京 · Beijing'.encode() in client.get('/journeys?view=map').data


def test_evidence_removed_from_form_detail_and_new_schema(client):
    assert '证据'.encode() not in client.get('/objects/new').data
    response = client.post('/objects/new', data=dict(name='没有证据字段', category='其他', evidence='不再录入'))
    page = client.get(response.headers['Location']).data
    assert '暂未附上证据'.encode() not in page
    assert '不再录入'.encode() not in page
    with museum.app.app_context():
        assert 'evidence' not in {row[1] for row in museum.get_db().execute('PRAGMA table_info(objects)')}
