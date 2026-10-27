<p align="center">选择语言 / Language: <a href="README.zh-CN.md">简体中文</a> · <strong>English</strong></p>

<p align="center">
  <img src="docs/cabinet.svg" alt="Cabinet — Objects remember what we forget" width="100%">
</p>

<p align="center">
  <strong>A personal museum of objects, journeys, origins, and memories.</strong><br>
  Keep the things you bring home, together with the stories they carry.
</p>

## Every object has a journey

A textile brought home from a trip, an old ceramic, a small thing you cannot quite throw away. Cabinet brings their photos, origins, and stories together in a personal museum on your own computer.

## Features

- **Organize your collection** — browse photos, search names, stories, and places, and filter by category.
- **Keep the story** — record origins, materials, craftsmanship, purchase prices, and personal memories.
- **Revisit your journeys** — follow your collection through a timeline or explore its origins on a world map.
- **Leave room for uncertainty** — record a year, a month, a full date, or no date at all; distinguish facts, accounts, and guesses.
- **Keep it local** — upload your own photos, with no account or subscription required.

## Quick start

Requires **Python 3.11 or newer**.

```bash
git clone https://github.com/hhaolinh/museum.git
cd museum
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
flask --app app run
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) and add your first object.

On Windows, use `.venv\Scripts\activate` to activate the environment. Cabinet currently runs as a personal, local application with a Chinese interface.

## Documentation

- [Usage and backups](docs/guide.md)
- [Development](docs/development.md)
- [Data sources and licenses](data/SOURCES.md)

---

<p align="center"><sub>Objects remember what we forget.</sub></p>
