from pathlib import Path

def stamp(t,ass=False):
    cs=round(t*(100 if ass else 1000));base=100 if ass else 1000
    h,cs=divmod(cs,3600*base);m,cs=divmod(cs,60*base);s,cs=divmod(cs,base)
    return f'{h}:{m:02}:{s:02}.{cs:02}' if ass else f'{h:02}:{m:02}:{s:02},{cs:03}'
def escape(text): return text.replace('\\','').replace('{','').replace('}','').replace('\n',' ')
def write(words,out):
    groups=[words[i:i+5] for i in range(0,len(words),5)]
    srt=[];vtt=['WEBVTT\n'];ass=['''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Default,DejaVu Sans,52,&H00FFFFFF,&H0000D9FC,&H00151A24,&H80000000,-1,0,0,0,100,100,0,0,1,3,0,2,100,160,340,1
[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text''']
    previous=0
    for i,g in enumerate(groups):
        start=max(previous,g[0]['start']);end=g[-1]['end'];previous=end
        if end<=start:continue
        text=' '.join(w['text'] for w in g)
        srt.append(f'{i+1}\n{stamp(start)} --> {stamp(end)}\n{text}\n')
        vtt.append(f'{stamp(start).replace(",",".")} --> {stamp(end).replace(",",".")}\n{text}\n')
        karaoke=''.join(f'{{\\kf{max(1,round((w["end"]-w["start"])*100))}}}{escape(w["text"])} ' for w in g)
        ass.append(f'Dialogue: 0,{stamp(start,True)},{stamp(end,True)},Default,,0,0,0,,{{\\fad(80,80)}}{karaoke}')
    for ext,content in [('srt',srt),('vtt',vtt),('ass',ass)]: (out/f'subtitles.{ext}').write_text('\n'.join(content))
