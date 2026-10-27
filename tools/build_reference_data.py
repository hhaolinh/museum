"""Regenerate bundled data: pip install geonamescache==3.0.2 Babel==2.18.0 pyshp==3.1.6.
Download https://naturalearth.s3.amazonaws.com/110m_physical/ne_110m_land.zip
and https://download.geonames.org/export/dump/admin1CodesASCII.txt,
Also download https://download.geonames.org/export/dump/alternateNamesV2.zip.
Pass land zip, admin1 text, and alternateNamesV2 zip paths as arguments. Runtime does not need these packages.
"""
import json
import re
import sys
import zipfile
from pathlib import Path
import geonamescache
from babel import Locale
from babel.numbers import get_currency_name, get_currency_precision, get_territory_currencies
import shapefile

ROOT = Path(__file__).resolve().parents[1]
cache = geonamescache.GeonamesCache()
locale = Locale.parse('zh_CN')
countries = {}
currency_codes = set()
for code, country in cache.get_countries().items():
    if code not in locale.territories:
        continue
    currencies = get_territory_currencies(code)
    currency_codes.update(currencies)
    countries[code] = {'name': locale.territories.get(code, country['name']), 'english': country['name'],
                       'currency': currencies[0] if currencies else ''}
admin_names = {parts[0]: parts[1] for line in Path(sys.argv[2]).read_text().splitlines() if len(parts := line.split('\t')) >= 2}
cities = {}
for city in cache.get_cities().values():
    if city['countrycode'] not in countries:
        continue
    aliases = sorted({alias for alias in city['alternatenames'] if re.fullmatch(r'[\u3400-\u9fff]{2,20}', alias)}, key=lambda x: (len(x), x))
    cities[str(city['geonameid'])] = {'name': city['name'], 'aliases': aliases,
        'country': city['countrycode'], 'lat': round(city['latitude'], 5), 'lon': round(city['longitude'], 5),
        'population': city['population'], 'region': admin_names.get(city['countrycode'] + '.' + city['admin1code'], '')}
# The short alias list has no language/history flags; display names must come
# from the full export, filtering historical/colloquial names before ranking.
chinese = {}
languages = {'zh-Hans': 0, 'zh-CN': 1, 'zh': 2, 'zh-Hant': 3, 'zh-TW': 4, 'zh-HK': 5}
with zipfile.ZipFile(sys.argv[3]) as names_archive:
    with names_archive.open('alternateNamesV2.txt') as names:
        for line in names:
            parts = line.decode('utf-8').rstrip('\r\n').split('\t')
            if len(parts) < 8 or parts[1] not in cities or parts[2] not in languages:
                continue
            if parts[7] == '1' or parts[6] == '1' or (len(parts) > 9 and parts[9]):
                continue
            name = parts[3]
            if not re.search(r'[\u3400-\u9fff]', name):
                continue
            rank = (0 if parts[4] == '1' else 1, languages[parts[2]], 0 if parts[5] == '1' else 1, len(name), name)
            if parts[1] not in chinese or rank < chinese[parts[1]][0]:
                chinese[parts[1]] = (rank, name)
for key, (_, name) in chinese.items():
    cities[key]['zh_name'] = name
print(f'Chinese display names: {len(chinese)}')
currencies = {code: {'name': get_currency_name(code, locale='zh_CN'), 'digits': get_currency_precision(code)} for code in sorted(currency_codes)}
(ROOT / 'data/places.json').write_text(json.dumps({'countries': countries, 'cities': cities, 'currencies': currencies}, ensure_ascii=False, separators=(',', ':')))
with zipfile.ZipFile(sys.argv[1]) as archive:
    from io import BytesIO
    reader = shapefile.Reader(shp=BytesIO(archive.read('ne_110m_land.shp')), shx=BytesIO(archive.read('ne_110m_land.shx')), dbf=BytesIO(archive.read('ne_110m_land.dbf')))
    paths = []
    for shape in reader.shapes():
        stops = list(shape.parts) + [len(shape.points)]
        for start, end in zip(stops, stops[1:]):
            points = [(round((lon + 180) * 1000 / 360, 2), round((90 - lat) * 500 / 180, 2)) for lon, lat in shape.points[start:end]]
            paths.append('M' + 'L'.join(f'{x},{y}' for x, y in points) + 'Z')
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 500"><g fill="#d4d8cb" stroke="#bcc6b6" stroke-width="0.4">' + ''.join(f'<path d="{path}"/>' for path in paths) + '</g></svg>'
    (ROOT / 'static/world-land.svg').write_text(svg)
print(f'{len(countries)} countries/areas, {len(cities)} cities, {len(currencies)} currencies')
