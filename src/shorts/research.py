"""Conservative World Bank connector. No model-generated measurements."""
import csv
import hashlib
import io
import math
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

CATALOG = {
    'life expectancy': ('SP.DYN.LE00.IN', 'Life expectancy at birth', 'years', (0, 130), 'Expected years of life for a newborn under current mortality conditions; not a prediction for an individual.'),
    'gdp': ('NY.GDP.MKTP.CD', 'GDP', 'current US dollars', (0, 1e15), 'GDP at current US dollars. Exchange rates and inflation affect comparisons; this is not living standards.'),
    'fertility': ('SP.DYN.TFRT.IN', 'Fertility rate', 'births per woman', (0, 15), 'Total fertility rate under current age-specific fertility rates; not observed completed family size.'),
    'internet': ('IT.NET.USER.ZS', 'Individuals using the Internet', 'percent of population', (0, 100), 'Individuals who used the Internet from any location in the last three months.'),
    'population': ('SP.POP.TOTL', 'Population', 'people', (0, 2e10), 'Midyear population estimates; country and territory coverage follows the World Bank.'),
    'youngest': ('SP.POP.0014.TO.ZS', 'Population ages 0–14', 'percent of population', (0, 100), 'Share aged 0–14; this measures children, not median age.'),
}
class ResearchError(ValueError):
    pass

def resolve(brief):
    b = brief.lower()
    if any(x in b for x in ['sex', 'divorce', 'youngest', '50 years', 'changed', 'over time']):
        raise ResearchError('This request requires a comparable survey, median-age dataset, or time-series connector that is not implemented. No substitute ranking was generated. Try: Compare life expectancy across countries.')
    aliases = {'econom': 'gdp', 'birth rate': 'fertility'}
    keys = [k for k in CATALOG if k in b]
    keys += [v for k, v in aliases.items() if k in b]
    keys = set(keys)
    if len(keys) != 1:
        raise ResearchError('Choose one supported global metric: life expectancy, GDP, fertility, internet usage, or population. Geographic subsets and historical comparisons are not yet supported.')
    if any(x in b for x in ['africa', 'europe', 'asia', 'per capita', 'women', 'men', 'female', 'male', 'lowest', 'smallest']):
        raise ResearchError('This scope or metric variant is not supported by the current global highest-value connector. No topic substitution was made.')
    return CATALOG[keys.pop()]

def session():
    s = requests.Session()
    s.mount('https://', HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[429,500,502,503,504])))
    return s

def validate(rows, bounds):
    seen = set()
    for r in rows:
        key = (r['code'], r['year'])
        if key in seen or not math.isfinite(r['value']) or not bounds[0] <= r['value'] <= bounds[1]:
            raise ResearchError('Duplicate, nonfinite, or out-of-range source record')
        seen.add(key)
    if len(rows) < 5:
        raise ResearchError('Fewer than five comparable observations')
    return sorted(rows, key=lambda x: (-x['value'], x['name']))

def research(brief, out):
    code, title, unit, bounds, definition = resolve(brief)
    s = session()
    def get(url):
        r = s.get(url, timeout=(15,90)); r.raise_for_status(); return r
    countries = get('https://api.worldbank.org/v2/country?format=json&per_page=400').json()[1]
    names = {c['id']:c['name'] for c in countries if c['region']['id'] != 'NA'}
    year_now = datetime.now(timezone.utc).year
    url = f'https://api.worldbank.org/v2/country/all/indicator/{code}?format=json&per_page=20000&date={year_now-8}:{year_now}'
    response = get(url)
    (out/'source_response.json').write_text(response.text)
    payload = response.json()
    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        raise ResearchError('World Bank returned no usable records')
    records = [{'code':r['countryiso3code'], 'name':names[r['countryiso3code']], 'year':int(r['date']), 'value':float(r['value'])} for r in payload[1] if r['countryiso3code'] in names and r['value'] is not None]
    # A common year prevents false rankings caused by mixing vintages.
    years = sorted({r['year'] for r in records}, reverse=True)
    selected = next((y for y in years if sum(r['year']==y for r in records)>=100), None)
    if selected is None:
        raise ResearchError('No common year with at least 100 countries/territories')
    ranked = validate([r for r in records if r['year']==selected], bounds)
    with (out/'dataset.csv').open('w') as f:
        w=csv.DictWriter(f, fieldnames=['code','name','year','value']);w.writeheader();w.writerows(ranked)
    source = {'id':'WB', 'publisher':'World Bank', 'dataset':title, 'indicator':code, 'url':url, 'definition':definition, 'unit':unit, 'reference_year':selected, 'retrieved_at':datetime.now(timezone.utc).isoformat(), 'license':'CC BY 4.0, subject to indicator third-party exceptions; review linked metadata', 'metadata_url':f'https://data.worldbank.org/indicator/{code}', 'response_sha256':hashlib.sha256(response.content).hexdigest()}
    return {'brief':brief, 'metric':title, 'unit':unit, 'year':selected, 'definition':definition, 'coverage':len(ranked), 'rows':ranked[:5], 'source':source, 'limitation':'Ranking includes reporting countries and territories, excludes aggregates and missing values, and uses a single common year. Estimates can be revised.'}
