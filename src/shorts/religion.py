"""Global religious affiliation counts: Pew's comparable 2010/2020 benchmarks."""
import csv
import hashlib
import io
import json
import math
import re
from datetime import datetime, timezone
from .research import ResearchError,session

REPORT='https://www.pewresearch.org/religion/2025/06/09/how-the-global-religious-landscape-changed-from-2010-to-2020/'
DATASET='https://www.pewresearch.org/dataset/dataset-of-global-religious-composition-estimates-for-2010-and-2020/'
CHART='https://ourworldindata.org/grapher/religious-composition'
GROUPS={
    'CHR':('christians','Christianity','christian'),
    'MUS':('muslims','Islam','muslim'),
    'HIN':('hindus','Hinduism','hindu'),
    'BUD':('buddhists','Buddhism','buddhist'),
    'JEW':('jews','Judaism','jews'),
    'OTH':('other_religions','Other religions','other religions'),
    'UNA':('religiously_unaffiliated','Unaffiliated','not religious'),
}
METRIC=('PEW.RELIGION','Religion','people',(0,1e10),'Estimated global religious affiliation, classified by self-identification; unaffiliated is a separate non-religious category.')


def is_topic(brief):
    return bool(re.search(r'\b(religion|religions|religious|christianity|islam|hinduism|buddhism|judaism)\b',brief.lower()))


def validate_brief(brief,mode='Race'):
    if mode!='Race':raise ResearchError('Religion currently supports the global Race format. Choose Race or use the brief "Religion race".')
    b=brief.lower()
    if any(x in b for x in ['country','countries','india','china','united states','europe','africa','asia','region','fertility','birth','life expectancy','gdp','sex','per capita','percentage','growth rate']):
        raise ResearchError('Religion race currently compares global affiliation counts, not country, birth-rate, practice, or percentage rankings.')
    years=[int(x) for x in re.findall(r'\b(?:18|19|20)\d{2}\b',brief)]
    if years and sorted(set(years))!=[2010,2020]:
        raise ResearchError('The comparable religion benchmarks are 2010 and 2020 only. Older history, later years and forecasts are not available in this adapter.')
    period=re.search(r'(?:last|past)\s+(\d+)\s+years',b)
    if period:raise ResearchError('Use the explicit benchmark period 2010 to 2020; this is not a present-day annual series.')


def parse_world(text,expected_keyword):
    reader=csv.DictReader(io.StringIO(text))
    columns=[c for c in (reader.fieldnames or []) if c not in ['Entity','Code','Year']]
    if len(columns)!=1 or not columns[0].startswith('Number of people') or expected_keyword not in columns[0].lower():
        raise ResearchError('Religion API returned an unexpected metric or group; refusing a substitute series')
    values={}
    for row in reader:
        if row.get('Entity')!='World':continue
        year=int(row['Year'])
        if year not in [2010,2020]:raise ResearchError('Unexpected religion benchmark year')
        value=float(row[columns[0]])
        if year in values or not math.isfinite(value) or not 0<value<4e9:raise ResearchError('Invalid or duplicate global religious affiliation estimate')
        values[year]=value
    if set(values)!={2010,2020}:raise ResearchError('Missing global religion benchmark; annual values will not be invented')
    return values


def retrieve(brief,out,mode='Race'):
    validate_brief(brief,mode)
    s=session();s.headers['User-Agent']='Our World In Data data fetch/1.0'
    tables={2010:{},2020:{}};raw={};series=[]
    for code,(slug,name,keyword) in GROUPS.items():
        url=f'{CHART}.csv?v=1&csvType=full&useColumnShortNames=false&indicator=count_unrounded&religion={slug}'
        r=s.get(url,timeout=(15,90));r.raise_for_status()
        values=parse_world(r.text,keyword);raw[code]=r.text
        for year,value in values.items():tables[year][code]=value
        series.append({'code':code,'group':name,'url':url,'response_sha256':hashlib.sha256(r.content).hexdigest()})
    for year,table in tables.items():
        if set(table)!=set(GROUPS) or not 6e9<sum(table.values())<9e9:
            raise ResearchError('Global category coverage or sum is inconsistent')
    payload=json.dumps(raw,ensure_ascii=False)
    (out/'source_response.json').write_text(payload)
    places={c:{'name':g[1],'iso2':''} for c,g in GROUPS.items()}
    rows=[{'code':c,'name':places[c]['name'],'year':year,'value':v} for year,t in tables.items() for c,v in t.items()]
    with (out/'dataset.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=['code','name','year','value']);w.writeheader();w.writerows(rows)
    source={'id':'PEW_OWID','publisher':'Pew Research Center; processed by Our World in Data','dataset':'Global Religious Composition Estimates for 2010 and 2020','url':CHART,'metadata_url':DATASET,'report_url':REPORT,'source_years':[2010,2020],'publication_year':2025,'unit':'people','definition':METRIC[-1], 'retrieved_at':datetime.now(timezone.utc).isoformat(),'response_sha256':hashlib.sha256(payload.encode()).hexdigest(),'series':series,'license':'Pew Research Center terms apply to original data; OWID processing CC BY. Include publisher attribution and source link.','terms_url':'https://www.pewresearch.org/about/terms-and-conditions/','attribution':'Pew Research Center (2025), Global Religious Composition Estimates for 2010 and 2020; processed by Our World in Data. Independent animation; not endorsed by the source publishers.','reference_year':2020,'precision_note':'Original unrounded estimates are preserved in the CSV. Video labels round to million/tenth-million notation; these are estimates, not exact counts.'}
    top=sorted(tables[2020],key=lambda c:(-tables[2020][c],c))
    return {'brief':brief,'metric':'Religion','unit':'people','entity_kind':'religious affiliation group','definition':METRIC[-1],'year':2020,'start_year':2010,'years':[2010,2020],'tables':{str(y):t for y,t in tables.items()},'places':places,'pair':top[:2],'coverage':7,'rows':[{'code':c,'name':places[c]['name'],'year':2020,'value':tables[2020][c]} for c in top],'leader_changes':[{'year':2010,'code':max(tables[2010],key=tables[2010].get),'tied':False}],'source':source,'limitation':'Only the 2010 and 2020 Pew/OWID benchmark estimates are observed in this dataset. Intermediate animated years are linear interpolation, not independent annual measurements. No extrapolation or forecast. Affiliation reflects self-identification, not belief or practice. Unaffiliated is a separate category, not a religion; Other religions combines multiple smaller traditions.'}
