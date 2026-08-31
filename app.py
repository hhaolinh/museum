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
                    "蓝绿色变色织物", "织物", "2026-08-27", "exact",
                    "曼谷", "泰国", "Pha ToomThong", "฿2,400",
                    "我在三个颜色之间纠结了很久，最后发现这一块随着光线和角度会悄悄地从蓝色变成绿色。店主说它叫 Pha ToomThong；我先把购买当天听到的说法保存下来，留待以后考证。",
                    "丝", "手工织造", "佚名", "泰国", "极佳",
                    "seller", "店主口述 · 购买当天的照片",
                    "https://images.unsplash.com/photo-1606722590583-6951b5ea92ad?auto=format&fit=crop&w=1400&q=85", 1,
                ),
                (
                    "靛蓝市集布料", "织物", "2026-08-24", "exact",
                    "清迈", "泰国", "周末市集", "฿680",
                    "它折在一叠颜色更鲜亮的布料下面。最后选中它，恰恰是因为那种并不均匀的靛蓝。",
                    "棉", "防染", "佚名", "泰国北部", "良好",
                    "guess", "个人记忆 · 照片",
                    "https://images.unsplash.com/photo-1590736969955-71cc94901144?auto=format&fit=crop&w=1400&q=85", 0,
                ),
                (
                    "小型釉陶器", "陶瓷", "2018", "year",
                    "城市不详", "日本", "来源不详", "价格不详",
                    "大概是在一次日本家庭旅行中买到的，具体城市已经记不清了。也许以后找到旧照片，能够重新确定它来自哪里。",
                    "炻器", "施釉", "佚名", "日本", "良好",
                    "unknown", "仅凭记忆",
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
            flash("请填写藏品名称和类别，让它在收藏中有一个位置。")
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
