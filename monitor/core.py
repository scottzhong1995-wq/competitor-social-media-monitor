from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import sqlite3
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / 'config/brands.json').read_text())
UTC = timezone.utc
LA = ZoneInfo(CONFIG['report_timezone'])


def stamp(value=None):
    if value is None:
        return datetime.now(UTC).isoformat()
    dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('时间必须包含时区，例如 2026-10-20T12:00:00Z')
    return dt.astimezone(UTC).isoformat()


def connect(path=None):
    p = Path(path or os.environ.get('MONITOR_DB', ROOT / 'data/monitor.db'))
    p.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(p, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS videos (
      id TEXT PRIMARY KEY, platform TEXT NOT NULL, url TEXT NOT NULL,
      title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '',
      creator TEXT NOT NULL, creator_url TEXT NOT NULL DEFAULT '',
      published_at TEXT NOT NULL, discovered_at TEXT NOT NULL,
      format TEXT NOT NULL, brands TEXT NOT NULL, models TEXT NOT NULL,
      direction TEXT NOT NULL, keywords TEXT NOT NULL, cooperation TEXT NOT NULL,
      evidence TEXT NOT NULL, source TEXT NOT NULL, market TEXT NOT NULL,
      language TEXT NOT NULL, creator_type TEXT NOT NULL DEFAULT '',
      contact TEXT NOT NULL DEFAULT '', contact_source TEXT NOT NULL DEFAULT '',
      content_group TEXT NOT NULL DEFAULT '', review_note TEXT NOT NULL DEFAULT '',
      reviewed_at TEXT);
    CREATE TABLE IF NOT EXISTS snapshots (
      video_id TEXT NOT NULL REFERENCES videos(id), observed_at TEXT NOT NULL,
      views INTEGER, likes INTEGER, comments INTEGER, followers INTEGER,
      source TEXT NOT NULL, PRIMARY KEY(video_id, observed_at));
    CREATE TABLE IF NOT EXISTS trends (
      series_id TEXT NOT NULL, query TEXT NOT NULL, week TEXT NOT NULL,
      value REAL NOT NULL, source TEXT NOT NULL,
      PRIMARY KEY(series_id, query, week));
    CREATE TABLE IF NOT EXISTS runs (
      id INTEGER PRIMARY KEY, started_at TEXT NOT NULL, status TEXT NOT NULL,
      detail TEXT NOT NULL);
    ''')
    return db


def identify(text):
    text = text.lower()
    brands, models = [], []
    for brand in CONFIG['brands']:
        matches = []
        remaining = text
        for model in brand['models']:
            found = False
            for alias in sorted(model['aliases'], key=len, reverse=True):
                pattern = r'(?<![a-z0-9])' + re.escape(alias) + r'(?![a-z0-9])'
                if re.search(pattern, remaining):
                    found = True
                    remaining = re.sub(pattern, ' ', remaining)
            if found:
                matches.append(model['name'])
        if re.search(r'\b' + brand['name'].lower() + r'\b', text) or matches:
            brands.append(brand['name'])
            models.extend(matches)
    return brands, models


def classify(title, description):
    text = (title + '\n' + description).lower()
    directions = [label for pattern, label in [
        (r'unbox|assembl|setup', '开箱/组装'), (r'review|honest|verdict', '评测'),
        (r'off.?road|trail|dirt|motocross', '越野'), (r'hill|climb', '爬坡'),
        (r'top speed|mph|speed test', '速度实测'), (r'range|battery test', '续航实测'),
        (r'\bvs\b|versus|compar', '竞品对比'), (r'first ride', '首次骑行')
    ] if re.search(pattern, text)] or ['待分类']
    keywords = [w for w in re.findall(r'[a-z0-9]+(?:-[a-z0-9]+)*', title.lower())
                if w not in {'the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'is', 'it', 'for', 'my', 'this', 'on', 'with'}]
    clues = []
    for pattern, label in [
        (r'sponsored|paid partnership|paid promotion|#ad\b', '赞助披露线索'),
        (r'sent me|sent us|gifted|provided.{0,30}(bike|review)', '赠品/送测线索'),
        (r'affiliate|commission', '联盟线索'),
        (r'discount code|coupon|use.{0,15}code', '折扣码线索')
    ]:
        match = re.search(pattern, text)
        if match:
            clues.append(label + '：' + text[max(0, match.start()-35):match.end()+90].replace('\n', ' '))
    return directions, list(dict.fromkeys(keywords))[:15], clues


def canonical(platform, url):
    p = urlparse(url)
    host = (p.hostname or '').lower().removeprefix('www.')
    if p.scheme != 'https' or p.username or p.password or p.port not in (None, 443):
        raise ValueError('视频链接必须为对应平台的 HTTPS 地址')
    if platform == 'YouTube' and host in {'youtube.com', 'm.youtube.com', 'youtu.be'}:
        if host == 'youtu.be':
            key = p.path.strip('/')
        elif p.path.startswith(('/shorts/', '/live/')):
            key = p.path.split('/')[2]
        else:
            key = parse_qs(p.query).get('v', [''])[0]
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}', key):
            raise ValueError('无效的 YouTube 视频 ID')
        return 'yt:' + key, 'https://www.youtube.com/watch?v=' + key
    if platform == 'Instagram' and host == 'instagram.com':
        match = re.fullmatch(r'/(?:reel|reels|p)/([\w-]+)/?', p.path)
        if match:
            return 'ig:' + match[1], 'https://www.instagram.com/reel/' + match[1] + '/'
    if platform == 'TikTok' and host == 'tiktok.com':
        match = re.fullmatch(r'/(@[\w.-]+)/video/(\d+)/?', p.path)
        if match:
            return 'tt:' + match[2], f'https://www.tiktok.com/{match[1]}/video/{match[2]}'
    raise ValueError('需要 YouTube、Instagram 或 TikTok 的完整视频链接（不支持短链接跳转）')


def number(value):
    if value in (None, ''):
        return None
    if isinstance(value, bool) or not str(value).isdigit():
        raise ValueError('账号及互动数据必须为非负整数；未知请留空')
    return int(value)


def import_videos(db, items):
    if not isinstance(items, list) or not 1 <= len(items) <= 5000:
        raise ValueError('请导入包含 1 至 5000 条记录的 JSON 数组')
    now = stamp()
    with db:
        for item in items:
            platform = item['platform']
            vid, url = canonical(platform, item['url'])
            title, creator = str(item['title']).strip(), str(item['creator']).strip()
            if not title or not creator or not item.get('source'):
                raise ValueError('标题、红人账号和数据来源不能为空')
            published = stamp(item['published_at'])
            observed = stamp(item.get('observed_at', now))
            if published > now or observed > now or observed < published:
                raise ValueError('发布时间或观测时间无效：不可在未来，观测不可早于发布')
            description = str(item.get('description', ''))
            brands, models = identify(title + '\n' + description)
            if not brands:
                raise ValueError('标题或描述需包含 Yozma、Tuttio 或重点车型')
            directions, keywords, clues = classify(title, description)
            cooperation = item.get('cooperation', '线索待核实' if clues else '普通提及')
            if cooperation not in {'明确合作', '线索待核实', '普通提及', '排除'}:
                raise ValueError('未知的合作状态')
            evidence = str(item.get('evidence', '\n'.join(clues)))
            if cooperation == '明确合作' and not evidence.strip():
                raise ValueError('确认合作必须填写披露证据')
            fmt = item.get('format', 'unknown')
            if fmt not in {'long', 'short', 'unknown'}:
                raise ValueError('format 必须为 long、short 或 unknown')
            contact = str(item.get('contact', ''))
            if contact and not item.get('contact_source'):
                raise ValueError('联系方式必须附公开来源链接')
            row = dict(id=vid, platform=platform, url=url, title=title, description=description,
                       creator=creator, creator_url=str(item.get('creator_url', '')),
                       published_at=published, discovered_at=now, format=fmt,
                       brands=json.dumps(brands), models=json.dumps(models),
                       direction=json.dumps(directions), keywords=json.dumps(keywords),
                       cooperation=cooperation, evidence=evidence, source=str(item['source']),
                       market=str(item.get('market', 'unknown')).upper() if item.get('market') not in (None, 'unknown') else 'unknown',
                       language=str(item.get('language', 'unknown')).lower().split('-')[0],
                       creator_type=str(item.get('creator_type', '')), contact=contact,
                       contact_source=str(item.get('contact_source', '')),
                       content_group=str(item.get('content_group', '')))
            old = db.execute('SELECT * FROM videos WHERE id=?', (vid,)).fetchone()
            # Refresh statistics/metadata without erasing manually reviewed decisions.
            if old:
                for field in ('cooperation', 'evidence', 'format', 'market', 'language', 'contact',
                              'contact_source', 'creator_type', 'content_group'):
                    if old['reviewed_at'] or field not in item:
                        row[field] = old[field]
            fields = list(row)
            updates = ','.join(f'{k}=excluded.{k}' for k in fields if k not in {'id', 'discovered_at'})
            db.execute(f"INSERT INTO videos ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)}) "
                       f'ON CONFLICT(id) DO UPDATE SET {updates}', list(row.values()))
            values = [number(item.get(k)) for k in ('views', 'likes', 'comments', 'followers')]
            db.execute('INSERT INTO snapshots VALUES (?,?,?,?,?,?,?) ON CONFLICT(video_id,observed_at) '
                       'DO UPDATE SET views=excluded.views,likes=excluded.likes,comments=excluded.comments,'
                       'followers=excluded.followers,source=excluded.source',
                       [vid, observed, *values, str(item['source'])])
    return len(items)


def review(db, item):
    vid = item['id']
    if not db.execute('SELECT 1 FROM videos WHERE id=?', (vid,)).fetchone():
        raise ValueError('视频不存在')
    status = item['cooperation']
    if status not in {'明确合作', '线索待核实', '普通提及', '排除'}:
        raise ValueError('无效的合作状态')
    if status == '明确合作' and not str(item.get('evidence', '')).strip():
        raise ValueError('确认合作必须填写证据')
    if item.get('format') not in {'long', 'short', 'unknown'}:
        raise ValueError('无效的内容格式')
    with db:
        db.execute('UPDATE videos SET cooperation=?,evidence=?,format=?,market=?,language=?,review_note=?,reviewed_at=? WHERE id=?',
                   (status, item.get('evidence', ''), item['format'], item.get('market', 'unknown'),
                    item.get('language', 'unknown'), item.get('review_note', ''), stamp(), vid))


def week_bounds(week=None, now=None):
    today = (now or datetime.now(UTC)).astimezone(LA).date()
    monday = date.fromisoformat(week) if week else today - timedelta(days=today.weekday()+7)
    if monday.weekday() != 0:
        raise ValueError('周起始日期必须为周一')
    start = datetime.combine(monday, time(), LA)
    return start.astimezone(UTC), (start + timedelta(days=7)).astimezone(UTC)


def report(db, week=None):
    start, end = week_bounds(week)
    now = datetime.now(UTC)
    cutoff = min(now, end)
    selected, creators, grouping = [], {}, Counter()
    # No assumed zero baseline. Historical snapshots never get overwritten.
    for raw in db.execute('SELECT * FROM videos ORDER BY published_at DESC'):
        v = dict(raw)
        if not cutoff - timedelta(days=CONFIG['history_days']) <= datetime.fromisoformat(v['published_at']) < cutoff:
            continue
        for k in ('brands', 'models', 'direction', 'keywords'):
            v[k] = json.loads(v[k])
        snaps = [dict(s) for s in db.execute('SELECT * FROM snapshots WHERE video_id=? AND observed_at<? ORDER BY observed_at', (v['id'], cutoff.isoformat()))]
        latest = snaps[-1] if snaps else {}
        before = [s for s in snaps if s['observed_at'] <= start.isoformat() and s['views'] is not None]
        inside = [s for s in snaps if s['observed_at'] >= start.isoformat() and s['views'] is not None]
        # Only compute observed-window growth, and expose its exact coverage.
        baseline = before[-1] if before else (inside[0] if inside else None)
        measured = [s for s in snaps if s['views'] is not None]
        last_measured = measured[-1] if measured else None
        delta = (last_measured['views'] - baseline['views']) if baseline and last_measured and baseline['observed_at'] != last_measured['observed_at'] else None
        v.update(views=latest.get('views'), likes=latest.get('likes'), comments=latest.get('comments'),
                 followers=latest.get('followers'), observed_at=latest.get('observed_at'), metric_source=latest.get('source'),
                 observed_growth=delta, growth_from=baseline['observed_at'] if baseline else None,
                 growth_to=last_measured['observed_at'] if last_measured else None,
                 metric_correction=delta is not None and delta < 0,
                 new_in_week=start.isoformat() <= v['published_at'] < end.isoformat(),
                 discovered_in_week=start.isoformat() <= v['discovered_at'] < end.isoformat())
        v['target_market'] = v['market'] == 'US' and v['language'] == 'en'
        v['viral_candidate'] = bool(v['views'] is not None and v['views'] >= CONFIG['viral_candidate_views'][v['format']])
        v['viral_reason'] = f"累计播放达到 {CONFIG['viral_candidate_views'][v['format']]:,}；需人工分析内容与流量来源" if v['viral_candidate'] else ''
        selected.append(v)
        creator_key = (v['platform'], v['creator_url'] or v['creator'])
        if creator_key not in creators:
            creators[creator_key] = {k: v[k] for k in ('platform', 'creator', 'creator_url', 'followers', 'creator_type', 'contact', 'contact_source', 'observed_at')}
            creators[creator_key].update(videos=0, confirmed=0)
        c = creators[creator_key]
        c['videos'] += 1
        c['confirmed'] += v['cooperation'] == '明确合作'
        if (v['observed_at'] or '') > (c['observed_at'] or ''):
            for key in ('followers', 'observed_at'):
                c[key] = v[key]
        for key in ('contact', 'contact_source', 'creator_type'):
            if v[key]:
                c[key] = v[key]
        if v['new_in_week'] and v['target_market'] and v['cooperation'] == '明确合作':
            grouping[(v['platform'], v['format'])] += 1
    confirmed = [v for v in selected if v['new_in_week'] and v['target_market'] and v['cooperation'] == '明确合作']
    counts = []
    for (platform, fmt), count in sorted(grouping.items()):
        rows = [v for v in confirmed if v['platform'] == platform and v['format'] == fmt]
        known = [v['views'] for v in rows if v['views'] is not None]
        counts.append(dict(platform=platform, format=fmt, videos=count, views=sum(known) if known else None, measured=len(known)))
    trend_rows = [dict(r) for r in db.execute('SELECT * FROM trends WHERE week>=? AND week<? ORDER BY series_id,query,week',
                 ((start.astimezone(LA).date()-timedelta(days=90)).isoformat(), end.astimezone(LA).date().isoformat()))]
    for t in trend_rows:
        previous_week = (date.fromisoformat(t['week'])-timedelta(days=7)).isoformat()
        prev = db.execute('SELECT value FROM trends WHERE series_id=? AND query=? AND week=?', (t['series_id'], t['query'], previous_week)).fetchone()
        t['change_percent'] = round((t['value']/prev['value']-1)*100, 1) if prev and prev['value'] else None
    return dict(week=start.astimezone(LA).date().isoformat(), end=(end.astimezone(LA).date()-timedelta(days=1)).isoformat(),
                timezone=CONFIG['report_timezone'], complete=end <= now, generated_at=stamp(), videos=selected,
                creators=list(creators.values()), breakdown=counts, trends=trend_rows,
                summary=dict(confirmed_videos=len(confirmed), confirmed_creators=len({(v['platform'], v['creator_url'] or v['creator']) for v in confirmed}),
                             unique_content=len({v['content_group'] or v['id'] for v in confirmed}),
                             pending=sum(v['new_in_week'] and v['cooperation']=='线索待核实' for v in selected),
                             known_views=sum(v['views'] for v in confirmed if v['views'] is not None) if any(v['views'] is not None for v in confirmed) else None,
                             measured_videos=sum(v['views'] is not None for v in confirmed)),
                coverage=dict(video_records=len(selected), youtube=('已配置 API key；以运行记录判断采集是否成功' if os.environ.get('YOUTUBE_API_KEY') else '需配置免费 API key 后启用关键词发现与指标更新'),
                              instagram='仅导入，未接入自动发现', tiktok='仅导入，未接入自动发现', trends='仅导入 Google Trends，美国 Web 相对热度，非平台搜索量'),
                runs=[dict(r) for r in db.execute('SELECT * FROM runs ORDER BY id DESC LIMIT 10')])


def import_trends(db, text):
    rows = list(csv.DictReader(io.StringIO(text.lstrip('\ufeff'))))
    required = {'series_id', 'query', 'week', 'value', 'source', 'geo', 'search_type'}
    if not rows or not required <= rows[0].keys():
        raise ValueError('趋势 CSV 需要列：' + ','.join(sorted(required)))
    if len(rows) > 10000:
        raise ValueError('每次最多导入 10000 条趋势记录')
    with db:
        for r in rows:
            d = date.fromisoformat(r['week'])
            val = float(r['value'])
            if d.weekday() or d > datetime.now(LA).date()-timedelta(days=7) or not 0 <= val <= 100:
                raise ValueError('趋势需完整周的周一日期，热度需为 0–100')
            if r['geo'] != 'US' or r['search_type'] != 'web' or not all(r[k].strip() for k in ('series_id', 'query', 'source')):
                raise ValueError('当前仅接收美国 Web 搜索热度；series_id、query 和 source 必填')
            db.execute('INSERT INTO trends VALUES (?,?,?,?,?) ON CONFLICT(series_id,query,week) DO UPDATE SET value=excluded.value,source=excluded.source',
                       (r['series_id'], r['query'], r['week'], val, r['source']))
    return len(rows)
