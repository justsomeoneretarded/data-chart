"""Synthetic TEST DATA only; live religion estimates are fetched during real runs."""
import pytest
from shorts.religion import parse_world,validate_brief,is_topic
from shorts.history import snapshot,metric_for
from shorts.research import ResearchError

CSV='Entity,Code,Year,Number of people who are Christians\nWorld,OWID_WRL,2010,1000000\nWorld,OWID_WRL,2020,1200000\nCountry X,XXX,2020,100\n'

def test_global_only():
    assert parse_world(CSV,'christian')=={2010:1000000,2020:1200000}

def test_wrong_religion_not_substituted():
    with pytest.raises(ResearchError):parse_world(CSV,'muslim')

def test_missing_benchmark_not_invented():
    with pytest.raises(ResearchError):parse_world(CSV.replace('World,OWID_WRL,2010,1000000\n',''),'christian')

def test_percentages_cannot_be_used_as_counts():
    with pytest.raises(ResearchError):parse_world(CSV.replace('Number of people who are Christians','Share of population who are Christians'),'christian')

@pytest.mark.parametrize('brief',['Religion race 1900 to 2020','Religion race 2010 to 2050','Religion race last 50 years','religion race in India','religion by percentage','religion fertility rates'])
def test_unsupported_religion_scope(brief):
    with pytest.raises(ResearchError):validate_brief(brief)

def test_two_benchmarks_do_not_become_fake_observed_years():
    data={'start_year':2010,'year':2020,'tables':{'2010':{'TEST_A':100},'2020':{'TEST_A':200}}}
    values,lo,hi,f=snapshot(data,2015)
    assert (lo,hi,f)==(2010,2020,.5) and values['TEST_A']==150
    assert list(data['tables'])==['2010','2020']

def test_religion_brief_dispatch():
    assert is_topic('Religion race')
    assert metric_for('Religion race')[1]=='Religion'
    validate_brief('Religion race from 2010 to 2020')
    with pytest.raises(ResearchError):validate_brief('Religion race',mode='Versus')
