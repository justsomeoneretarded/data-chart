"""Streaming raster motion design; memory is independent of video duration."""
import math
import subprocess
import textwrap
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .audio import run

FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
PALETTES={'Cinematic':('#0b1425','#4ee3c2','#f5bd71'),'Minimal':('#141821','#f4f5f7','#a7b4d0'),'Energetic':('#17102c','#b4fc59','#f579cb'),'Documentary':('#172023','#f6c879','#a8d5c7'),'Auto':('#0b1425','#4ee3c2','#f5bd71')}
def ease(x): x=max(0,min(1,x));return x*x*(3-2*x)
def fmt(v):
    for n,s in [(1e12,'T'),(1e9,'B'),(1e6,'M'),(1e3,'K')]:
        if abs(v)>=n:return f'{v/n:.1f}{s}'
    return f'{v:.1f}'
def font(size,bold=False):return ImageFont.truetype(BOLD if bold else FONT,size)
def wrapped(draw,text,xy,size=52,width=850,fill='white',bold=True):
    f=font(size,bold);x,y=xy;line=''
    for word in text.split():
        candidate=(line+' '+word).strip()
        if draw.textlength(candidate,font=f)>width and line:
            draw.text((x,y),line,font=f,fill=fill);y+=size*1.3;line=word
        else:line=candidate
    if line:draw.text((x,y),line,font=f,fill=fill);y+=size*1.3
    return y

def frame(t,scenes,data,style='Auto',size=(1080,1920)):
    bg,accent,secondary=PALETTES[style]
    im=Image.new('RGB',(1080,1920),bg);d=ImageDraw.Draw(im)
    # restrained moving grid and orbital geometry
    drift=int(20*math.sin(t*.28))
    for x in range(-200,1300,130):d.line((x+drift,0,x+drift,1920),fill='#1a293a',width=1)
    for y in range(0,1920,130):d.line((0,y+drift,1080,y+drift),fill='#1a293a',width=1)
    d.ellipse((650+drift,-200,1450+drift,600),outline='#284251',width=2)
    d.text((85,115),'FIELDNOTES   /   DATA EXPLAINED',font=font(25,True),fill=accent)
    scene=next((s for s in scenes if s['start']<=t<s['end']),scenes[-1]);local=t-scene['start'];progress=ease(local/1.2)
    idx=scenes.index(scene)
    d.rounded_rectangle((85,185,240,233),radius=12,fill=accent)
    d.text((100,192),f'0{idx+1} / 04',font=font(25,True),fill=bg)
    wrapped(d,scene['text'],(85,280+int(22*(1-progress))),size=61,width=850)
    rows=data['rows'];kind=scene['kind']
    if kind=='bars':
        for i,r in enumerate(rows):
            y=610+i*145;p=ease((local-i*.28)/1.5)
            name=r['name']
            fsize=35
            while d.textlength(name,font=font(fsize,True))>650:fsize-=1
            d.text((85,y),name,font=font(fsize,True),fill='white')
            d.rounded_rectangle((85,y+56,930,y+88),radius=12,fill='#25374b')
            bar=max(1,int(845*r['value']/rows[0]['value']*p))
            d.rounded_rectangle((85,y+56,85+bar,y+88),radius=12,fill=accent if i==0 else '#5e8f9a')
            d.text((790,y+4),fmt(r['value']*p),font=font(34,True),fill=secondary)
    elif kind=='contrast':
        gap=rows[0]['value']-rows[4]['value']
        d.text((85,610),fmt(gap*progress),font=font(170,True),fill=accent)
        wrapped(d,data['unit'],(95,810),size=38,fill=secondary)
        wrapped(d,'BETWEEN THE FIRST AND FIFTH SHOWN',(95,935),size=33,width=760)
        for i,r in enumerate([rows[0],rows[4]]):
            y=1060+i*145
            wrapped(d,r['name'],(95,y),size=32,width=730)
            d.rounded_rectangle((95,y+57,95+max(1,int(740*r['value']/rows[0]['value']*progress)),y+86),radius=10,fill=accent if i==0 else secondary)
    elif kind=='hook':
        for i in range(3):
            y=640+i*180;w=int((740-i*130)*ease((local-i*.18)/1.8))
            d.rounded_rectangle((85,y,85+max(w,2),y+110),radius=22,fill=accent if i==0 else '#355869')
            if progress>.5:d.text((110,y+28),['A NUMBER','A COMPARISON','A QUESTION'][i],font=font(36,True),fill=bg if i==0 else 'white')
        wrapped(d,'What does the ranking actually tell us?',(85,1230),size=43,width=820,fill=secondary)
    else:
        wrapped(d,data['definition'],(85,620),size=43,width=800,fill=accent)
        wrapped(d,'ONE MEASURE\nONE COMMON YEAR\nREPORTED DATA ONLY',(85,1040),size=38,width=800,fill=secondary)
    d.text((85,1700),f"WORLD BANK  /  {data['year']}  /  {data['coverage']} REPORTING PLACES",font=font(24,True),fill='#b3c5d5')
    wrapped(d,data['unit'].upper(),(85,1750),size=24,width=850,fill='#b3c5d5')
    total=scenes[-1]['end'];d.rectangle((85,1815,85+int(845*min(1,t/total)),1821),fill=accent)
    # soft per-scene entrance, no full black frames
    if local<.22:
        im=Image.blend(Image.new('RGB',im.size,bg),im,.35+.65*ease(local/.22))
    return im if size==(1080,1920) else im.resize(size,Image.Resampling.LANCZOS)

