"""Optional YouTube Data API v3 adapter. Never logs keys or raw HTTP errors."""
import json
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .core import CONFIG, import_videos, stamp


def api(resource, **params):
    key = os.environ.get('YOUTUBE_API_KEY')
    if not key:
        raise ValueError('未配置 YOUTUBE_API_KEY；可在 Google Cloud 创建 YouTube Data API 免费配额密钥，无需接入付费采集服务')
    query = urlencode(params)
    try:
        with urlopen(Request('https://www.googleapis.com/youtube/v3/' + resource + '?' + query,
                             headers={'User-Agent': 'CompetitorMonitor/0.1', 'X-Goog-Api-Key': key}), timeout=30) as response:
            return json.load(response)
    except Exception:
        raise RuntimeError('YouTube API 请求失败；请检查网络允许列表、密钥限制、API 启用状态和免费配额。错误 URL 已隐藏以保护密钥。') from None


def collect(db, backfill=False):
    started = stamp()
    count = 0
    try:
        # 6 queries × 100 search units; initial backfill at most 2 pages per query.
        # Deliberately bounded: no guarantee of exhaustive discovery.
        days = CONFIG['history_days'] if backfill else 7
        after = (datetime.now(timezone.utc)-timedelta(days=days)).isoformat().replace('+00:00', 'Z')
        ids = set()
        for query in CONFIG['youtube_queries']:
            token = None
            for _ in range(2 if backfill else 1):
                params = dict(part='snippet', type='video', q=query, maxResults=50,
                              order='date', publishedAfter=after, regionCode='US', relevanceLanguage='en')
                if token:
                    params['pageToken'] = token
                result = api('search', **params)
                ids.update(x['id']['videoId'] for x in result.get('items', []))
                token = result.get('nextPageToken')
                if not token:
                    break
        for row in db.execute("SELECT id FROM videos WHERE platform='YouTube' AND published_at>=?",
                              ((datetime.now(timezone.utc)-timedelta(days=90)).isoformat(),)):
            ids.add(row['id'][3:])
        ids = sorted(ids)
        if len(ids) > 2000:
            raise ValueError('待更新视频超过单次 2000 条上限；请先调整采集范围，未静默丢弃视频')
        for offset in range(0, len(ids), 50):
            videos = api('videos', part='snippet,statistics,contentDetails', id=','.join(ids[offset:offset+50]))
            channels = {v['snippet']['channelId'] for v in videos.get('items', [])}
            channel_data = api('channels', part='statistics', id=','.join(sorted(channels))) if channels else {'items': []}
            followers = {c['id']: c['statistics'].get('subscriberCount') for c in channel_data.get('items', [])}
            for video in videos.get('items', []):
                s, stats = video['snippet'], video.get('statistics', {})
                from .core import identify
                if not identify(s['title'] + '\n' + s.get('description', ''))[0]:
                    continue
                import_videos(db, [dict(platform='YouTube', url='https://www.youtube.com/watch?v='+video['id'],
                    title=s['title'], description=s.get('description', ''), creator=s['channelTitle'],
                    creator_url='https://www.youtube.com/channel/'+s['channelId'], published_at=s['publishedAt'],
                    views=stats.get('viewCount'), likes=stats.get('likeCount'), comments=stats.get('commentCount'),
                    followers=followers.get(s['channelId']), source='YouTube Data API v3',
                    # Search language and region are hints, not proof of account geography.
                    market='unknown', language=s.get('defaultAudioLanguage', 'unknown'), format='unknown')])
                count += 1
        detail = f'更新 {count} 条视频；{days} 天发现窗口，关键词结果有页数上限，不保证全量；地区/长短视频需审核'
        with db:
            db.execute('INSERT INTO runs(started_at,status,detail) VALUES (?,?,?)', (started, 'success', detail))
        return detail
    except Exception as error:
        # Only errors explicitly sanitized above may be persisted.
        detail = str(error) if isinstance(error, (ValueError, RuntimeError)) else '采集失败，请检查配置与响应结构；未记录敏感请求内容'
        with db:
            db.execute('INSERT INTO runs(started_at,status,detail) VALUES (?,?,?)', (started, 'failed', detail))
        raise RuntimeError(detail) from None
