import json
import pytest
from shorts.web_research import WebPlan,Findings,Fact,validate_facts,assemble,number,public_url
from shorts.dynamic import Film

@pytest.fixture
def evidence():
    return [dict(id='W1',url='https://source.example/a',title='A records',text='League - 29 Cup - 32',sha256='a',retrieved_at='2026-10-23'),dict(id='W2',url='https://source.example/b',title='B records',text='36 Leagues 20 Cups',sha256='b',retrieved_at='2026-10-23')]

@pytest.fixture
def findings():
    facts=[Fact(subject=s,category=c,year=None,value_text=v,source_id=i,quote=q) for s,c,v,i,q in [('A','League','29','W1','League - 29'),('B','League','36','W2','36 Leagues'),('A','Cup','32','W1','Cup - 32'),('B','Cup','20','W2','20 Cups')]]
    return Findings(title='Selected trophies',unit='trophies',layout='categories',scope='Comparable named competitions only',limitations='Snapshots may have different update dates.',facts=facts,icon='trophy')

def plan():return WebPlan(queries=['A B records'],subjects=['A','B'],focus_terms=['records'],scope='Comparable records')

def test_source_quotes_and_categories_are_not_historical_measurements(tmp_path,evidence,findings):
    d=assemble('A vs B trophies',tmp_path,'Versus',plan(),findings,evidence)
    assert d['data_kind']=='source observations'
    assert d['category_frames'][0]['values']=={'W1':29,'W2':36}
    assert d['category_frames'][0]['year'] is None
    assert json.loads((tmp_path/'web_evidence.json').read_text())[0]['quote']=='League - 29'
    film=Film(d,'Versus',{})
    assert film.frame(10,30,True).tobytes()!=film.frame(20,30,True).tobytes()

@pytest.mark.parametrize('changes',[{'value_text':'99'},{'quote':'Invented League - 29'},{'source_id':'W99'},{'subject':'C'},{'year':2020}])
def test_invented_claims_are_rejected(evidence,findings,changes):
    findings.facts[0]=findings.facts[0].model_copy(update=changes)
    with pytest.raises(ValueError):validate_facts(findings,evidence,['A','B'])

def test_missing_categories_do_not_become_zero(tmp_path,evidence,findings):
    findings.facts.pop()
    with pytest.raises(ValueError,match='two comparable'):
        assemble('A vs B',tmp_path,'Versus',plan(),findings,evidence)

def test_snapshot_cannot_answer_historical_cutoff(tmp_path,evidence,findings):
    with pytest.raises(ValueError,match='historical cutoff'):
        assemble('A vs B trophies through 2025',tmp_path,'Versus',plan(),findings,evidence)

def test_literal_numeric_scaling():
    assert number('2.5 million')==2500000
    assert number('1,234')==1234
    with pytest.raises(ValueError):number('about a billion')

def test_private_urls_are_rejected():
    with pytest.raises(ValueError):public_url('http://127.0.0.1/secret')

def test_web_is_tried_before_simulation(tmp_path,monkeypatch):
    from shorts.general import resolve
    def missing(*a,**k):raise ValueError('not in catalog')
    monkeypatch.setattr('shorts.general.choose_source',lambda *a:'country_statistics')
    monkeypatch.setattr('shorts.discovery.retrieve',missing)
    monkeypatch.setattr('shorts.web_research.retrieve',lambda *a,**k:{'data_kind':'source observations'})
    def no_simulation(*a,**k):pytest.fail('simulation must not run')
    monkeypatch.setattr('shorts.general.retrieve',no_simulation)
    assert resolve('A vs B trophies',tmp_path,'Versus')['data_kind']=='source observations'

def test_complete_web_reader_searches_fetches_and_extracts(tmp_path,evidence,findings,monkeypatch):
    from types import SimpleNamespace
    from shorts import web_research as web
    p=plan().model_copy(update={'candidate_urls':[r['url'] for r in evidence]})
    answers=iter([p,SimpleNamespace(source_ids=['W1','W2']),findings])
    monkeypatch.setattr(web,'model',lambda *a,**k:next(answers))
    queries=[]
    def search(q):queries.append(q);return []
    monkeypatch.setattr(web,'search',search)
    def fetch(url,out,index,terms):
        r=next(r for r in evidence if r['url']==url)
        return {**r,'excerpt':r['text'],'links':[]}
    monkeypatch.setattr(web,'fetch',fetch)
    data=web.retrieve('A vs B trophies',tmp_path,'Versus')
    assert queries==p.queries
    assert data['source']['id']=='WEB'
    assert len(json.loads((tmp_path/'web_evidence.json').read_text()))==4

def test_matching_duplicates_are_corroboration_not_extra_categories(evidence,findings):
    findings.facts.append(findings.facts[0])
    assert len(validate_facts(findings,evidence,['A','B']))==4

def test_conflicting_source_numbers_are_not_silently_chosen(evidence,findings):
    evidence[1]['text']+=' League - 30'
    findings.facts.append(findings.facts[0].model_copy(update={'value_text':'30','source_id':'W2','quote':'League - 30'}))
    with pytest.raises(ValueError,match='Conflicting'):
        validate_facts(findings,evidence,['A','B'])


def test_organizations_cannot_be_replaced_with_country_data(tmp_path,monkeypatch):
    from shorts.general import resolve
    monkeypatch.setattr('shorts.general.choose_source',lambda *a:'other_entities')
    def no_country_substitution(*a,**k):pytest.fail('Non-country entities must not query the country catalog')
    monkeypatch.setattr('shorts.discovery.retrieve',no_country_substitution)
    monkeypatch.setattr('shorts.web_research.retrieve',lambda *a,**k:{'source':{'id':'WEB'}})
    assert resolve('Team A vs Team B trophies',tmp_path,'Versus')['source']['id']=='WEB'
