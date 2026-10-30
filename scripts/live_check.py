"""Bounded, source-attributed live check; isolated from the monitoring database."""
import json
from pathlib import Path
import sys
import tempfile
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from monitor.youtube import api,duration
from monitor.core import connect,import_videos,report
from monitor.export import workbook,markdown

def main():
    now=datetime.now(ZoneInfo('America/Los_Angeles'))
    after=(now-timedelta(days=90)).isoformat()
    search=api('search',part='snippet',type='video',q='Yozma IN-10',maxResults=1,regionCode='US',relevanceLanguage='en',publishedAfter=after)
    if not search.get('items'):raise SystemExit('搜索成功但没有返回小样本，未生成虚假结果')
    details=api('videos',part='snippet,statistics,contentDetails',id=search['items'][0]['id']['videoId'])['items'][0]
    s=details['snippet'];stats=details.get('statistics',{})
    channel=api('channels',part='statistics',id=s['channelId'])['items'][0]
    with tempfile.TemporaryDirectory() as folder:
        db=connect(Path(folder)/'live-check.db')
        import_videos(db,[dict(platform='YouTube',url='https://www.youtube.com/watch?v='+details['id'],title=s['title'],description=s.get('description',''),
            creator=s['channelTitle'],creator_id=s['channelId'],creator_url='https://www.youtube.com/channel/'+s['channelId'],published_at=s['publishedAt'],
            source='YouTube Data API v3 真实小样本验证',market='unknown',language=s.get('defaultAudioLanguage','unknown'),format='unknown',
            duration_seconds=duration(details.get('contentDetails',{}).get('duration')),views=stats.get('viewCount'),likes=stats.get('likeCount'),comments=stats.get('commentCount'),followers=channel['statistics'].get('subscriberCount'))])
        week=(now.date()-timedelta(days=now.weekday())).isoformat();r=report(db,week,scope='all',include_other='1')
        r['data_label']='LIVE CHECK：1条真实API样本，非全网统计，合作关系/所在地/形式未审核'
        out=Path(__file__).resolve().parent.parent/'examples/live-check';out.mkdir(exist_ok=True)
        (out/'live-check.xlsx').write_bytes(workbook(r));(out/'live-check.md').write_text(markdown(r),encoding='utf-8')
        (out/'validation.json').write_text(json.dumps({'status':'passed','checks':['search','video statistics','channel statistics','isolated import','xlsx','markdown'],'video_url':r['videos'][0]['url'],'captured_at':r['generated_at'],'records':1,'production_database_changed':False},ensure_ascii=False,indent=2),encoding='utf-8')
        db.close()
    print('Live API PASS: search/video/channel, one source-attributed record, isolated report exports. No production data changed.')

if __name__=='__main__':main()
