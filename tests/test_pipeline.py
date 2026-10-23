"""Synthetic fixtures below are TEST DATA, never production source records."""
import json
from pathlib import Path
import pytest
from pydantic import ValidationError
from shorts.research import validate,ResearchError
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

def test_ffmpeg_integration(data,tmp_path):
    """Encode and probe an actual tiny TEST DATA film, no network/models needed."""
    import shutil
    import subprocess
    import wave
    import numpy as np
    from shorts.visuals import render
    if not shutil.which('ffmpeg'):pytest.skip('FFmpeg not installed')
    scenes=[{**s.model_dump(),'start':i*.4,'end':(i+1)*.4} for i,s in enumerate(fallback(data).scenes)]
    with wave.open(str(tmp_path/'narration.wav'),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(24000)
        w.writeframes((np.sin(np.arange(38400)*2*np.pi*220/24000)*1000).astype('<i2').tobytes())
    write([{'text':'TEST DATA','start':.1,'end':1.4}],tmp_path)
    render(scenes,data,tmp_path,music='None',preview=True)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-of','json',str(tmp_path/'video.mp4')]))
    v=next(s for s in probe['streams'] if s['codec_type']=='video')
    assert v['codec_name']=='h264' and (v['width'],v['height'])==(540,960)

def test_originality(data,tmp_path):
    from shorts.originality import audit,remember
    story=fallback(data)
    report,record=audit(story,'TEST DATA',tmp_path)
    assert not report['matches']
    remember(record,tmp_path)
    report,_=audit(story,'TEST DATA',tmp_path)
    assert report['matches'][0]['similarity']==1

def test_spoken_numeric_equivalence():
    from shorts.audio import numeric_tokens
    assert numeric_tokens('1,000,000.0 and 86.50 in 2024') == numeric_tokens('1 million and 86 .5 in 2024')
    assert numeric_tokens('86.5') != numeric_tokens('85.6')
    assert numeric_tokens('86.5 twice: 86.5') != numeric_tokens('86.5')
