import copy
import pytest
from shorts.discovery import Selection, candidates, assemble, validate_selection
from shorts.story import facts, fallback

CATALOG={
    'MALE':{'id':'MALE','name':'Population, male','unit':'people'},
    'FEMALE':{'id':'FEMALE','name':'Population, female','unit':'people'},
    'OTHER':{'id':'OTHER','name':'Unemployment, total','unit':'percent'},
}
COUNTRIES={'USA':{'name':'United States','iso2Code':'US'}}
PLAN=dict(indicator_ids=['MALE','FEMALE'],country_ids=['USA'],global_countries=False,title='USA population',unit='people',comparable=True,explanation='Comparable source counts')

def records():
    return [{'indicator':{'id':i},'countryiso3code':'USA','date':str(y),'value':v}
            for i,values in [('MALE',[10,11,12]),('FEMALE',[12,13,14])]
            for y,v in zip([2000,2001,2002],values)]

def test_metadata_discovery_not_fixed_topic_list():
    rows=list(CATALOG.values())+[{'id':'X','name':'Unrelated metric'}]
    found=candidates(rows,['population','male','female'],limit=2)
    assert {r['id'] for r in found}=={'MALE','FEMALE'}
    assert candidates(rows,['unemployment'],limit=1)[0]['id']=='OTHER'

def test_real_demographic_series_preserve_values_and_scope(tmp_path):
    d=assemble('Male vs female population USA 2000–2025',tmp_path,'Race',Selection(**PLAN),CATALOG,COUNTRIES,records())
    assert d['data_kind']=='source observations'
    assert d['tables']['2000']=={'S1':10,'S2':12}
    assert d['year']==2002
    assert d['places']['S1']['name']=='Male'
    assert len(d['source']['series'])==2
    assert (tmp_path/'dataset.csv').exists()
    assert facts(d)['G']
    assert fallback(d)

@pytest.mark.parametrize('update',[
    {'indicator_ids':['INVENTED']},
    {'country_ids':['INVENTED']},
    {'indicator_ids':['MALE','OTHER']},
    {'indicator_ids':['MALE','MALE']},
    {'indicator_ids':['MALE'],'global_countries':True},
])
def test_reject_unknown_or_incomparable_selection(update):
    with pytest.raises(ValueError):
        validate_selection(Selection(**{**PLAN,**update}),CATALOG,COUNTRIES,'Versus')

def test_missing_values_are_not_zero_or_fabricated(tmp_path):
    r=records()
    r[1]['value']=None
    with pytest.raises(ValueError,match='continuous'):
        assemble('population',tmp_path,'Race',Selection(**PLAN),CATALOG,COUNTRIES,r)

def test_duplicates_and_nonfinite_records_rejected(tmp_path):
    for extra in [records()[0],{**records()[0],'value':float('nan')}]:
        with pytest.raises(ValueError):
            assemble('population',tmp_path,'Race',Selection(**PLAN),CATALOG,COUNTRIES,records()+[extra])

def test_complete_discovery_uses_metadata_not_model_values(tmp_path,monkeypatch):
    from shorts import discovery
    answers=iter([discovery.Search(terms=['population','male','female']),Selection(**PLAN)])
    monkeypatch.setattr(discovery,'model',lambda *a:next(answers))
    def pages(s,path,params):
        if path=='/indicator':return list(CATALOG.values())
        if path=='/country':return [dict(id='USA',region={'id':'NAC'},**COUNTRIES['USA'])]
        return [r for r in records() if r['indicator']['id']==path.rsplit('/',1)[-1]]
    monkeypatch.setattr(discovery,'pages',pages)
    d=discovery.retrieve('Male vs female population USA',tmp_path,'Race')
    assert d['tables']['2002']=={'S1':12,'S2':14}
    assert (tmp_path/'discovery_selection.json').exists()

def test_semantic_selection_is_corrected_before_fallback(tmp_path,monkeypatch):
    from shorts import discovery
    invalid=Selection(**{**PLAN,'indicator_ids':['MALE','FEMALE'],'country_ids':['USA','CHN']})
    countries={**COUNTRIES,'CHN':{'name':'China','iso2Code':'CN'}}
    answers=iter([invalid,discovery.SingleIndicator(indicator_id='MALE',explanation='One shared definition')]);schemas=[]
    def model(schema,prompt):
        schemas.append(schema);return next(answers)
    monkeypatch.setattr(discovery,'model',model)
    result=discovery.select_validated('brief',CATALOG,countries,'Versus',tmp_path)
    assert result.indicator_ids==['MALE']
    assert result.country_ids==['USA','CHN']
    assert schemas==[Selection,discovery.SingleIndicator]
    import json
    attempts=json.loads((tmp_path/'discovery_attempts.json').read_text())
    assert len(attempts)==1 and 'error' not in attempts[0]
