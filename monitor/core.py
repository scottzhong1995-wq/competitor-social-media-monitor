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
from .settings import load as settings
from .schema import migrate

ROOT = Path(__file__).resolve().parent.parent
CONFIG = json.loads((ROOT / 'config/brands.json').read_text(encoding='utf-8'))
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
    migrate(db)
    db.commit()
    return db


def identify(text):
    text = text.lower()
    brands, models = [], []
    for brand in settings()['brands']:
        matches = []
        remaining = text
        for model in brand['models']:
            found = False
            for alias in sorted(model['aliases'], key=len, reverse=True):
                if alias.lower() == 'gb pro' and brand['name'].lower() not in text:
                    continue
                pattern = r'(?<![a-z0-9])' + re.escape(alias) + r'(?![a-z0-9])'
                if re.search(pattern, remaining):
                    found = True
                    remaining = re.sub(pattern, ' ', remaining)
            if found:
                matches.append(model['name'])
        if any(re.search(r'(?<![a-z0-9])'+re.escape(alias.lower())+r'(?![a-z0-9])',text) for alias in [brand['name'],*brand.get('aliases',[]),*brand.get('tags',[])]) or matches:
            brands.append(brand['name'])
            models.extend(matches)
    return brands, models


def classify(title, description):
    text = (title + '\n' + description).lower()
    directions = [label for pattern, label in [
        (r'unbox|assembl|setup', '开箱/组装'), (r'review|honest|verdict', '评测'),
        (r'off.?road|trail|dirt|motocross', '越野'), (r'hill|climb', '爬坡'),
        (r'top speed|mph|speed test', '速度实测'), (r'range|battery test', '续航实测'),
        (r'\bvs\b|versus|compar', '竞品对比'), (r'first ride', '首次骑行'), (r'upgrad|modif|custom', '改装'), (r'long.?term|months later|year later', '长期体验')
    ] if re.search(pattern, text)] or ['待分类']
    keywords = [w for w in re.findall(r'[a-z0-9]+(?:-[a-z0-9]+)*', title.lower())
                if w not in {'the', 'a', 'an', 'and', 'or', 'of', 'to', 'in', 'is', 'it', 'for', 'my', 'this', 'on', 'with'}]
    from .commercial import signals
    clues = [x['kind']+'：'+x['value']+'；'+x['context'] for x in signals(title+'\n'+description)]
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
            return 'ig:' + match[1], 'https://www.instagram.com/' + ('p' if p.path.startswith('/p/') else 'reel') + '/' + match[1] + '/'
    if platform == 'TikTok' and host == 'tiktok.com':
        match = re.fullmatch(r'/(@[\w.-]+)/video/(\d+)/?', p.path)
        if match:
            return 'tt:' + match[2], f'https://www.tiktok.com/{match[1]}/video/{match[2]}'
    if platform in settings()['platforms'] and platform not in {'YouTube','Instagram','TikTok'} and host:
        clean = p._replace(query='',fragment='').geturl()
        return platform+':'+hashlib.sha256(clean.encode()).hexdigest()[:24], clean
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
            retained = db.execute('SELECT brands,models FROM videos WHERE id=?',(vid,)).fetchone()
            if not brands and retained:
                brands,models = json.loads(retained['brands']),json.loads(retained['models'])
            if not brands and not retained and not item.get('baseline_only'):
                raise ValueError('标题或描述需匹配已配置品牌/车型，或显式标记 baseline_only 基线样本')
            directions, keywords, clues = classify(title, description)
            requested_status = {'已确认合作':'明确合作','疑似合作':'线索待核实','普通品牌提及':'普通提及'}.get(item.get('cooperation'),item.get('cooperation'))
            from .commercial import signals
            priority = signals(title+'\n'+description)
            cooperation = requested_status or ('明确合作' if priority else '线索待核实')
            if cooperation not in {'明确合作', '线索待核实', '普通提及', '排除', '品牌官方内容'}:
                raise ValueError('未知的合作状态')
            evidence = str(item.get('evidence', '\n'.join(clues) if priority else '未发现折扣码或联盟链接，待人工审核。'+('\n'+'\n'.join(clues) if clues else '')))
            origin = 'manual_import' if requested_status else 'auto'
            if cooperation == '品牌官方内容' and not evidence.strip():
                raise ValueError('品牌官方账号需提供核验依据')
            if cooperation == '明确合作' and not evidence.strip():
                raise ValueError('确认合作必须填写披露证据')
            fmt = item.get('format', 'short' if platform in {'Instagram','TikTok'} and '/p/' not in url else 'unknown')
            if fmt not in {'long', 'short', 'unknown'}:
                raise ValueError('format 必须为 long、short 或 unknown')
            contact = str(item.get('contact', ''))
            if contact and not item.get('contact_source'):
                raise ValueError('联系方式必须附公开来源链接')
            extra = {k:item[k] for k in ('creator_id','duration_seconds','summary_zh','market_evidence','language_evidence','baseline_only','evidence_source') if k in item}
            if 'duration_seconds' in extra: extra['duration_seconds'] = number(extra['duration_seconds'])
            extra['creator_id'] = item.get('creator_id') or (str(item.get('creator_url','')).split('/channel/')[-1].strip('/') if '/channel/' in str(item.get('creator_url','')) else item.get('creator_url')) or creator
            if 'materials' in item:
                from .profiles import validate_materials
                extra['materials'] = json.dumps(validate_materials(item['materials']))
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
            row.update(extra)
            row['classification_origin']=origin
            row['last_checked_at'] = observed
            old = db.execute('SELECT * FROM videos WHERE id=?', (vid,)).fetchone()
            # Refresh statistics/metadata without erasing manually reviewed decisions.
            if old:
                protected = bool(old['reviewed_at']) or old['classification_origin']=='manual_import' or (not old['classification_origin'] and old['cooperation'] in {'明确合作','品牌官方内容','排除'})
                if protected:row['classification_origin']=old['classification_origin']
                for field in ('cooperation', 'evidence', 'format', 'market', 'language', 'contact',
                              'contact_source', 'creator_type', 'content_group','summary_zh','market_evidence','language_evidence','materials','evidence_source'):
                    if (protected if field in {'cooperation','evidence'} else bool(old['reviewed_at']) or field not in item):
                        row[field] = old[field]
            fields = list(row)
            updates = ','.join(f'{k}=excluded.{k}' for k in fields if k not in {'id', 'discovered_at'})
            db.execute(f"INSERT INTO videos ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)}) "
                       f'ON CONFLICT(id) DO UPDATE SET {updates}', list(row.values()))
            values = [number(item.get(k)) for k in ('views', 'likes', 'comments', 'followers')]
            db.execute('INSERT INTO snapshots(video_id,observed_at,views,likes,comments,followers,source,shares) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(video_id,observed_at) '
                       'DO UPDATE SET views=excluded.views,likes=excluded.likes,comments=excluded.comments,'
                       'followers=excluded.followers,source=excluded.source,shares=excluded.shares',
                       [vid, observed, *values, str(item['source']), number(item.get('shares'))])
            from .profiles import upsert_account
            upsert_account(db, {**row, 'account_id':row['creator_id']}, preserve=True)
    return len(items)


def review(db, item):
    from .profiles import revise_video
    return revise_video(db, item)


def week_bounds(week=None, now=None, timezone_name=None):
    LA = ZoneInfo(timezone_name or settings()['report_timezone'])
    today = (now or datetime.now(UTC)).astimezone(LA).date()
    monday = date.fromisoformat(week) if week else today - timedelta(days=today.weekday()+7)
    if monday.weekday() != 0:
        raise ValueError('周起始日期必须为周一')
    start = datetime.combine(monday, time(), LA)
    return start.astimezone(UTC), (start + timedelta(days=7)).astimezone(UTC)


def report(db, week=None, **filters):
    from .analytics import build_report
    return build_report(db, week, **filters)


def import_trends(db, text):
    from .trends import ingest
    return ingest(db, text)
