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
COLORS=['#178CFA','#2838A8','#F1772D','#177C8A','#81118B','#00AFCB','#C4A600','#486DC3','#D7596B','#16A085','#8E5EA2','#D45E00']

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

def color(code):
    return COLORS[int(hashlib.sha256(code.encode()).hexdigest()[:6],16)%len(COLORS)]

def rgb(hex):return tuple(int(hex[i:i+2],16) for i in [1,3,5])



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
    if metric=='people':
        people(d,x,y,fill,scale)
    elif metric=='trophy':
        d.polygon([(x-16,y+8),(x+16,y+8),(x+10,y+32),(x,y+38),(x-10,y+32)],fill=fill)
        d.line((x,y+34,x,y+49),fill=fill,width=5)
        d.rectangle((x-13,y+48,x+13,y+53),fill=fill)
        d.arc((x-25,y+9,x+25,y+36),0,180,fill=fill,width=3)
    elif metric=='coins':
        r=18*scale
        d.ellipse((x-r,y+12*scale,x+r,y+48*scale),outline=fill,width=max(1,int(3*scale)))
        d.line((x,y+18*scale,x,y+42*scale),fill=fill,width=max(1,int(3*scale)))
        d.arc((x-8*scale,y+18*scale,x+8*scale,y+33*scale),80,280,fill=fill,width=2)
        d.arc((x-8*scale,y+28*scale,x+8*scale,y+43*scale),260,460,fill=fill,width=2)
    elif metric=='heart':
        d.ellipse((x-19*scale,y+8*scale,x+2*scale,y+30*scale),fill=fill)
        d.ellipse((x-2*scale,y+8*scale,x+19*scale,y+30*scale),fill=fill)
        d.polygon([(x-18*scale,y+23*scale),(x+18*scale,y+23*scale),(x,y+47*scale)],fill=fill)
    elif metric=='bar':
        for k,h in enumerate([18,30,42]):
            d.rectangle((x-20+k*15,y+50-h,x-11+k*15,y+50),fill=fill)
    else:
        d.rounded_rectangle((x-19*scale,y+8*scale,x+19*scale,y+38*scale),radius=3,outline=fill,width=2)
        d.line((x,y+39*scale,x,y+48*scale),fill=fill,width=2)
        d.line((x-10*scale,y+48*scale,x+10*scale,y+48*scale),fill=fill,width=2)


def timeline(t,duration,data):
    # Brief opening and final holds; the canvas has no decorative UI elements.
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
        self.name=lambda c:data['places'][c]['name']
        self.unit=self.total_max/40 if self.total_max else 1
    def fill(self,code):
        base=np.array(rgb(color(code)),dtype=float)
        if self.style=='Cinematic':base*=.8
        elif self.style=='Energetic':base=np.minimum(255,base*1.12)
        elif self.style=='Documentary':base=.75*base+.25*120
        elif self.style=='Minimal':base=.65*base+.35*85
        return tuple(base.astype(int))

    def frame(self,t,duration,preview=False):
        data=self.data
        im=Image.new('RGB',(W,H),'white');d=ImageDraw.Draw(im)
        title=data['metric']
        text(d,title,(30,65),64,color='#151515',max_width=1020)
        year=timeline(t,duration,data);values,lo,hi,fraction=snapshot(data,year)
        if self.mode=='Race':self.race(im,d,t,values,lo,hi,fraction)
        else:self.versus(im,d,t,values)
        label=str(int(year+1e-6));f=font(130)
        text(d,label,(1030-d.textlength(label,font=f),1660),130,color='#777777')
        return im.resize((540,960),Image.Resampling.LANCZOS) if preview else im

    def race(self,im,d,t,values,lo,hi,fraction):
        if not values:return
        visible=min(15,len(values));pitch=min(150,1320/max(1,visible));height=min(80,int(pitch*.64))
        top=sorted(values,key=lambda c:(-values[c],c))[:visible+2]
        scale=max(1e-12,max(values.values())*1.025)
        ranka=self.ranks[lo];rankb=self.ranks[hi]
        layer=Image.new('RGBA',(W,int(visible*pitch)),(255,255,255,0));ld=ImageDraw.Draw(layer)
        for c in reversed(top):
            rank=ranka.get(c,visible+2)+(rankb.get(c,visible+2)-ranka.get(c,visible+2))*fraction
            y=int(rank*pitch+10)
            offset=max(7,(height-42)//2)
            if y>=visible*pitch or y < -pitch:continue
            text(ld,self.name(c),(24,y+offset),36,color='#151515',max_width=215,bold=False)
            width=max(0,int(620*values[c]/scale))
            if width:ld.rectangle((260,y,260+width,y+height),fill=self.fill(c))
            text(ld,live_fmt(values[c]),(270+width,y+offset),34,color='#222222',bold=False)
        im.paste(layer,(0,220),layer)

    def versus(self,im,d,t,values):
        data=self.data;pair=data['pair'];colors=['#2865B0','#BC3443']
        backgrounds=['#DCEBFA','#F8E1E5']
        for i,c in enumerate(pair):
            x=i*540;v=values[c];accent=colors[i]
            d.rectangle((x,190,x+539,1550),fill=backgrounds[i])
            if data['places'][c].get('iso2'):flag(im,d,c,self.flags,(x+206,230),(128,86))
            name=self.name(c)
            size=48
            while d.textlength(name,font=font(size))>480 and size>20:size-=1
            text(d,name,(x+(540-d.textlength(name,font=font(size)))/2,350),size,color='#151515')
            label=live_fmt(v);size=98
            while d.textlength(label,font=font(size))>480 and size>20:size-=1
            text(d,label,(x+(540-d.textlength(label,font=font(size)))/2,450),size,color=accent)
            count=v/self.unit
            for n in range(48):
                cx=x+85+(n%6)*74;cy=650+(n//6)*105
                fill=accent if n<count else backgrounds[i]
                glyph(d,cx,cy,fill,1.0,data.get('icon','bar'))


def render(data,out,duration=50,mode='Race',music='Auto',style='Auto',seed=42,preview=False):
    flags=load_flags(data,out) if mode=='Versus' else {}
    if mode=='Race':(out/'asset_sources.json').write_text('[]')
    film=Film(data,mode,flags,style);film.duration=duration
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
