"""Source benchmark observations for races; interpolation is explicitly visual only."""
import csv
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from .research import CATALOG, ResearchError, session


def metric_for(brief):
    from .religion import is_topic,validate_brief,METRIC
    if is_topic(brief):
        validate_brief(brief)
        return METRIC
    b=brief.lower()
    if any(s in b for s in ['sex','divorce','youngest','per capita','density','growth rate','women','female','male']):
        raise ResearchError('This metric requires a different verified data adapter; no substitute comparison was generated.')
    matches={k for k in CATALOG if k!='youngest' and k in b}
    if 'econom' in b:matches.add('gdp')
    if 'birth rate' in b:matches.add('fertility')
    if len(matches)!=1:raise ResearchError('Choose one supported metric: population, GDP, life expectancy, fertility, or internet usage. Sports awards and survey comparisons need additional verified adapters.')
    return CATALOG[matches.pop()]


def retrieve(brief,out,mode='Race'):
    from .religion import is_topic,retrieve as religion_data
    if is_topic(brief):return religion_data(brief,out,mode)
    indicator,title,unit,bounds,definition=metric_for(brief)
    s=session()
    def get(url):
        r=s.get(url,timeout=(15,90));r.raise_for_status();return r
    countries=get('https://api.worldbank.org/v2/country?format=json&per_page=400').json()[1]
    places={c['id']:{'name':c['name'],'iso2':c['iso2Code']} for c in countries if c['region']['id']!='NA'}
    # Explicit named-country comparisons are supported; no silent geographic replacement.
    requested=[code for code,c in places.items() if re.search(r'\b'+re.escape(c['name'].lower())+r'\b',brief.lower())]
    aliases={'usa':'USA','united states':'USA','south korea':'KOR','russia':'RUS','uk':'GBR','china':'CHN','india':'IND'}
    for name,code in aliases.items():
        if re.search(r'\b'+re.escape(name)+r'\b',brief.lower()) and code not in requested:requested.append(code)
    def position(code):
        labels=[places[code]['name'].lower()]+[name for name,c in aliases.items() if c==code]
        return min((m.start() for label in labels for m in re.finditer(r'\b'+re.escape(label)+r'\b',brief.lower())),default=10000)
    requested.sort(key=position)
    if any(x in brief.lower() for x in ['europe','asia','africa','regional']) and not requested:
        raise ResearchError('Regional subsets are not implemented. Specify two countries, or a global comparison.')
    if requested and len(requested)!=2:
        raise ResearchError('Named-country comparisons currently require exactly two countries.')
    now=datetime.now(timezone.utc).year
    url=f'https://api.worldbank.org/v2/country/all/indicator/{indicator}?format=json&per_page=20000&date=1960:{now}'
    response=get(url);payload=response.json()
    if not isinstance(payload,list) or len(payload)<2 or not payload[1]:raise ResearchError('No annual source observations returned')
    pages=[payload]
    count=int(payload[0].get('pages',1))
    if count>5:raise ResearchError('Source pagination exceeds the bounded connector limit')
    for page in range(2,count+1):pages.append(get(url+f'&page={page}').json())
    raw=json.dumps(pages,ensure_ascii=False);(out/'source_response.json').write_text(raw)
    tables={};seen=set()
    for page in pages:
        for r in page[1]:
            code=r['countryiso3code'];value=r['value']
            if code not in places or value is None:continue
            if requested and code not in requested:continue
            year=int(r['date']);value=float(value);key=(code,year)
            if key in seen or not math.isfinite(value) or not bounds[0]<=value<=bounds[1]:raise ResearchError('Invalid or duplicate annual observation')
            seen.add(key)
            tables.setdefault(year,{})[code]=value
    minimum=2 if requested else 100
    years=sorted(y for y,t in tables.items() if len(t)>=minimum)
    if len(years)<2:raise ResearchError('Insufficient comparable annual coverage')
    explicit=[int(y) for y in re.findall(r'\b(?:19|20)\d{2}\b',brief)]
    start,end=(min(explicit),max(explicit)) if len(explicit)>=2 else (years[0],years[-1])
    if len(explicit)==1:
        if re.search(r'(?:since|from)\s+'+str(explicit[0]),brief.lower()):start=explicit[0]
        else:raise ResearchError('A music-first timeline needs a year range. Specify two years, omit the year for full history, or choose Explainer for a snapshot.')
    period=re.search(r'(?:last|past)\s+(\d+)\s+years',brief.lower())
    if period:start=end-int(period.group(1))
    if start<years[0] or end>years[-1] or start>=end:raise ResearchError(f'Requested period unavailable. Source coverage: {years[0]}–{years[-1]}.')
    selected=[y for y in years if start<=y<=end]
    if selected!=list(range(start,end+1)):raise ResearchError('Missing annual coverage within requested period; refusing to bridge the gap')
    latest=tables[end]
    pair=requested or sorted(latest,key=lambda c:-latest[c])[:2]
    if mode=='Versus':
        # Both entries must be observed in every displayed year; gaps are never zero.
        selected=[y for y in selected if all(c in tables[y] for c in pair)]
        if len(selected)<2 or selected!=list(range(selected[0],selected[-1]+1)):raise ResearchError('Selected pair lacks continuous comparable observations')
        if (explicit or period) and (selected[0]!=start or selected[-1]!=end):raise ResearchError('Selected countries lack the requested period')
        start,end=selected[0],selected[-1]
        tables={y:{c:tables[y][c] for c in pair} for y in selected}
    else:tables={y:tables[y] for y in selected}
    rows=[]
    for y,t in tables.items():
        rows += [{'code':c,'name':places[c]['name'],'iso2':places[c]['iso2'],'year':y,'value':v} for c,v in sorted(t.items())]
    with (out/'dataset.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=['code','name','iso2','year','value']);w.writeheader();w.writerows(rows)
    latest=tables[end];top=sorted(latest,key=lambda c:(-latest[c],c))
    leaders=[{'year':y,'code':sorted(tables[y],key=lambda c:(-tables[y][c],c))[0], 'tied':sum(math.isclose(v,max(tables[y].values()),rel_tol=0,abs_tol=1e-9) for v in tables[y].values())>1} for y in tables]
    changes=[r for i,r in enumerate(leaders) if i==0 or r['code']!=leaders[i-1]['code']]
    source={'id':'WB','publisher':'World Bank','dataset':title,'indicator':indicator,'url':url,'metadata_url':f'https://data.worldbank.org/indicator/{indicator}','definition':definition,'unit':unit,'reference_year':end,'start_year':start,'retrieved_at':datetime.now(timezone.utc).isoformat(),'license':'World Bank CC BY 4.0, subject to indicator metadata exceptions','response_sha256':hashlib.sha256(raw.encode()).hexdigest()}
    return {'brief':brief,'metric':title,'unit':unit,'definition':definition,'year':end,'start_year':start,'years':selected,'tables':{str(y):t for y,t in tables.items()},'places':places,'pair':pair,'coverage':len(latest),'rows':[{'code':c,'name':places[c]['name'],'year':end,'value':latest[c]} for c in top[:5]],'leader_changes':changes,'source':source,'limitation':'Annual World Bank observations; intermediate animation values are linearly interpolated between adjacent observed years. Missing observations are excluded, never zero. Coverage follows reporting countries and territories. Estimates can be revised.'}


def snapshot(data,year):
    anchors=sorted(int(y) for y in data['tables'])
    year=max(anchors[0],min(anchors[-1],year))
    lo=max(y for y in anchors if y<=year)
    hi=min(y for y in anchors if y>=year)
    a=data['tables'][str(lo)];b=data['tables'][str(hi)]
    fraction=(year-lo)/(hi-lo) if hi!=lo else 0
    values={c:a[c]+(b[c]-a[c])*fraction for c in a.keys() & b.keys()}
    return values,lo,hi,fraction
