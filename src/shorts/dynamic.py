"""Music-first comparison films: continuous races and accumulating icon duels."""
import hashlib
import io
import json
import math
import subprocess
from functools import lru_cache
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .history import snapshot
from .research import session
from .beat import create, BPM
from .visuals import fmt

W,H=1080,1920
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
COLORS=['#73F1C5','#82ACFF','#FFAE72','#D299FF','#F3CF68','#F78AB4','#72DBF0','#B9E86A']
SHORT={'United States':'United States','Russian Federation':'Russia','Korea, Rep.':'South Korea','Iran, Islamic Rep.':'Iran','Egypt, Arab Rep.':'Egypt','Hong Kong SAR, China':'Hong Kong','Venezuela, RB':'Venezuela','Congo, Dem. Rep.':'DR Congo'}

@lru_cache(maxsize=100)
def font(size,bold=True):return ImageFont.truetype(BOLD if bold else FONT,size)
def ease(x):x=max(0,min(1,x));return 1-(1-x)**3

def text(d,label,xy,size=40,color='white',max_width=None,bold=True):
    while max_width and d.textlength(label,font=font(size,bold))>max_width and size>20:size-=1
    d.text(xy,label,font=font(size,bold),fill=color)

def live_fmt(value):
    if abs(value)>=1e12:return f'{value/1e12:.2f}T'
    if abs(value)>=1e9:return f'{value/1e9:.3f}B'
    return fmt(value)

def color(code):return COLORS[int(hashlib.sha256(code.encode()).hexdigest()[:6],16)%len(COLORS)]
def rgb(hex):return tuple(int(hex[i:i+2],16) for i in [1,3,5])

