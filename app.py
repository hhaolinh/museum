from pathlib import Path
import sqlite3

from flask import Flask, abort, flash, g, redirect, render_template, request, url_for


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "museum.db"

app = Flask(__name__)
app.config.update(SECRET_KEY="dev-change-me", DATABASE=DATABASE)


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
            evidence TEXT,
            image_url TEXT,
            featured INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_objects_country ON objects(country);
        CREATE INDEX IF NOT EXISTS idx_objects_category ON objects(category);
        """
    )
    if db.execute("SELECT COUNT(*) FROM objects").fetchone()[0] == 0:
        db.executemany(
            """
            INSERT INTO objects
            (name, category, acquired_date, date_precision, place, country, source,
             price, story, material, technique, maker, culture_region, condition,
             knowledge_status, evidence, image_url, featured)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    "Blue–green woven textile", "Textile", "2026-08-27", "exact",
                    "Bangkok", "Thailand", "Pha ToomThong", "฿2,400",
                    "I kept turning it in the light because the blue quietly became green. The shopkeeper called it Pha ToomThong; that name is kept here as part of the day, pending further research.",
                    "Silk", "Hand woven", "Unknown", "Thailand", "Excellent",
                    "seller", "Seller description · purchase-day photographs",
                    "https://images.unsplash.com/photo-1606722590583-6951b5ea92ad?auto=format&fit=crop&w=1400&q=85", 1,
                ),
                (
                    "Indigo market cloth", "Textile", "2026-08-24", "exact",
                    "Chiang Mai", "Thailand", "Weekend market", "฿680",
                    "Found folded beneath a stack of brighter cloths. The uneven indigo was the reason I chose it.",
                    "Cotton", "Resist dye", "Unknown", "Northern Thailand", "Good",
                    "guess", "Memory · photographs",
                    "https://images.unsplash.com/photo-1590736969955-71cc94901144?auto=format&fit=crop&w=1400&q=85", 0,
                ),
                (
                    "Small glazed vessel", "Ceramic", "2018", "year",
                    "Unknown city", "Japan", "Unknown", "Unknown",
                    "Probably bought during a family trip to Japan. The exact city has slipped away; an old photograph may eventually place it.",
                    "Stoneware", "Glazed", "Unknown", "Japan", "Good",
                    "unknown", "Memory only",
                    "https://images.unsplash.com/photo-1610701596007-11502861dcfa?auto=format&fit=crop&w=1400&q=85", 0,
                ),
            ],
        )
    db.commit()


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
    objects = db.execute(sql, params).fetchall()
    categories = db.execute(
        "SELECT category, COUNT(*) AS count FROM objects GROUP BY category ORDER BY category"
    ).fetchall()
    countries = db.execute(
        "SELECT COUNT(DISTINCT country) FROM objects WHERE country != ''"
    ).fetchone()[0]
    return render_template(
        "index.html", objects=objects, categories=categories, countries=countries,
        total=db.execute("SELECT COUNT(*) FROM objects").fetchone()[0],
        query=query, active_category=category,
    )


@app.route("/objects/<int:object_id>")
def object_detail(object_id):
    item = get_db().execute("SELECT * FROM objects WHERE id = ?", (object_id,)).fetchone()
    if item is None:
        abort(404)
    return render_template("detail.html", item=item)


@app.route("/objects/new", methods=("GET", "POST"))
def new_object():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        category = request.form.get("category", "").strip()
        if not name or not category:
            flash("Give the object a name and category so it has a place in the collection.")
            return render_template("new.html", form=request.form)
        fields = [
            "name", "category", "acquired_date", "date_precision", "place", "country",
            "source", "price", "story", "material", "technique", "maker",
            "culture_region", "condition", "knowledge_status", "evidence", "image_url",
        ]
        values = [request.form.get(field, "").strip() for field in fields]
        db = get_db()
        db.execute(
            f"INSERT INTO objects ({', '.join(fields)}) VALUES ({', '.join('?' for _ in fields)})",
            values,
        )
        db.commit()
        object_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        return redirect(url_for("object_detail", object_id=object_id))
    return render_template("new.html", form={})


@app.route("/journeys")
def journeys():
    groups = get_db().execute(
        """
        SELECT country, place, substr(acquired_date, 1, 4) AS year, COUNT(*) AS count
        FROM objects
        GROUP BY country, place, year
        ORDER BY year DESC, country, place
        """
    ).fetchall()
    return render_template("journeys.html", groups=groups)


with app.app_context():
    init_db()


if __name__ == "__main__":
    app.run(debug=True)