def render(scenes,data,out,style='Auto',music='Auto',seed=42,preview=False):
    width,height=(540,960) if preview else (1080,1920);fps=30;duration=scenes[-1]['end']
    # FFmpeg encodes once, with ASS captions and a ducked procedural score.
    narration=out/'narration.wav'
    command=['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r',str(fps),'-i','pipe:0','-i',str(narration)]
    if music!='None':
        score(out/'music.wav',duration,music,seed)
        command+=['-i',str(out/'music.wav'),'-filter_complex','[1:a]asplit=2[n][side];[2:a][side]sidechaincompress=threshold=0.025:ratio=8:attack=15:release=300[m];[n][m]amix=inputs=2:normalize=0,alimiter=limit=0.95[a]','-map','0:v','-map','[a]']
    else:command+=['-map','0:v','-map','1:a']
    # Paths are generated locally; no untrusted brief is inserted in a filter.
    command+=['-vf',f"ass={out.resolve()/'subtitles.ass'}",'-c:v','libx264','-preset','veryfast','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t',str(duration),'-movflags','+faststart',str(out/'video.mp4')]
    proc=subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        for i in range(math.ceil(duration*fps)):
            proc.stdin.write(frame(i/fps,scenes,data,style,(width,height)).tobytes())
        proc.stdin.close()
        if proc.wait(timeout=600):raise RuntimeError('FFmpeg render failed')
    except BaseException:
        proc.kill();proc.wait();raise
    thumb=frame(scenes[1]['start']+2,scenes,data,style)
    thumb.save(out/'thumbnail.png')

def score(path,duration,style,seed):
    import wave
    sr=24000;t=np.arange(math.ceil(duration*sr))/sr
    # Original procedural score. Slow pentatonic tones, no sampled copyrighted music.
    rng=np.random.default_rng(seed);signal=np.zeros(len(t))
    notes={'Ambient':[130.81,164.81,196.0], 'Cinematic':[110,130.81,164.81], 'Electronic':[130.81,196,261.63]}.get(style,[130.81,164.81,196])
    for i,f in enumerate(notes):signal+=.012*np.sin(2*np.pi*f*t+rng.uniform(0,6.28))*(.65+.35*np.sin(2*np.pi*.08*t+i))
    signal*=np.minimum(t/2,1)*np.minimum((duration-t)/2,1)
    with wave.open(str(path),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr);w.writeframes((signal*32767).astype('<i2').tobytes())