@lru_cache(maxsize=20)
def background(mode,style="Auto"):
    y,x=np.mgrid[0:H,0:W];glow=np.exp(-((x-800)**2/(700**2)+(y-450)**2/(1000**2)))
    base=np.zeros((H,W,3),np.uint8)
    for i,(low,high) in enumerate([(8,19),(13,26),(26,49)]):base[:,:,i]=low+(high-low)*glow
    if style=='Energetic':base[:,:,0]=np.clip(base[:,:,0]+(glow*22).astype(np.uint8),0,255)
    if style=='Documentary':base[:,:,1]=np.clip(base[:,:,1]+(glow*13).astype(np.uint8),0,255)
    if style=='Minimal':base[:,:,:]=[13,17,24]
    if mode=='Versus':
        split=np.where(x<W//2,1,0)
        base[:,:,2]=np.clip(base[:,:,2]+split*12,0,255)
        base[:,:,0]=np.clip(base[:,:,0]+(1-split)*12,0,255)
    return Image.fromarray(base)


def load_flags(data,out):
    important=set(data['pair'])
    for table in data['tables'].values():important.update(sorted(table,key=lambda c:-table[c])[:9])
    root=out/'flags';root.mkdir(exist_ok=True);flags={};manifest=[];s=session()
    for code in sorted(important):
        iso=data['places'][code]['iso2'].lower()
        if len(iso)!=2:continue
        url=f'https://flagcdn.com/w160/{iso}.png';path=root/f'{code}.png'
        try:
            r=s.get(url,timeout=(10,20));r.raise_for_status()
            im=Image.open(io.BytesIO(r.content)).convert('RGB');im.load();path.write_bytes(r.content);flags[code]=im
            manifest.append({'code':code,'url':url,'purpose':'national flag identification','attribution':'Flagpedia / flagcdn; national flag designs; check jurisdiction-specific restrictions'})
        except Exception:
            # Labels remain complete if the optional flag service is unavailable.
            manifest.append({'code':code,'url':url,'fallback':'ISO3 badge; flag unavailable'})
    (out/'asset_sources.json').write_text(json.dumps(manifest,indent=2))
    return flags


def flag(im,d,code,flags,xy,size=(72,48)):
    x,y=map(int,xy)
    if code in flags:
        asset=flags[code].resize(size,Image.Resampling.LANCZOS)
        mask=Image.new('L',size,0);ImageDraw.Draw(mask).rounded_rectangle((0,0,size[0]-1,size[1]-1),radius=7,fill=255)
        im.paste(asset,(x,y),mask)
    else:
        d.rounded_rectangle((x,y,x+size[0],y+size[1]),radius=7,fill='#253D52')
        text(d,code,(x+5,y+9),size=23)


def glyph(d,x,y,fill,scale,metric):
    if metric in ['Population','Fertility rate']:
        people(d,x,y,fill,scale)
    elif metric=='GDP':
        r=18*scale
        d.ellipse((x-r,y+12*scale,x+r,y+48*scale),outline=fill,width=max(1,int(3*scale)))
        d.line((x,y+18*scale,x,y+42*scale),fill=fill,width=max(1,int(3*scale)))
        d.arc((x-8*scale,y+18*scale,x+8*scale,y+33*scale),80,280,fill=fill,width=2)
        d.arc((x-8*scale,y+28*scale,x+8*scale,y+43*scale),260,460,fill=fill,width=2)
    elif metric=='Life expectancy at birth':
        d.ellipse((x-19*scale,y+8*scale,x+2*scale,y+30*scale),fill=fill)
        d.ellipse((x-2*scale,y+8*scale,x+19*scale,y+30*scale),fill=fill)
        d.polygon([(x-18*scale,y+23*scale),(x+18*scale,y+23*scale),(x,y+47*scale)],fill=fill)
    else:
        d.rounded_rectangle((x-19*scale,y+8*scale,x+19*scale,y+38*scale),radius=3,outline=fill,width=2)
        d.line((x,y+39*scale,x,y+48*scale),fill=fill,width=2)
        d.line((x-10*scale,y+48*scale,x+10*scale,y+48*scale),fill=fill,width=2)


def timeline(t,duration,data):
    # Two-beat introduction and a final hold still retain animated beat/progress elements.
    start=1.2;hold=2.5
    u=max(0,min(1,(t-start)/max(1,duration-start-hold)))
    return data['start_year']+(data['year']-data['start_year'])*u


def people(d,x,y,fill,scale=1):
    r=7*scale
    d.ellipse((x-r,y,x+r,y+2*r),fill=fill)
    d.rounded_rectangle((x-11*scale,y+18*scale,x+11*scale,y+48*scale),radius=6*scale,fill=fill)
    d.rounded_rectangle((x-10*scale,y+42*scale,x-1*scale,y+67*scale),radius=3*scale,fill=fill)
    d.rounded_rectangle((x+1*scale,y+42*scale,x+10*scale,y+67*scale),radius=3*scale,fill=fill)


class Film:
    def __init__(self,data,mode,flags,style='Auto'):
        self.data=data;self.mode=mode;self.flags=flags;self.style=style
        self.ranks={int(y):{c:i for i,c in enumerate(sorted(table,key=lambda c:(-table[c],c)))} for y,table in data['tables'].items()}
        self.total_max=max(v for table in data['tables'].values() for v in table.values())
        self.name=lambda c:SHORT.get(data['places'][c]['name'],data['places'][c]['name'])
        self.unit=self.total_max/40 if self.total_max else 1
        self.bars={}
        for c in set(data['places']):
            # A reusable horizontal gradient is cropped to the live bar width.
            shade=np.array(rgb(color(c)));a=np.linspace(.42,1,850)[:,None];arr=np.tile((shade[None,:]*a).astype(np.uint8)[None,:,:],(68,1,1))
            self.bars[c]=Image.fromarray(arr)
    def frame(self,t,duration,preview=False):
        data=self.data;im=background(self.mode,self.style).copy();d=ImageDraw.Draw(im)
        pulse=(1+math.cos(t*2*math.pi*BPM/60))/2
        # Decorative motion sits behind the information, not over labels.
        for i in range(11):
            x=int((i*113+t*(5+i%3))%1080);y=int(80+(i*157)%1700)
            d.ellipse((x,y,x+3,y+3),fill='#365169')
        d.line((48,105,1032,105),fill='#2B3C50',width=2)
        text(d,'FIELDNOTES',(48,53),28,color='#B5C2D5')
        text(d,'DATA IN MOTION',(735,55),23,color='#74F1C5')
        text(d,self.mode.upper()+' / WORLD BANK',(48,143),23,color='#73F1C5')
        title={'Population':'THE POPULATION\nRACE','GDP':'THE ECONOMIC\nRACE','Life expectancy at birth':'THE LONGEVITY\nRACE','Fertility rate':'BIRTHS, IN\nMOTION','Individuals using the Internet':'THE INTERNET\nREVOLUTION'}[data['metric']]
        if self.mode=='Versus':title={'Population':'POPULATION','GDP':'GDP','Life expectancy at birth':'LONGEVITY','Fertility rate':'FERTILITY','Individuals using the Internet':'INTERNET USAGE'}[data['metric']]+'\nHEAD TO HEAD'
        for i,line in enumerate(title.split('\n')):text(d,line,(48,196+i*86),76,max_width=970)
        year=timeline(t,duration,data);values,lo,hi,fraction=snapshot(data,year)
        if self.mode=='Race':self.race(im,d,t,values,lo,hi,fraction)
        else:self.versus(im,d,t,values)
        if t>duration-3.3:
            # A beat-lit final reveal is part of the composition, not a fake data change.
            winner=max(values,key=values.get)
            accent=rgb(color(winner));shade=tuple(int(v*(.35+.15*pulse)) for v in accent)
            d.rounded_rectangle((48,390,1032,440),radius=12,fill=shade,outline=color(winner),width=3)
            top_value=values[winner]
            tied=sum(math.isclose(v,top_value,rel_tol=0,abs_tol=1e-9) for v in values.values())>1
            label=f"{data['year']} {'JOINT LEADER' if tied else 'LEADER'}  /  {self.name(winner).upper()}"
            text(d,label,(68,400),26,max_width=930)
        # Large time counter is the visual anchor in both formats.
        text(d,str(int(year+1e-6)),(650,1505),132,color='#E8F0FF',max_width=380)
        text(d,f"{data['start_year']} — {data['year']}",(52,1543),31,color='#9AAEC7')
        text(d,'OBSERVED ANNUALLY',(52,1592),22,color='#9AAEC7')
        text(d,data['unit'].upper(),(48,1687),27,color='#D3DFED',max_width=980)
        text(d,'INTERMEDIATE VALUES ANIMATED BETWEEN OBSERVATIONS',(48,1732),20,color='#8296B0',max_width=980,bold=False)
        d.rounded_rectangle((48,1802,1032,1808),radius=3,fill='#263449')
        d.rounded_rectangle((48,1802,48+max(2,int(984*t/duration)),1808),radius=3,fill='#74F1C5')
        # Beat meter and advancing playhead keep the final-value hold visually active.
        for i in range(20):
            h=4+int(15*(.5+.5*math.sin(t*BPM/60*math.pi*2-i*.37)))
            d.rectangle((50+i*9,1853-h,54+i*9,1853),fill='#74F1C5')
        text(d,'SOURCE → data.worldbank.org',(490,1835),23,color='#8296B0',max_width=540)
        return im.resize((540,960),Image.Resampling.LANCZOS) if preview else im
    def race(self,im,d,t,values,lo,hi,fraction):
        data=self.data;top=sorted(values,key=lambda c:(-values[c],c))[:10]
        if not top:return
        scale=max(1e-12,max(values.values())*1.05)
        ranka=self.ranks[lo];rankb=self.ranks[hi]
        text(d,f'TOP {min(8,len(values))}  /  REPORTING COUNTRIES & TERRITORIES',(48,402),22,color='#9AAEC7')
        # Render rows on a separate layer so entering/exiting ranks clip cleanly.
        layer=Image.new('RGBA',(1080,984),(0,0,0,0));ld=ImageDraw.Draw(layer)
        for c in reversed(top):
            rank=ranka.get(c,12)+(rankb.get(c,12)-ranka.get(c,12))*fraction
            y=int(rank*123+18+(1-ease(t/1.1))*40)
            if y>1030 or y< -120:continue
            ld.rounded_rectangle((46,y-7,1032,y+105),radius=18,fill=(20,33,52,210))
            text(ld,f'{int(round(rank))+1:02}',(61,y+8),22,color='#8398B5')
            flag(layer,ld,c,self.flags,(108,y+7),(64,43))
            text(ld,self.name(c),(191,y+4),37,max_width=600)
            label=live_fmt(values[c]);f=font(38)
            ld.text((1000-ld.textlength(label,font=f),y+3),label,font=f,fill=color(c))
            width=max(2,int(810*values[c]/scale))
            ld.rounded_rectangle((191,y+61,1000,y+85),radius=12,fill='#23344B')
            strip=self.bars[c].resize((max(1,width),24))
            mask=Image.new('L',(max(1,width),24),0);ImageDraw.Draw(mask).rounded_rectangle((0,0,width,24),radius=12,fill=255)
            layer.paste(strip,(191,y+61),mask)
        im.paste(layer,(0,450),layer)
        # Source-derived lead changes, timed to the annual observation that supports them.
        now=int(timeline(t,self.duration,data)) if hasattr(self,'duration') else lo
        changes=[r for r in data['leader_changes'] if r['year']<=now]
        if changes:
            latest=changes[-1];name=self.name(latest['code'])
            label=f"{name.upper()} LEADS" if latest['year']==data['start_year'] else f"{name.upper()} TOOK THE LEAD · {latest['year']}"
            if latest.get('tied'):label=f"{name.upper()} / JOINT LEADER"
            text(d,label,(48,1468),24,color=color(latest['code']),max_width=980)
    def versus(self,im,d,t,values):
        data=self.data;pair=data['pair'];colors=['#80B2FF','#FF8B9B']
        text(d,'LIVE COMPARISON',(48,405),22,color='#9AAEC7')
        for i,c in enumerate(pair):
            x=48+i*504;v=values[c];accent=colors[i]
            d.rounded_rectangle((x,460,x+480,1435),radius=28,fill='#14253E' if i==0 else '#321F32',outline=accent,width=2)
            flag(im,d,c,self.flags,(x+24,486),(104,70))
            text(d,self.name(c).upper(),(x+24,586),39,max_width=432)
            text(d,live_fmt(v),(x+24,666),92,color=accent,max_width=432)
            d.rounded_rectangle((x+24,798,x+456,800),radius=1,fill=accent)
            count=v/self.unit
            for n in range(48):
                cx=x+50+(n%8)*54;cy=846+(n//8)*87
                fill=accent if n<count else '#334156'
                scale=.66
                if 0<count-n<1.4:scale*=1+.12*math.sin(t*BPM/60*math.pi*2)
                glyph(d,cx,cy,fill,scale,data['metric'])
            text(d,f'1 ICON ≈ {fmt(self.unit)}',(x+24,1390),21,color='#9BAAC0',max_width=432)
        # The point-in-time split is computed from actual values, not a fabricated score.
        total=sum(values[c] for c in pair);share=values[pair[0]]/total if total else .5
        d.rounded_rectangle((48,1470,1032,1482),radius=6,fill=colors[1])
        d.rounded_rectangle((48,1470,48+int(984*share),1482),radius=6,fill=colors[0])


def render(data,out,duration=50,mode='Race',music='Auto',style='Auto',seed=42,preview=False):
    flags=load_flags(data,out);film=Film(data,mode,flags,style);film.duration=duration
    width,height=(540,960) if preview else (1080,1920)
    if music=='None':
        command=['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r','30','-i','pipe:0','-f','lavfi','-i','anullsrc=r=44100:cl=stereo']
        audio={'enabled':False,'narration':False}
    else:
        audio=create(out/'music.wav',duration,seed,music);audio['enabled']=True;audio['narration']=False
        command=['ffmpeg','-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r','30','-i','pipe:0','-i',str(out/'music.wav')]
    command+=['-map','0:v','-map','1:a','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-t',str(duration),'-movflags','+faststart',str(out/'video.mp4')]
    proc=subprocess.Popen(command,stdin=subprocess.PIPE)
    try:
        for i in range(math.ceil(duration*30)):
            proc.stdin.write(film.frame(i/30,duration,preview).tobytes())
            if i%300==0:print(f'Rendered {i//30}s / {duration}s',flush=True)
        proc.stdin.close()
        if proc.wait(timeout=600):raise RuntimeError('Dynamic FFmpeg render failed')
    except BaseException:proc.kill();proc.wait();raise
    film.frame(duration-2.5,duration).save(out/'thumbnail.png')
    (out/'audio_report.json').write_text(json.dumps(audio,indent=2))
    return audio
