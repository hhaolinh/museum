from pathlib import Path
from datetime import datetime, date
from uuid import uuid4
import sqlite3
import warnings
import hmac

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for, send_from_directory, session
from PIL import Image, UnidentifiedImageError
from local_data import runtime_config, prepare_database, SCHEMA_VERSION
from catalog import COUNTRIES, CITIES, CURRENCIES, CATEGORIES, CONDITIONS, find_cities, validate_object, city_label


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "museum.db"

app = Flask(__name__)
app.config.update(runtime_config(BASE_DIR))
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024


@app.before_request
def desktop_access():
    token = app.config.get('DESKTOP_TOKEN', '')
    if not token:
        return None
    if request.path == '/desktop/session' and request.method == 'GET':
        if not hmac.compare_digest(request.args.get('token', '').encode(), token.encode()):
            abort(403)
        session['desktop_token'] = token
        response = redirect(url_for('index'))
        response.headers['Cache-Control'] = 'no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response
    if not hmac.compare_digest(str(session.get('desktop_token', '')).encode(), token.encode()):
        abort(403)
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        origin = request.headers.get('Origin')
        if origin and origin != request.host_url.rstrip('/'):
            abort(403)
    return None


@app.context_processor
def form_reference_data():
    form = g.reference_form if "reference_form" in g else request.form
    country = form.get("country_code", "")
    cities, _ = find_cities(country, selected=form.get("place_id", ""))
    return dict(country_options=sorted(COUNTRIES.items(), key=lambda pair: pair[1]["english"]),
                currency_options=CURRENCIES, category_options=CATEGORIES,
                condition_options=CONDITIONS, city_options=cities,
                current_year=date.today().year,
                country_currencies={code: item["currency"] for code, item in COUNTRIES.items()})


@app.get("/api/places")
def place_options():
    country = request.args.get("country", "")
    if country not in COUNTRIES:
        return {"error": "请选择有效的国家或地区。"}, 400
    cities, total = find_cities(country, request.args.get("q", ""))
    return {"cities": cities, "total": total}


@app.route("/storage/<filename>")
def stored_image(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.errorhandler(413)
def upload_too_large(_error):
    g.reference_form = {}
    flash("图片和表单总大小不能超过 10 MB。请压缩图片后重新选择。")
    return render_template("new.html", form={}), 413


def save_image(upload):
    """Validate actual image contents, then store using an opaque filename."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(upload.stream) as picture:
                extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "GIF": ".gif"}.get(picture.format)
                if extension is None:
                    raise ValueError("请选择 JPEG、PNG、WebP 或 GIF 图片。")
                picture.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValueError("无法读取这张图片，请选择有效的 JPEG、PNG、WebP 或 GIF 文件。") from error
    folder = Path(app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (uuid4().hex + extension)
    upload.stream.seek(0)
    try:
        upload.save(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS objects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            acquired_date TEXT,
            date_precision TEXT NOT NULL DEFAULT 'exact',
            place TEXT,
            country TEXT,
            source TEXT,
            price TEXT,
            story TEXT,
            material TEXT,
            technique TEXT,
            maker TEXT,
            culture_region TEXT,
            condition TEXT,
            knowledge_status TEXT NOT NULL DEFAULT 'unknown',
            image_url TEXT,
            featured INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_objects_country ON objects(country);
        CREATE INDEX IF NOT EXISTS idx_objects_category ON objects(category);
        """
    )
    columns = {row[1] for row in db.execute("PRAGMA table_info(objects)")}
    for field in ("country_code", "place_id", "price_amount", "currency_code"):
        if field not in columns:
            db.execute(f"ALTER TABLE objects ADD COLUMN {field} TEXT NOT NULL DEFAULT ''")
    if app.config.get('DATA_DIRECTORY'):
        db.execute(f'PRAGMA user_version = {SCHEMA_VERSION}')
    db.commit()


def acquisition_year(item):
    if item["date_precision"] == "unknown":
        return None
    value = (item["acquired_date"] or "").strip()
    formats = {4: "%Y", 7: "%Y-%m", 10: "%Y-%m-%d"}
    if len(value) not in formats:
        return None
    try:
        return datetime.strptime(value, formats[len(value)]).year
    except ValueError:
        return None


def display_item(row):
    item = dict(row)
    city = CITIES.get(item['place_id'])
    if city and city['country'] == item['country_code']:
        item['place'] = city_label(city)
    return item


