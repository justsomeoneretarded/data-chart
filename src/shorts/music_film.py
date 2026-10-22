"""Orchestrate the visual comparison format independently of speech models."""
import json
import logging
import time
from types import SimpleNamespace
from .history import retrieve
from .dynamic import render
from .quality import check
from .publishing import metadata,upload


def make(args,out,mode):
    started=time.monotonic()
    def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    logging.info('Retrieving annual source data for %s',mode)
    data=retrieve(args.brief,out,mode)
    save('research.json',data);save('sources.json',[data['source']])
    save('analysis.json',{'leader_changes':data['leader_changes'],'final_ranking':data['rows'],'pair':data['pair'],'method':'Actual annual observations; linear interpolation only between adjacent years with both values observed. Display ranks transition between annual endpoint ranks.','coverage_by_year':{y:len(v) for y,v in data['tables'].items()}})
    events=[{'year':r['year'],'code':r['code'],'time':1.2+(r['year']-data['start_year'])/(data['year']-data['start_year'])*(args.duration-3.7)} for r in data['leader_changes']]
    save('storyboard.json',{'format':mode,'start':0,'end':args.duration,'intro_seconds':1.2,'final_hold_seconds':2.5,'data':'dataset.csv','start_year':data['start_year'],'end_year':data['year'],'leader_events':events,'narration':False,'camera':'Fixed readable information plane; moving depth particles','motion':'Continuous annual interpolation, smoothly changing ranks, value counters, icon accumulation, beat meter','safe_area':[48,105,1032,1808]})
    names=[data['places'][c]['name'] for c in data['pair']]
    title=(f"{data['metric']}: {data['start_year']}–{data['year']} | The changing leaders" if mode=='Race' else f"{names[0]} vs {names[1]}: {data['metric']}")[:95]
    meta=metadata(SimpleNamespace(title=title),data,out,narrated=False)
    meta['alt_text']=f"{mode} animation of World Bank {data['metric']} observations, {data['start_year']} to {data['year']}. Annual observations are interpolated during motion."
    save('metadata.json',meta)
    (out/'script.txt').write_text(f"MUSIC-FIRST VISUAL FILM — NO SPOKEN NARRATION\n\n{title}\n\n{data['definition']}\n\n{data['limitation']}")
    logging.info('Rendering %s with original rhythmic background music',mode)
    audio=render(data,out,args.duration,mode,args.music,args.style,args.seed,args.preview)
    logging.info('Running final media quality gates')
    check(out,args.duration,args.preview,captions_required=False,allow_silence=args.music=='None')
    (out/'production_report.md').write_text(f"# Production report\n\nStatus: generated and technically validated.\n\nFormat: **{mode}**, music-first. No speech models or AI-generated measurements are used.\n\nReference period: {data['start_year']}–{data['year']}\n\nSource: {data['source']['metadata_url']}\n\nAudio: {'Original procedural electronic score, 124 BPM' if args.music!='None' else 'Intentionally silent'}; uploaded reference audio is not sampled.\n\n{data['limitation']}\n\nElapsed: {time.monotonic()-started:.1f}s\n\nLimitations: only the implemented World Bank metrics are supported. This does not research football trophies or obtain licensed athlete portraits. National flags are optional sourced assets; availability and jurisdiction-specific reuse restrictions are recorded in asset_sources.json. Review editorial value before publishing. No monetization guarantee.\n")
    if args.upload_to_youtube or __import__('os').getenv('INPUT_UPLOAD')=='true':
        if args.preview:raise ValueError('Preview-resolution video may not be uploaded')
        upload(out,meta)
    return data
