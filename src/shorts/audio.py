"""Chunked permitted speech, measured timing, and independent ASR alignment."""
import difflib
from collections import Counter
from decimal import Decimal
import json
import re
import subprocess
import time
import wave
from pathlib import Path
import requests

PIPER_ROOT='https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/ljspeech/medium/'
def run(args):
    subprocess.run([str(a) for a in args],check=True,timeout=600,stdout=subprocess.DEVNULL)
def seconds(path):
    with wave.open(str(path)) as w: return w.getnframes()/w.getframerate()
def download(url,path):
    if not path.exists():
        r=requests.get(url,timeout=(15,180));r.raise_for_status();path.write_bytes(r.content)

def synthesize(story,out,voice='Warguy',engine='piper',duration=50):
    started=time.monotonic();chunks=[];warnings=[]
    reference=Path('assets/voices')/(voice.replace(' ','_')+'.wav')
    consent=reference.with_suffix('.license.txt')
    if not reference.exists() or not consent.exists():
        warnings.append(f'{voice}: authorized reference and consent record unavailable; using disclosed neutral synthetic voice.')
    if engine=='chatterbox':
        if not reference.exists() or not consent.exists():
            raise ValueError('Chatterbox requires a reference WAV and adjacent .license.txt consent record')
        from chatterbox.tts_turbo import ChatterboxTurboTTS
        import torchaudio
        model=ChatterboxTurboTTS.from_pretrained(device='cpu')
        def speak(text,path):
            torchaudio.save(str(path),model.generate(text,audio_prompt_path=str(reference)),model.sr)
        actual='Chatterbox Turbo CPU, authorized reference'
    elif engine=='piper':
        from piper import PiperVoice
        root=Path('models');root.mkdir(exist_ok=True)
        modelpath=root/'en_US-ljspeech-medium.onnx'
        for suffix in ['', '.json']:
            download(PIPER_ROOT+modelpath.name+suffix,Path(str(modelpath)+suffix))
        card=root/'LJSPEECH_MODEL_CARD.txt'
        download(PIPER_ROOT+'MODEL_CARD',card)
        (out/'voice_model_card.txt').write_text(card.read_text())
        model=PiperVoice.load(str(modelpath))
        def speak(text,path):
            with wave.open(str(path),'wb') as f: model.synthesize_wav(text,f)
        actual='Piper en_US-ljspeech-medium; generic model preset, no user voice cloning'
    else:
        def speak(text,path): run(['espeak-ng','-s','165','-w',path,text])
        actual='eSpeak NG synthetic demonstration voice (lower naturalness)'
        warnings.append('Demonstration voice: use Piper for release output.')
    for i,scene in enumerate(story.scenes):
        path=out/f'chunk-{i}.wav';speak(scene.narration,path);chunks.append(path)
    raw_total=sum(seconds(p) for p in chunks)
    tempo=raw_total/duration
    if not 0.72<=tempo<=1.35:
        raise ValueError(f'Script pacing cannot fit target naturally: {raw_total:.1f}s speech for {duration}s target. Select a duration near {raw_total:.0f}s.')
    normalized=[];offset=0;scenes=[]
    for i,(path,scene) in enumerate(zip(chunks,story.scenes)):
        dest=out/f'voice-{i}.wav'
        run(['ffmpeg','-v','error','-y','-i',path,'-af',f'atempo={tempo},loudnorm=I=-16:TP=-2:LRA=9','-ar','24000','-ac','1',dest])
        length=seconds(dest);scenes.append({**scene.model_dump(),'start':offset,'end':offset+length,'transition':'smooth fade','camera':'subtle drift','subtitle_safe_region':[90,1400,900,1660]});offset+=length;normalized.append(dest)
    with (out/'concat.txt').open('w') as f:
        for p in normalized:f.write(f"file '{p.resolve()}'\n")
    run(['ffmpeg','-v','error','-y','-f','concat','-safe','0','-i',out/'concat.txt','-c:a','pcm_s16le',out/'narration.wav'])
    return scenes,{'engine':actual,'warnings':warnings,'raw_seconds':raw_total,'tempo':tempo,'generation_seconds':time.monotonic()-started}

def numeric_tokens(text):
    """Compare equivalent English numeric spellings without weakening value checks."""
    tokens = re.findall(r'(?<![\w.])(\d[\d,]*(?:\s*\.\s*\d+)?)(?:\s*(trillion|billion|million|thousand)\b)?', text.lower())
    scales = {'': Decimal(1), 'thousand': Decimal(1000), 'million': Decimal(10)**6,
              'billion': Decimal(10)**9, 'trillion': Decimal(10)**12}
    return Counter(Decimal(re.sub(r'[\s,]', '', number)) * scales[suffix]
                   for number, suffix in tokens)


def normalize(text): return re.findall(r"[a-z0-9]+",text.lower())
def align(scenes,out,model_name='base'):
    from faster_whisper import WhisperModel
    model=WhisperModel(model_name,device='cpu',compute_type='int8',cpu_threads=4)
    words=[];reports=[]
    for i,scene in enumerate(scenes):
        segments,_=model.transcribe(str(out/f'voice-{i}.wav'),language='en',beam_size=5,word_timestamps=True,condition_on_previous_text=False)
        chunkwords=[w for s in segments for w in (s.words or [])]
        actual=' '.join(w.word for w in chunkwords)
        similarity=difflib.SequenceMatcher(None,normalize(scene['narration']),normalize(actual),autojunk=False).ratio()
        numeric_match=numeric_tokens(scene['narration'])==numeric_tokens(actual)
        reports.append({'numeric_match':numeric_match,'scene':i,'expected':scene['narration'],'recognized':actual,'similarity':similarity})
        if similarity<0.80 or not chunkwords or not numeric_match:
            (out/'speech_check.json').write_text(json.dumps(reports,indent=2))
            raise ValueError(f'Speech mismatch in scene {i}: {similarity:.0%}, numerical match={numeric_match}. Original chunks retained for diagnosis.')
        words += [{'text':w.word.strip(),'start':scene['start']+w.start,'end':min(scene['end'],scene['start']+w.end)} for w in chunkwords]
    (out/'speech_check.json').write_text(json.dumps(reports,indent=2))
    return words