@app.route("/")
def index():
    db = get_db()
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sql = "SELECT * FROM objects WHERE 1=1"
    params = []
    if query:
        sql += " AND (name LIKE ? OR story LIKE ? OR place LIKE ? OR country LIKE ?)"
        params.extend([f"%{query}%"] * 4)
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY featured DESC, acquired_date DESC, id DESC"
    objects = [display_item(row) for row in db.execute(sql, params)]
    categories = db.execute(
        "SELECT category, COUNT(*) AS count FROM objects GROUP BY category ORDER BY category"
    ).fetchall()
    countries = db.execute(
        "SELECT COUNT(DISTINCT country) FROM objects WHERE country != ''"
    ).fetchone()[0]
    years = [year for item in db.execute("SELECT acquired_date, date_precision FROM objects")
             if (year := acquisition_year(item)) is not None]
    return render_template(
        "index.html", objects=objects, categories=categories, countries=countries,
        total=db.execute("SELECT COUNT(*) FROM objects").fetchone()[0],
        query=query, active_category=category, first_year=min(years) if years else None,
    )


@app.route("/objects/<int:object_id>")
def object_detail(object_id):
    item = get_db().execute("SELECT * FROM objects WHERE id = ?", (object_id,)).fetchone()
    if item is None:
        abort(404)
    return render_template("detail.html", item=display_item(item))


@app.route("/objects/new", methods=("GET", "POST"))
def new_object():
    if request.method == "POST":
        try:
            data = validate_object(request.form)
        except ValueError as error:
            flash(str(error))
            return render_template("new.html", form=request.form), 400
        fields = list(data)
        values = list(data.values())
        upload = request.files.get("image")
        saved_image = None
        if upload and upload.filename:
            try:
                saved_image = save_image(upload)
            except ValueError as error:
                flash(str(error))
                return render_template("new.html", form=request.form), 400
            values[fields.index("image_url")] = url_for("stored_image", filename=saved_image.name)
        try:
            db = get_db()
            db.execute(
                f"INSERT INTO objects ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
                values,
            )
            db.commit()
        except Exception:
            if saved_image:
                saved_image.unlink(missing_ok=True)
            if "db" in g:
                g.db.rollback()
            raise
        object_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        return redirect(url_for("object_detail", object_id=object_id))
    return render_template("new.html", form={})


@app.route("/journeys")
def journeys():
    all_items = [display_item(row) for row in get_db().execute("SELECT * FROM objects ORDER BY acquired_date DESC, id DESC")]
    selected_year = request.args.get("year", "")
    view = "map" if request.args.get("view") == "map" else "timeline"
    available_years = sorted({acquisition_year(item) for item in all_items if acquisition_year(item)}, reverse=True)
    if selected_year and selected_year not in {str(year) for year in available_years} | {"unknown"}:
        selected_year = ""
    items = [item for item in all_items if not selected_year or
             (str(acquisition_year(item)) if acquisition_year(item) else "unknown") == selected_year]
    map_groups = {}
    unlocated = []
    for item in items:
        city = CITIES.get(item["place_id"])
        if not city or city["country"] != item["country_code"]:
            unlocated.append(item)
            continue
        group = map_groups.setdefault(item["place_id"], dict(
            id=item["place_id"], name=item["place"], country=item["country"], objects=[],
            x=(city["lon"] + 180) / 3.6, y=(90 - city["lat"]) / 1.8))
        group["objects"].append(item)
    map_groups = list(map_groups.values())
    years = {}
    countries = set()
    places = set()
    for item in items:
        year = acquisition_year(item)
        country = (item["country"] or "").strip()
        place = (item["place"] or "").strip()
        if country:
            countries.add(country)
        if country or place:
            places.add((country, place))
        stops = years.setdefault(year, {})
        stops.setdefault((country, place), []).append(item)
    timeline = [
        {"year": year, "stops": [
            {"country": country, "place": place, "objects": objects}
            for (country, place), objects in years[year].items()
        ]}
        for year in sorted(years, key=lambda value: value or 0, reverse=True)
    ]
    return render_template("journeys.html", timeline=timeline, total=len(items),
                           countries=len(countries), places=len(places), view=view,
                           selected_year=selected_year, available_years=available_years,
                           map_groups=map_groups, unlocated=unlocated, has_records=bool(all_items))


with app.app_context():
    prepare_database(app.config)
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
