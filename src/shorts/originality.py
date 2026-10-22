"""Advisory comparison with prior successful scripts; no monetization scoring."""
import difflib
import hashlib
import json
from pathlib import Path

def audit(story,brief,history=Path('.history')):
    history.mkdir(exist_ok=True)
    script=' '.join(s.narration for s in story.scenes)
    hook=story.scenes[0].narration
    warnings=[];matches=[]
    for path in sorted(history.glob('*.json'))[-200:]:
        previous=json.loads(path.read_text())
        similarity=difflib.SequenceMatcher(None,script.lower(),previous['script'].lower(),autojunk=False).ratio()
        if similarity>.85 or previous['brief'].strip().lower()==brief.strip().lower():
            matches.append({'previous_file':path.name,'similarity':round(similarity,3)})
        if previous['hook']==hook:warnings.append('Opening narration repeats a previous successful video.')
    if matches:warnings.append('Near-duplicate script or topic found; revise the editorial structure before public publication.')
    warnings.append('This release uses four reusable scene families. Automated checks cannot establish material originality or monetization eligibility.')
    record={'script':script,'hook':hook,'brief':brief}
    return {'advisory':True,'compared_runs':len(list(history.glob('*.json'))),'matches':matches,'warnings':sorted(set(warnings))},record

def remember(record,history=Path('.history')):
    history.mkdir(exist_ok=True)
    digest=hashlib.sha256(record['script'].encode()).hexdigest()
    (history/f'{digest}.json').write_text(json.dumps(record))
