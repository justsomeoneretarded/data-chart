import json
import os
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict
import requests

class Scene(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['hook','bars','contrast','takeaway']
    text: str = Field(min_length=5,max_length=120)
    narration: str = Field(min_length=10,max_length=550)
    claim_ids: list[str]
class Story(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=10,max_length=95)
    scenes: list[Scene] = Field(min_length=4,max_length=4)

def facts(data):
    rows=data['rows']; unit=data['unit']
    claims={f'R{i}':f"{r['name']}: {r['value']:,.1f} {unit} ({data['year']})" for i,r in enumerate(rows)}
    claims['D']=data['definition']; claims['L']=data['limitation']
    claims['G']=f"Gap between the first and fifth displayed entries: {rows[0]['value']-rows[4]['value']:,.1f} {unit}."
    return claims

def fallback(data):
    c=facts(data)
    return Story(title=f"What {data['metric'].lower()} rankings really show", scenes=[
        Scene(kind='hook',text='THE RANKING IS ONLY HALF THE STORY',narration=f"Which places lead this measure? Before comparing {data['metric'].lower()}, we need to know what the number actually measures.",claim_ids=['D']),
        Scene(kind='bars',text=f"{data['metric'].upper()}",narration=f"Among reporting countries and territories, {c['R0']}. Next is {c['R1']}. These are the highest five available values in the same year.",claim_ids=['R0','R1','R2','R3','R4']),
        Scene(kind='contrast',text='LOOK AT THE DISTANCE',narration=f"{c['G']} {c['D']} A ranking alone hides both the size of the difference and the meaning of the measure.",claim_ids=['G','D']),
        Scene(kind='takeaway',text='COMPARE THE MEASURE. CHECK THE YEAR.',narration=f"{c['L']} Read these figures as a snapshot of this measure, not a complete verdict on a country. The source and full comparison are included with this video.",claim_ids=['L'])])

def validate_story(story, data):
    c=facts(data)
    if [s.kind for s in story.scenes] != ['hook','bars','contrast','takeaway']:
        raise ValueError('Story must have hook, bars, contrast, takeaway')
    for s in story.scenes:
        if not s.claim_ids or any(k not in c for k in s.claim_ids):
            raise ValueError('Unmapped claim')
        # Free-form model numerical/causal assertions are disallowed. The model may
        # choose presentation text; narration is assembled from reviewed facts below.
        if any(ch.isdigit() for ch in s.text):
            raise ValueError('Heading must not introduce numerical claims')
    return story

def plan(data, mode='ollama'):
    base=fallback(data)
    if mode=='editorial': return base, 'Deterministic editorial fallback (explicit selection)'
    prompt = f'''/no_think\nCreate original short, non-sensational presentation headings and a title for this evidence. Do not invent explanations or numbers. Return the exact supplied JSON structure; keep narration and claim_ids UNCHANGED. Only change title and scene text. Evidence: {json.dumps(facts(data))}. Structure: {base.model_dump_json()}'''
    errors=[]
    for attempt in range(3):
        try:
            r=requests.post(os.getenv('OLLAMA_URL','http://127.0.0.1:11434')+'/api/generate',json={'model':'qwen3:4b','prompt':prompt,'format':Story.model_json_schema(),'stream':False,'think':False,'keep_alive':0,'options':{'temperature':0.6,'num_predict':1800,'num_ctx':4096,'seed':int(os.getenv('SHORTS_SEED','42'))}},timeout=(10,600));r.raise_for_status()
            story=validate_story(Story.model_validate_json(r.json()['response']),data)
            # Authoritative narration is constrained to the audited evidence composer.
            for scene, original in zip(story.scenes,base.scenes):
                scene.narration=original.narration;scene.claim_ids=original.claim_ids
            return story,'Qwen3 4B headings/title; evidence-composed narration'
        except (ValueError,KeyError,requests.RequestException) as exc:
            errors.append(str(exc));prompt+='\nCorrect the schema and do not put numbers in headings.'
    raise RuntimeError('Qwen planning failed after 3 attempts: '+'; '.join(errors))
