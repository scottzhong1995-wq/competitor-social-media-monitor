"""YouTube adapter: bounded discovery, safe retries, never log credentials."""
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from .core import import_videos, stamp, identify
from .settings import load


def api(resource, **params):
    key=os.environ.get('YOUTUBE_API_KEY')
    if not key:
        raise ValueError('未配置 YOUTUBE_API_KEY；可使用 YouTube Data API 免费配额密钥')
    query=urlencode(params)
    for attempt in range(3):
        try:
            req=Request('https://www.googleapis.com/youtube/v3/'+resource+'?'+query,
                        headers={'User-Agent':'CompetitorMonitor/2','X-Goog-Api-Key':key})
            with urlopen(req,timeout=25) as r:
                return json.load(r)
        except HTTPError as e:
            # Only numeric status + a fixed set of reason codes may enter logs.
            reason='requestDenied'
            try:
                codes=[x.get('reason') for x in json.loads(e.read()).get('error',{}).get('errors',[])]
                reason=next((c for c in codes if c in {'quotaExceeded','dailyLimitExceeded','keyInvalid','accessNotConfigured','forbidden','rateLimitExceeded'}),reason)
            except (ValueError,AttributeError,TypeError):
                pass
            if (e.code==429 or e.code>=500 or reason=='rateLimitExceeded') and attempt<2:
                try: delay=min(30,max(.25,float(e.headers.get('Retry-After',2**attempt))))
                except (ValueError,TypeError): delay=2**attempt
                time.sleep(delay);continue
            raise RuntimeError(f'YouTube HTTP {e.code} / {reason}；保留旧数据，请检查网络、启用状态、限制或免费配额') from None
        except Exception:
            if attempt<2:
                time.sleep(.25*(2**attempt));continue
            raise RuntimeError('YouTube 网络/响应异常；重试3次失败，未记录密钥或原始请求。保留旧数据。') from None


def duration(value):
    match=re.fullmatch(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?',value or '')
    return sum(int(x or 0)*unit for x,unit in zip(match.groups(),(3600,60,1))) if match else None


def collect(db, backfill=False):
    config=load();started=stamp();count=0
    try:
        if 'YouTube' not in config['platforms']:
            raise ValueError('YouTube 平台当前已停用')
        days=config['history_days'] if backfill else 7
        after=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat().replace('+00:00','Z')
        ids=set();baseline_ids=set()
        for query in config['youtube_queries']:
            pages=0;found=set();token=None
            try:
                for _ in range(min(10,int(config.get('youtube_max_pages',2))) if backfill else 1):
                    params=dict(part='snippet',type='video',q=query,maxResults=50,order='date',publishedAfter=after,
                                regionCode=config['countries'][0] if config['countries'] else 'US',
                                relevanceLanguage=config['languages'][0] if config['languages'] else 'en')
                    if token: params['pageToken']=token
                    result=api('search',**params);pages+=1
                    found.update(i['id']['videoId'] for i in result.get('items',[]))
                    token=result.get('nextPageToken')
                    if not token:break
                ids.update(found)
                with db: db.execute('INSERT INTO queries(run_at,query,pages,discovered,status) VALUES (?,?,?,?,?)',(started,query,pages,len(found),'page_limit' if token else 'completed'))
            except (ValueError,RuntimeError):
                with db: db.execute('INSERT INTO queries(run_at,query,pages,discovered,status) VALUES (?,?,?,?,?)',(started,query,pages,len(found),'failed'))
                raise
        # Explicitly added videos are refreshed; manual monitor accounts discover uploads.
        for row in db.execute("SELECT id FROM videos WHERE platform='YouTube' AND published_at>=?",((datetime.now(timezone.utc)-timedelta(days=config['history_days'])).isoformat(),)):
            ids.add(row['id'][3:])
        for row in db.execute("SELECT * FROM creators WHERE platform='YouTube'"):
            profile=json.loads(row['profile'])
            aid=row['account_id'].split('/')[-1]
            if profile.get('monitor') and re.fullmatch(r'UC[\w-]{22}',aid):
                result=api('search',part='snippet',type='video',channelId=aid,maxResults=12,order='date',publishedAfter=after)
                account_ids={i['id']['videoId'] for i in result.get('items',[])}
                ids.update(account_ids);baseline_ids.update(account_ids)
                with db:db.execute('INSERT INTO queries(run_at,query,pages,discovered,status) VALUES (?,?,?,?,?)',(started,'channel:'+aid,1,len(result.get('items',[])),'account_latest_12_limit'))
        ids=sorted(ids)
        if len(ids)>2000:raise ValueError('单次超过2000条上限，请调整范围；没有静默丢弃')
        for offset in range(0,len(ids),50):
            batch=ids[offset:offset+50]
            result=api('videos',part='snippet,statistics,contentDetails',id=','.join(batch))
            returned={v['id'] for v in result.get('items',[])}
            with db:
                for absent in set(batch)-returned:
                    db.execute("UPDATE videos SET availability='unavailable',last_checked_at=? WHERE id=?",(stamp(),'yt:'+absent))
            channelids={v['snippet']['channelId'] for v in result.get('items',[])}
            channels=api('channels',part='statistics',id=','.join(sorted(channelids))) if channelids else {'items':[]}
            followers={c['id']:c['statistics'].get('subscriberCount') for c in channels.get('items',[])}
            for v in result.get('items',[]):
                s,stats=v['snippet'],v.get('statistics',{})
                known=db.execute('SELECT id FROM videos WHERE id=?',('yt:'+v['id'],)).fetchone()
                matches_brand=bool(identify(s['title']+'\n'+s.get('description',''))[0])
                if not matches_brand and not known and v['id'] not in baseline_ids:continue
                item=dict(platform='YouTube',url='https://www.youtube.com/watch?v='+v['id'],title=s['title'],description=s.get('description',''),creator=s['channelTitle'],
                    creator_id=s['channelId'],creator_url='https://www.youtube.com/channel/'+s['channelId'],published_at=s['publishedAt'],
                    views=stats.get('viewCount'),likes=stats.get('likeCount'),comments=stats.get('commentCount'),followers=followers.get(s['channelId']),source='YouTube Data API v3',
                    market='unknown',language=s.get('defaultAudioLanguage','unknown'),format='unknown',duration_seconds=duration(v.get('contentDetails',{}).get('duration')))
                if not matches_brand and not known:item['baseline_only']=True
                import_videos(db,[item])
                with db:db.execute("UPDATE videos SET availability='active' WHERE id=?",('yt:'+v['id'],))
                count+=1
        detail=f'更新 {count} 条；发现窗口 {days} 天；仅 {config["youtube_queries"]} 和手动监控账号，分页/账号最新12条有上限；国家和Shorts需审核'
        with db:db.execute('INSERT INTO runs(started_at,status,detail) VALUES (?,?,?)',(started,'success',detail))
        return detail
    except Exception as e:
        detail=str(e) if isinstance(e,(ValueError,RuntimeError)) else '采集处理异常；旧数据保留，未记录敏感响应'
        with db:db.execute('INSERT INTO runs(started_at,status,detail) VALUES (?,?,?)',(started,'failed',detail))
        raise RuntimeError(detail) from None
