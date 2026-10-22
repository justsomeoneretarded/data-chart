"""Synthetic fixtures below are TEST DATA, never production source records."""
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from shorts.research import resolve,validate,ResearchError
from shorts.story import Story, fallback,validate_story
from shorts.captions import write,stamp
from shorts.visuals import frame
from shorts.publishing import metadata

@pytest.fixture
def data():
    return {'metric':'TEST DATA','unit':'years','year':2020,'coverage':5,'definition':'TEST DATA measurement definition.','limitation':'TEST DATA not publishable.','rows':[{'code':str(i),'name':f'Test country {i}','year':2020,'value':float(90-i)} for i in range(5)],'source':{'metadata_url':'https://example.invalid/TEST'}}

def test_ranking(data):
    assert validate(list(reversed(data['rows'])),(0,130))==data['rows']
@pytest.mark.parametrize('value',[float('nan'),float('inf'),-1,131])
def test_invalid_values(data,value):
    data['rows'][0]['value']=value
    with pytest.raises(ResearchError):validate(data['rows'],(0,130))
def test_duplicate(data):
    data['rows'].append(data['rows'][0])
    with pytest.raises(ResearchError):validate(data['rows'],(0,130))
@pytest.mark.parametrize('brief',['Compare how often people have sex in different countries','youngest populations','GDP over time','compare divorce rates','life expectancy per capita','life expectancy in Africa','lowest population'])
def test_no_silent_substitution(brief):
    with pytest.raises(ResearchError):resolve(brief)
def test_metric():assert resolve('highest life expectancy')[0]=='SP.DYN.LE00.IN'
def test_story(data):
    story=fallback(data);assert validate_story(Story.model_validate_json(story.model_dump_json()),data)
    story.scenes[0].claim_ids=['invented']
    with pytest.raises(ValueError):validate_story(story,data)
def test_bad_model():
    with pytest.raises(ValidationError):Story.model_validate({'title':'Invalid','scenes':[]})
def test_captions(tmp_path):
    write([{'text':'Hello','start':0.1,'end':.5},{'text':'world','start':.5,'end':1}],tmp_path)
    assert '00:00:00,100 --> 00:00:01,000' in (tmp_path/'subtitles.srt').read_text()
    assert (tmp_path/'subtitles.vtt').read_text().startswith('WEBVTT')
    assert '\\kf' in (tmp_path/'subtitles.ass').read_text()
    assert stamp(59.9999)=='00:01:00,000'
def test_renderer(data):
    scenes=[{**s.model_dump(),'start':i*10,'end':(i+1)*10} for i,s in enumerate(fallback(data).scenes)]
    a=frame(11,scenes,data);b=frame(13,scenes,data)
    assert a.size==(1080,1920) and a.tobytes()!=b.tobytes()
def test_metadata(data,tmp_path):
    result=metadata(fallback(data),data,tmp_path)
    assert result['privacyStatus']=='private'
    assert 'https://example.invalid/TEST' in result['description']
