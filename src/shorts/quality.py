import json
import subprocess
from .audio import run

def check(out,expected,preview=False,captions_required=True,allow_silence=False):
    r=subprocess.run(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(out/'video.mp4')],check=True,capture_output=True,text=True)
    probe=json.loads(r.stdout);video=next(s for s in probe['streams'] if s['codec_type']=='video');audio=next(s for s in probe['streams'] if s['codec_type']=='audio')
    tests={'h264':video['codec_name']=='h264','aac':audio['codec_name']=='aac','resolution':(video['width'],video['height'])==((540,960) if preview else (1080,1920)),'duration':abs(float(probe['format']['duration'])-expected)<1,'av_sync':abs(float(video['duration'])-float(audio['duration']))<.25,'nonempty':(out/'video.mp4').stat().st_size>10000,'subtitles':not captions_required or all((out/f'subtitles.{e}').stat().st_size>50 for e in ['srt','vtt','ass'])}
    scan=subprocess.run(['ffmpeg','-hide_banner','-i',str(out/'video.mp4'),'-vf','blackdetect=d=0.5:pix_th=0.02,freezedetect=n=-65dB:d=3','-af','silencedetect=n=-45dB:d=4','-f','null','-'],capture_output=True,text=True,timeout=600)
    tests['decode']=scan.returncode==0
    tests['no_black_sequences']='black_start:' not in scan.stderr
    tests['no_frozen_sequences']='freeze_start:' not in scan.stderr
    tests['no_long_silence']=allow_silence or 'silence_start:' not in scan.stderr
    (out/'ffmpeg_qa.log').write_text(scan.stderr)
    report={'captions_required':captions_required,'intentional_silence':allow_silence,'passed':all(tests.values()),'checks':tests,'warnings':['Visual label collisions and editorial originality require human review. Automated checks do not establish monetization eligibility.'],'probe':probe}
    (out/'quality_report.json').write_text(json.dumps(report,indent=2))
    if not report['passed']:raise ValueError('Quality gate failed: '+str([k for k,v in tests.items() if not v]))
    return report
