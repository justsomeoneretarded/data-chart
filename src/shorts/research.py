"""Shared source HTTP and numerical validation; no topic catalog or keyword gates."""
import math
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class ResearchError(ValueError):
    pass

def session():
    s=requests.Session()
    s.mount('https://',HTTPAdapter(max_retries=Retry(total=3,backoff_factor=1,status_forcelist=[429,500,502,503,504])))
    return s

def validate(rows,bounds):
    seen=set()
    for r in rows:
        key=(r['code'],r['year'])
        if key in seen or not math.isfinite(r['value']) or not bounds[0]<=r['value']<=bounds[1]:
            raise ResearchError('Duplicate, nonfinite, or out-of-range source record')
        seen.add(key)
    if len(rows)<2:raise ResearchError('Fewer than two comparable observations')
    return sorted(rows,key=lambda x:(-x['value'],x['name']))

def research(brief,out):
    from .general import resolve
    data=resolve(brief,out,'Race')
    data['rows']=data['rows'][:5]
    return data
