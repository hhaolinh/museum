# 藏阁 Cabinet

一座记录物件、旅途、来源与记忆的私人博物馆。使用 Flask 与 SQLite 构建。

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --debug
```

The database is created automatically with three example records. Set a production `SECRET_KEY` before deploying.

## First release

- Collection gallery with search and category filters
- Object pages with acquisition, provenance, condition, and story
- Knowledge status: confirmed, seller-provided, guessed, or needs research
- Old-object records with approximate dates and evidence
- Journey overview grouped by year and place
- Responsive add-object workflow
