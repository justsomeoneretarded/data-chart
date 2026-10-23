import json
from types import SimpleNamespace
import pytest
from shorts.general import Comparison, retrieve, resolve
from shorts.dynamic import Film
from shorts.history import snapshot

PLAN={'title':'Trophies','unit':'trophies','years':[2000,2010,2020], 'entries':[{'name':'Barcelona','values':[50,65,90]},{'name':'Real Madrid','values':[60,72,95]}],'cumulative':True}

def test_reject_invalid_generated_data():
    for update in [{'years':[2020,2000,2010]},{'entries':[{'name':'A','values':[1,float('nan'),4]},{'name':'B','values':[2,3,4]}]},{'entries':[{'name':'A','values':[5,4,6]},{'name':'B','values':[2,3,4]}]}]:
        with pytest.raises(ValueError):Comparison.model_validate({**PLAN,**update})

def test_general_plan_to_clean_render(tmp_path,monkeypatch):
    monkeypatch.setattr('shorts.general.context',lambda b:[])
    monkeypatch.setattr('shorts.general.requests.post',lambda *a,**kw:SimpleNamespace(raise_for_status=lambda:None,json=lambda:{'response':json.dumps(PLAN)}))
    data=retrieve('Barcelona vs Real Madrid trophies',tmp_path,'Versus')
    assert data['data_kind']=='simulation'
    assert data['places']['E1']['iso2']==''
    assert snapshot(data,2005)[0]['E1']==57
    assert snapshot(data,2010)[0]['E1']==65
    assert Film(data,'Versus',{}).frame(12,30,True).size==(540,960)
    assert (tmp_path/'dataset.csv').exists()

def test_source_failure_routes_to_general(tmp_path,monkeypatch):
    def unavailable(*a,**k):raise ValueError('Unsupported metric')
    monkeypatch.setattr('shorts.discovery.retrieve',unavailable)
    monkeypatch.setattr('shorts.general.retrieve',lambda *a,**kw:kw)
    assert resolve('ants vs mosquitoes',tmp_path,'Versus')['reason']=='Unsupported metric'
