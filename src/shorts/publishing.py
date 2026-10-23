import hashlib
import json
import os
from pathlib import Path

def metadata(story,data,out,narrated=True):
    title=story.title
    description=f"{title}\n\n{data['definition']}\n\nSource: {data['source'].get('publisher','World Bank')} — {data['metric']}, reference year {data['year']}.\n{data['source']['metadata_url']}\n\n{data['limitation']}\n{('Narration is synthesized.' if narrated else 'Original procedural background music; no narration.')} {('Values are simulated for illustration.' if data.get('data_kind')=='simulation' else 'Charts preserve published values; figures may be revised.')}\n#Shorts #DataVisualization"
    if data.get('category_frames'):
        description=f"{title}\n\n{data['definition']}\n\nSource snapshots; retrieval year {data['reference_year']} is not an observation date.\n{data['limitation']}\n"+'\n'.join(p['url'] for p in data['source'].get('pages',[]))+'\nOriginal procedural music; no narration.'
    if data['source'].get('attribution'):description+='\n\n'+data['source']['attribution']
    meta={'title':title,'description':description,'tags':[data['metric'],'data visualization',data['source'].get('publisher','World Bank')],'categoryId':'27','language':'en','privacyStatus':'private','containsSyntheticMedia':True,'madeForKids':False,'pinned_comment':f"Source and definitions: {data['source']['metadata_url']}. {data['limitation']}",'alt_text':f"Animated comparison of the five highest available {data['metric']} values in {data['year']}.",'review_flags':['Review synthetic-content disclosure and audience settings before upload.']}
    for name,text in [('youtube_title.txt',title),('youtube_description.txt',description),('keywords.txt',', '.join(meta['tags'])),('pinned_comment.txt',meta['pinned_comment'])]:(out/name).write_text(text)
    (out/'metadata.json').write_text(json.dumps(meta,indent=2))
    return meta

def upload(out,meta):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    # A stable run key plus an existing upload manifest prevents retries from
    # duplicating local uploads. Remote marker search covers lost local state.
    creds=Credentials(token=None,refresh_token=os.environ['YOUTUBE_REFRESH_TOKEN'],token_uri='https://oauth2.googleapis.com/token',client_id=os.environ['YOUTUBE_CLIENT_ID'],client_secret=os.environ['YOUTUBE_CLIENT_SECRET'])
    creds.refresh(Request());yt=build('youtube','v3',credentials=creds,cache_discovery=False)
    marker='data-chart-run:'+os.environ.get('GITHUB_RUN_ID',hashlib.sha256((out/'video.mp4').read_bytes()).hexdigest())
    manifest=out/'youtube_upload.json'
    if manifest.exists():return
    channel=yt.channels().list(part='contentDetails',mine=True).execute()['items'][0]
    playlist=channel['contentDetails']['relatedPlaylists']['uploads']
    recent=yt.playlistItems().list(part='snippet',playlistId=playlist,maxResults=50).execute()
    if any(marker in item['snippet'].get('description','') for item in recent.get('items',[])):
        raise RuntimeError('This run already appears in recent uploads; refusing duplicate upload')
    request=yt.videos().insert(part='snippet,status',body={'snippet':{'title':meta['title'],'description':meta['description']+'\n\n'+marker,'tags':meta['tags'],'categoryId':'27','defaultLanguage':'en'},'status':{'privacyStatus':'private','selfDeclaredMadeForKids':False,'containsSyntheticMedia':True}},media_body=MediaFileUpload(str(out/'video.mp4'),chunksize=8*1024*1024,resumable=True))
    response=None
    while response is None:_,response=request.next_chunk(num_retries=3)
    manifest.write_text(json.dumps({'video_id':response['id'],'privacy':'private','marker':marker},indent=2))
