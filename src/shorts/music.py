"""Original deterministic electronic backing track; no reference audio is sampled."""
import wave
import numpy as np

BPM=124

def create(path,duration,seed=42,style='Auto'):
    sr=44100;rng=np.random.default_rng(seed);audio=np.zeros((int(sr*duration),2),np.float64)
    beat=60/BPM
    def place(sound,at,volume=1,pan=0):
        offset=int(at*sr)
        if offset>=len(audio):return
        sound=np.asarray(sound)[:len(audio)-offset]*volume
        audio[offset:offset+len(sound),0]+=sound*(1-pan*.5)
        audio[offset:offset+len(sound),1]+=sound*(1+pan*.5)
    def tone(freq,length):
        t=np.arange(int(sr*length))/sr
        env=np.minimum(t/.008,1)*np.exp(-t*7)
        return (np.sin(2*np.pi*freq*t)+.18*np.sin(4*np.pi*freq*t))*env
    ambient=style=='Ambient'
    for n in range(int(duration/beat)+1):
        t=np.arange(int(sr*.32))/sr
        kick=np.sin(2*np.pi*(47*t+7*(1-np.exp(-t*32))))*np.exp(-t*17)
        if not ambient and (style!='Cinematic' or n%2==0):place(kick,n*beat,.32)
        if n%2==1 and not ambient:
            t=np.arange(int(sr*.16))/sr;noise=rng.normal(size=len(t));clap=np.diff(noise,prepend=0)*np.exp(-t*32)
            place(clap,n*beat,.032)
        root=[55,43.65,65.41,49][(n//8)%4]
        place(tone(root,beat*.72),n*beat+.035,.13)
        if n%2==0:
            for j,mult in enumerate([4,6,5,8]):place(tone(root*mult,beat*.43),n*beat+j*beat/2,.027,(-1)**j*.5)
    if not ambient and style!='Cinematic':
        for n in range(int(duration/(beat/2))):
            t=np.arange(int(sr*.055))/sr;noise=rng.normal(size=len(t));hat=np.diff(noise,prepend=0)*np.exp(-t*80)
            place(hat,n*beat/2,.014 if n%2 else .009,(-1)**n*.55)
    # Broad quiet pads glue the percussion and arpeggios together.
    t=np.arange(len(audio))/sr
    for frequency in [110,130.81,164.81]:
        pad=np.sin(2*np.pi*frequency*t)*.012*(.7+.3*np.sin(2*np.pi*.12*t))
        audio[:,0]+=pad;audio[:,1]+=pad
    fade=np.minimum(t/1.1,1)*np.minimum((duration-t)/1.8,1)
    audio=np.tanh(audio*1.3)*fade[:,None]
    peak=np.max(np.abs(audio))
    if peak:audio*=.82/peak
    with wave.open(str(path),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(sr);f.writeframes((audio*32767).astype('<i2').tobytes())
    return {'composer':'Original procedural electronic score','bpm':BPM,'seed':seed,'reference_audio_used':False,'license':'Generated from project code; no third-party samples','style':style}


def prepare(out, duration: float, seed: int, style: str):
    """Pick background music: a track from assets/music/ if any exist, else the procedural score.

    Drop royalty-free tracks (e.g. from the YouTube Audio Library) into assets/music/
    once; every run then picks one by seed, trims it and fades it out.
    """
    import random
    import subprocess
    from pathlib import Path

    tracks = sorted(p for p in (Path(__file__).resolve().parents[2] / "assets" / "music").glob("*")
                    if p.suffix.lower() in {".mp3", ".wav", ".m4a", ".ogg", ".flac"})
    path = out / "music.wav"
    if tracks and style != "Procedural":
        track = random.Random(seed).choice(tracks)
        fade = max(0.0, duration - 2.0)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(track), "-t", str(duration),
                        "-af", f"afade=t=in:d=0.8,afade=t=out:st={fade}:d=2,loudnorm=I=-16:TP=-1.5",
                        "-ar", "44100", "-ac", "2", str(path)], check=True)
        return {"source": "library", "file": track.name, "note": "Royalty-free track from assets/music; check its license"}
    info = create(path, duration, seed, "Auto" if style in ("Auto", "Procedural") else style)
    info["source"] = "procedural"
    return info
