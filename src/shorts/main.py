import argparse
import json
import logging
import os
from pathlib import Path
import platform
import shutil
import sys
import time
import traceback
from .research import research
from .story import plan, facts
from .audio import synthesize,align
from .captions import write
from .visuals import render
from .quality import check
from .publishing import metadata,upload
from .originality import audit,remember

def save(path,value):path.write_text(json.dumps(value,indent=2,ensure_ascii=False))
def parser():
    p=argparse.ArgumentParser(description='Source-grounded World Bank Shorts generator')
    p.add_argument('--brief',default=os.getenv('INPUT_BRIEF'),required=not bool(os.getenv('INPUT_BRIEF')))
    p.add_argument('--duration',type=int,default=int(os.getenv('INPUT_DURATION','50')))
    p.add_argument('--voice',choices=['Warguy','Kit Laser','Female'],default=os.getenv('INPUT_VOICE','Warguy'))
    p.add_argument('--style',choices=['Auto','Cinematic','Minimal','Energetic','Documentary'],default=os.getenv('INPUT_STYLE','Auto'))
    p.add_argument('--music',choices=['Auto','Electronic','Ambient','Cinematic','None'],default=os.getenv('INPUT_MUSIC','Auto'))
    p.add_argument('--seed',type=int,default=int(os.getenv('INPUT_SEED') or 42))
    p.add_argument('--planner',choices=['ollama','editorial'],default='ollama')
    p.add_argument('--engine',choices=['piper','chatterbox','espeak'],default='piper')
    p.add_argument('--asr-model',default='base')
    p.add_argument('--out',type=Path,default=Path('output'))
    p.add_argument('--preview',action='store_true',help='540x960 diagnostic render; not production resolution')
    p.add_argument('--upload-to-youtube',action='store_true')
    return p

def main():
    args=parser().parse_args();out=args.out.resolve();out.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s',handlers=[logging.StreamHandler(),logging.FileHandler(out/'pipeline.log')])
    if any(out.iterdir()) and (out/'video.mp4').exists():raise SystemExit('Output directory already contains a video; choose a fresh directory')
    started=time.monotonic();stage='validation'
    try:
        if not 30<=args.duration<=90:raise ValueError('duration must be 30–90 seconds')
        if not args.brief or not 5<=len(args.brief.strip())<=1000:raise ValueError('brief must contain 5–1000 characters')
        os.environ['SHORTS_SEED']=str(args.seed)
        save(out/'run.json',{'arguments':{**vars(args),'out':str(out)},'cpu_count':os.cpu_count(),'platform':platform.platform(),'disk_free_bytes':shutil.disk_usage(out).free})
        stage='research';logging.info(stage);data=research(args.brief,out)
        save(out/'research.json',data);save(out/'sources.json',[data['source']]);save(out/'analysis.json',{'ranking':data['rows'],'claims':facts(data),'method':'Descending values within one common reference year; excludes regional aggregates and nulls.'})
        stage='story';logging.info(stage);story,planner=plan(data,args.planner)
        originality,history_record=audit(story,args.brief);save(out/'originality_report.json',originality)
        (out/'script.txt').write_text('\n\n'.join(s.narration for s in story.scenes))
        stage='voice';logging.info(stage);scenes,voice=synthesize(story,out,args.voice,args.engine,args.duration)
        save(out/'voice_report.json',voice);save(out/'storyboard.json',scenes)
        stage='speech alignment';logging.info(stage);words=align(scenes,out,args.asr_model);save(out/'alignment.json',words);write(words,out)
        stage='render';logging.info(stage);render(scenes,data,out,args.style,args.music,args.seed,args.preview)
        meta=metadata(story,data,out)
        stage='quality';logging.info(stage);check(out,scenes[-1]['end'],args.preview)
        (out/'production_report.md').write_text(f"# Production report\n\nStatus: generated and technically validated.\n\nPlanner: {planner}\n\nVoice: {voice['engine']}\n\n"+'\n'.join(voice['warnings'])+f"\n\nElapsed: {time.monotonic()-started:.1f}s\n\nSource: {data['source']['metadata_url']}\n\nLimitations: curated World Bank metrics only; no universal research or causal inference. Subjective originality and visual legibility require review. Chatterbox CPU feasibility has not been established on GitHub hosted runners. No monetization guarantee.\n")
        if args.upload_to_youtube or os.getenv('INPUT_UPLOAD')=='true':
            if args.preview or args.engine=='espeak':raise ValueError('Diagnostic preview may not be uploaded')
            stage='youtube upload';upload(out,meta)
        remember(history_record)
        logging.info('Finished: %s',out/'video.mp4')
    except Exception as exc:
        save(out/'failure.json',{'status':'failed','stage':stage,'error':str(exc)})
        (out/'production_report.md').write_text(f'# Generation failed\n\nStage: {stage}\n\n{exc}\n\nNo production success is claimed. Retained intermediate files are diagnostic only.\n')
        logging.exception('Pipeline failed');return 1
    return 0
if __name__=='__main__':sys.exit(main())
