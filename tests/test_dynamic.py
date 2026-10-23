"""TEST DATA for interpolation, scopes, drawing and original audio; never published."""
import json
import shutil
import subprocess
import wave
import numpy as np
import pytest
from shorts.history import snapshot
from shorts.main import choose_format,parser
from shorts.dynamic import Film
from shorts.beat import create

@pytest.fixture
def history():
    return {'metric':'Population','unit':'people','start_year':2000,'year':2002,'years':[2000,2001,2002],
            'pair':['AAA','BBB'],'places':{'AAA':{'name':'Test A','iso2':'aa'},'BBB':{'name':'Test B','iso2':'bb'},'CCC':{'name':'Missing Test C','iso2':'cc'}},
            'tables':{'2000':{'AAA':100,'BBB':80,'CCC':50},'2001':{'AAA':110,'BBB':120},'2002':{'AAA':120,'BBB':160}},
            'leader_changes':[{'year':2000,'code':'AAA'},{'year':2001,'code':'BBB'}]}

def test_interpolation(history):
    v,lo,hi,f=snapshot(history,2000.5)
    assert (lo,hi,f)==(2000,2001,.5)
    assert v['AAA']==105 and v['BBB']==100
    assert 'CCC' not in v  # Never invent an observation across a missing value.

def test_final_source_values(history):
    assert snapshot(history,2002)[0]==history['tables']['2002']

def test_mode_selection():
    assert choose_format('India vs China population')=='Versus'
    assert choose_format('Country wise population over time')=='Race'
    assert choose_format('Country wise population','Explainer')=='Explainer'
    assert parser().parse_args(['--brief','Population race']).format=='Auto'

@pytest.mark.parametrize('mode',['Race','Versus'])
def test_animated_composition(history,mode):
    f=Film(history,mode,{});f.duration=30
    a=f.frame(5,30,True);b=f.frame(20,30,True)
    assert a.size==(540,960) and a.tobytes()!=b.tobytes()

def test_original_score(tmp_path):
    a=tmp_path/'a.wav';b=tmp_path/'b.wav'
    meta=create(a,2,seed=3);create(b,2,seed=3)
    assert a.read_bytes()==b.read_bytes()
    assert meta['reference_audio_used'] is False
    with wave.open(str(a)) as w:
        assert w.getnchannels()==2 and w.getframerate()==44100
        data=np.frombuffer(w.readframes(w.getnframes()),dtype='<i2')
        assert np.max(np.abs(data))<32767 and np.sqrt(np.mean(data.astype(float)**2))>100

def test_true_frozen_video_is_rejected(tmp_path):
    from shorts.quality import check
    if not shutil.which('ffmpeg'):pytest.skip('FFmpeg required')
    subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=0x14253E:s=540x960:r=30','-f','lavfi','-i','anullsrc=r=44100:cl=stereo','-t','4.2','-c:v','libx264','-preset','ultrafast','-c:a','aac',str(tmp_path/'video.mp4')],check=True)
    with pytest.raises(ValueError,match='no_frozen_sequences'):
        check(tmp_path,4.2,preview=True,captions_required=False,allow_silence=True)
    report=json.loads((tmp_path/'quality_report.json').read_text())
    assert report['checks']['decode'] and not report['checks']['no_frozen_sequences']
    with pytest.raises(ValueError,match='no_frozen_sequences'):
        check(tmp_path,4.2,preview=True,captions_required=False,allow_silence=True,animation_window=(.1,4.1))

@pytest.mark.parametrize('icon',['people','coins','heart','screen','trophy','bar'])
def test_generic_pictograms(history,icon):
    history['icon']=icon
    film=Film(history,'Versus',{});film.duration=30
    assert film.frame(15,30,True).size==(540,960)

def test_observed_zeros_do_not_crash_race(history):
    history['tables']={y:{c:0.0 for c in table} for y,table in history['tables'].items()}
    film=Film(history,'Race',{});film.duration=30
    assert film.frame(10,30,True).size==(540,960)

@pytest.mark.parametrize('mode',['Race','Versus'])
def test_clean_on_screen_copy(history,mode,monkeypatch):
    import shorts.dynamic as module
    labels=[]
    original=module.text
    def record(draw,label,*args,**kwargs):
        labels.append(str(label));return original(draw,label,*args,**kwargs)
    monkeypatch.setattr(module,'text',record)
    film=Film(history,mode,{});film.duration=30
    image=film.frame(29,30)
    forbidden=['fieldnotes','world bank','data in motion','top ','leads','leader','observed','source','icon ≈','intermediate','head to head']
    assert not any(word in label.lower() for word in forbidden for label in labels)
    assert '2002' in labels
    assert image.getpixel((0,0))==(255,255,255)

def test_small_changes_in_versus_do_not_freeze(history,tmp_path,monkeypatch):
    """A slow percentage comparison must move between rounded counter updates."""
    from shorts.dynamic import render
    from shorts.quality import check
    if not shutil.which('ffmpeg'):pytest.skip('FFmpeg required')
    history['tables']={
        '2000':{'AAA':7.652,'BBB':4.93},
        '2001':{'AAA':6.51,'BBB':5.15},
        '2002':{'AAA':7.859,'BBB':5.61},
    }
    history['metric']='TEST percentage comparison'
    monkeypatch.setattr('shorts.dynamic.load_flags',lambda *a:{})
    render(history,tmp_path,30,'Versus',music='None',preview=True)
    report=check(tmp_path,30,True,captions_required=False,allow_silence=True,animation_window=(1.2,27.5))
    assert report['passed']
