"""Offline reference data and validation shared by forms and journeys."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import urlsplit

REFERENCE = json.loads((Path(__file__).parent / 'data/places.json').read_text())
COUNTRIES = REFERENCE['countries']
CITIES = REFERENCE['cities']
CURRENCIES = REFERENCE['currencies']
CATEGORIES = ('织物', '陶瓷', '金属器', '木器', '玻璃器', '珠宝首饰', '书画纸品', '雕塑摆件', '服饰', '日用器物', '自然物', '其他')
CONDITIONS = ('完好', '良好', '有使用痕迹', '有损伤', '待修复', '待检查')
PRECISIONS = {'exact': '%Y-%m-%d', 'month': '%Y-%m', 'year': '%Y', 'unknown': None}
STATUSES = ('confirmed', 'seller', 'guess', 'unknown')


def city_label(city):
    primary = city['name']
    name = f"{city['zh_name']} · {primary}" if city.get('zh_name') else primary
    return f"{name}（{city['region']}）" if city['region'] and city['region'] != primary else name


def search_key(value):
    return ''.join(char for char in unicodedata.normalize('NFKD', value.casefold()) if char.isalnum())


def find_cities(country, query='', selected=''):
    query = search_key(query.strip()[:80])
    matches = [dict(id=key, label=city_label(city), population=city['population'])
               for key, city in CITIES.items() if city['country'] == country
               and (not query or query in search_key(city['name']) or query in search_key(city.get('zh_name', '')) or any(query in search_key(alias) for alias in city['aliases']))]
    matches.sort(key=lambda city: (-city['population'], city['label']))
    result = matches[:100]
    if selected in CITIES and CITIES[selected]['country'] == country and not any(city['id'] == selected for city in result):
        result.insert(0, dict(id=selected, label=city_label(CITIES[selected]), population=CITIES[selected]['population']))
    return result, len(matches)


def validate_object(form):
    fields = ('name', 'category', 'acquired_date', 'date_precision', 'source', 'story', 'material', 'technique',
              'maker', 'culture_region', 'condition', 'knowledge_status', 'image_url',
              'country_code', 'place_id', 'price_amount', 'currency_code')
    data = {field: form.get(field, '').strip() for field in fields}
    if any(field in form for field in ('date_year', 'date_month', 'date_day')):
        year, month, day = (form.get(field, '').strip() for field in ('date_year', 'date_month', 'date_day'))
        if (month or day) and not year:
            raise ValueError('填写月份或日期前，请先填写年份。')
        if day and not month:
            raise ValueError('填写日期前，请先选择月份。')
        if year and not re.fullmatch(r'[0-9]{4}', year):
            raise ValueError('年份请填写四位数字。')
        if (month and not re.fullmatch(r'(?:0?[1-9]|1[0-2])', month)) or (day and not re.fullmatch(r'(?:0?[1-9]|[12][0-9]|3[01])', day)):
            raise ValueError('请选择有效的月份和日期。')
        data['acquired_date'] = year + (f'-{int(month):02d}' if month else '') + (f'-{int(day):02d}' if day else '')
        data['date_precision'] = 'exact' if day else 'month' if month else 'year' if year else 'unknown'
    data['date_precision'] = data['date_precision'] or 'unknown'
    data['knowledge_status'] = data['knowledge_status'] or 'unknown'
    if not data['name'] or not data['category']:
        raise ValueError('请填写藏品名称和类别。')
    if data['category'] not in CATEGORIES:
        raise ValueError('请从列表中选择藏品类别。')
    if data['condition'] and data['condition'] not in CONDITIONS:
        raise ValueError('请从列表中选择保存状况。')
    if data['knowledge_status'] not in STATUSES or data['date_precision'] not in PRECISIONS:
        raise ValueError('请选择有效的日期精度和知识状态。')
    country, place = data['country_code'], data['place_id']
    if country and country not in COUNTRIES:
        raise ValueError('请从列表中选择国家或地区。')
    if place and (place not in CITIES or CITIES[place]['country'] != country):
        raise ValueError('请选择属于当前国家或地区的城市。')
    if form.get('country') or form.get('place'):
        raise ValueError('请使用国家和城市选择框填写地点。')
    data['country'] = COUNTRIES[country]['name'] if country else ''
    data['place'] = city_label(CITIES[place]) if place else ''
    value, precision = data['acquired_date'], data['date_precision']
    patterns = {'exact': r'\d{4}-\d{2}-\d{2}', 'month': r'\d{4}-\d{2}', 'year': r'\d{4}'}
    if precision == 'unknown' and value:
        raise ValueError('日期不详时请清空日期，或选择对应的日期精度。')
    if precision != 'unknown':
        if not re.fullmatch(patterns[precision], value):
            raise ValueError('请按所选精度填写完整日期，记不清时可选择“不清楚”。')
        try:
            parsed = datetime.strptime(value, PRECISIONS[precision]).date()
        except ValueError as error:
            raise ValueError('日期不存在，请检查年、月、日。') from error
        if parsed > date.today():
            raise ValueError('入藏日期不能晚于今天。')
    amount, currency = data['price_amount'], data['currency_code']
    if currency and currency not in CURRENCIES:
        raise ValueError('请从列表中选择币种。')
    if bool(amount) != bool(currency):
        raise ValueError('请同时填写金额并选择币种；价格不详时两项都留空。')
    if form.get('price'):
        raise ValueError('请分别填写金额和币种。')
    if amount:
        if not re.fullmatch(r'\d{1,12}(?:\.\d{1,4})?', amount):
            raise ValueError('金额只能填写非负数字，最多 12 位整数、4 位小数。')
        try:
            number = Decimal(amount)
            digits = CURRENCIES[currency]['digits']
            if number != number.quantize(Decimal(1).scaleb(-digits)):
                raise ValueError(f'{currency} 最多支持 {digits} 位小数。')
        except InvalidOperation as error:
            raise ValueError('请输入有效金额。') from error
        data['price_amount'] = format(number, f'.{digits}f')
    data['price'] = f"{data['price_amount']} {currency}" if amount else ''
    image_url = data['image_url']
    if image_url:
        try:
            url = urlsplit(image_url)
            if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
                raise ValueError
        except ValueError as error:
            raise ValueError('图片链接必须是有效的 http 或 https 网址。') from error
    for field, value in data.items():
        limit = 10000 if field == 'story' else 2000 if field == 'image_url' else 200
        if len(value) > limit:
            raise ValueError(f'内容过长，请缩短后重试（每项最多 {limit} 字符）。')
    return data
