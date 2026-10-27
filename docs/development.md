# Development

[Back to the project](../README.md)

Cabinet uses Flask, Jinja templates, SQLite, and plain JavaScript. Runtime dependencies are listed in [requirements.txt](../requirements.txt).

## Run and test

After following the README setup:

```bash
flask --app app run --debug
```

Install the test dependency and run the suite:

```bash
pip install pytest
python -m pytest -q
```

## Reference data

The map, city catalogue, and currency metadata are bundled with the app. Data sources, licenses, and regeneration instructions are in [data/SOURCES.md](../data/SOURCES.md). The generation script is [tools/build_reference_data.py](../tools/build_reference_data.py); its build dependencies are separate from app runtime dependencies.

## Local files

Keep `museum.db`, uploaded files under `storage/`, virtual environments, and OS metadata out of commits. A fresh database starts empty. See the [backup guide](guide.md#back-up-your-collection) before working with personal collection data.

## macOS application

See [macOS build and release instructions](macos.md#maintainer-build-and-publish) for packaging, update signing, and release publishing.
