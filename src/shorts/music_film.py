"""Orchestrate the visual comparison format independently of speech models."""
import json
import logging
import time
from types import SimpleNamespace
from .general import resolve as retrieve
from .dynamic import render
from .quality import check
from .publishing import metadata,upload


def make(args,out,mode):
    started=time.monotonic()
    def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2))
    logging.info('Retrieving source data for %s',mode)
    data=retrieve(args.brief,out,mode)
    save('research.json',data);save('sources.json',[data['source']])
    save('analysis.json',{'leader_changes':data['leader_changes'],'final_ranking':data['rows'],'pair':data['pair'],'method':'Benchmark animation; see research.json data_kind and limitation for provenance. Display ranks transition between source endpoints.','source_years':data['years'],'coverage_by_year':{y:len(v) for y,v in data['tables'].items()}})
    events=[{'year':r['year'],'code':r['code'],'time':1.2+(r['year']-data['start_year'])/(data['year']-data['start_year'])*(args.duration-3.7)} for r in data['leader_changes']]
    save('storyboard.json',{'format':mode,'start':0,'end':args.duration,'source_years':([] if data.get('category_frames') else data['years']),'categories':data.get('category_frames',[]),'intro_seconds':1.2,'final_hold_seconds':2.5,'data':'dataset.csv','start_year':data['start_year'],'end_year':data['year'],'source_leader_events':events,'icon_unit':data['unit'],'value_per_icon':max(v for table in data['tables'].values() for v in table.values())/40 if any(v for table in data['tables'].values() for v in table.values()) else 1,'narration':False,'camera':'Fixed plain comparison canvas','motion':'Continuous annual interpolation, plain moving bars or icon columns, value counters and year only','safe_area':[24,65,1056,1830]})
    names=[data['places'][c]['name'] for c in data['pair']]
    title=(f"{names[0]} vs {names[1]}: {data['metric']}" if data.get('category_frames') else f"{data['metric']} race: {data['start_year']}–{data['year']}" if mode=='Race' else f"{names[0]} vs {names[1]}: {data['metric']}")[:95]
    meta=metadata(SimpleNamespace(title=title),data,out,narrated=False)
    meta['alt_text']=f"{mode} animation of {data['source']['publisher']} {data['metric']} estimates, {data['start_year']} to {data['year']}. Source benchmark observations are interpolated during motion."
    if data.get('category_frames'):
        meta['alt_text']=f"Category comparison of {names[0]} and {names[1]}; values extracted from quoted web source records."
    save('metadata.json',meta)
    (out/'script.txt').write_text(f"MUSIC-FIRST VISUAL FILM — NO SPOKEN NARRATION\n\n{title}\n\n{data['definition']}\n\n{data['limitation']}")
    logging.info('Rendering %s with original rhythmic background music',mode)
    audio=render(data,out,args.duration,mode,args.music,args.style,args.seed,args.preview)
    logging.info('Running final media quality gates')
    check(out,args.duration,args.preview,captions_required=False,allow_silence=args.music=='None',animation_window=(1.2,args.duration-2.5))
    (out/'production_report.md').write_text(f"# Production report\n\nStatus: generated and technically validated.\n\nFormat: **{mode}**, music-first. Data mode: {data.get('data_kind', 'source observations')}.\n\nReference period: {data['start_year']}–{data['year']}\n\nSource: {data['source']['metadata_url']}\n\nAudio: {'Original procedural electronic score, 124 BPM' if args.music!='None' else 'Intentionally silent'}; uploaded reference audio is not sampled.\n\n{data['limitation']}\n\nElapsed: {time.monotonic()-started:.1f}s\n\nLimitations: Generated simulations are illustrative, not verified historical measurements. Background references are retained separately; licensed portraits and club crests are not included. National flags are optional sourced assets; availability and jurisdiction-specific reuse restrictions are recorded in asset_sources.json. Review editorial value before publishing. No monetization guarantee.\n")
    if args.upload_to_youtube or __import__('os').getenv('INPUT_UPLOAD')=='true':
        if args.preview:raise ValueError('Preview-resolution video may not be uploaded')
        upload(out,meta)
    return data
