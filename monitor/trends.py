import csv
import io
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from .core import stamp
from .settings import load


def ingest(db, text):
    rows = list(csv.DictReader(io.StringIO(text.lstrip('\ufeff'))))
    required = {'series_id','query','week','value','source','geo','search_type'}
    if not rows or not required <= rows[0].keys() or len(rows)>10000:
        raise ValueError('需要1–10000行，列：'+','.join(sorted(required)))
    tz = ZoneInfo(load()['report_timezone'])
    with db:
        for row in rows:
            day = date.fromisoformat(row['week'])
            value = float(row['value']) if row['value'].strip() else None
            partial = str(row.get('partial','0')).lower() in {'1','true','yes'}
            if day.weekday() or value is None or not 0 <= value <= 100:
                raise ValueError('需周一日期和0–100指数；缺失样本应不导入，不能补0')
            if datetime.combine(day+timedelta(days=7),time(),tz)>datetime.now(timezone.utc) and not partial:
                raise ValueError('未完整周需标记 partial=1')
            if row['search_type'] not in {'web','youtube'} or not all(row[k].strip() for k in ('series_id','query','source','geo')):
                raise ValueError('趋势地区/来源/系列必填，渠道为web或youtube')
            old = db.execute('SELECT * FROM trends WHERE series_id=? LIMIT 1',(row['series_id'],)).fetchone()
            match = row.get('match_type','search_term')
            scope = row.get('range_label','')
            if old and (old['geo'],old['search_type'],old['match_type'],old['range_label']) != (row['geo'],row['search_type'],match,scope):
                raise ValueError('同一series_id必须有相同地区、渠道、匹配方式和查询范围')
            fields = ['series_id','query','week','value','source','geo','search_type','match_type','range_label','collected_at','partial']
            db.execute('INSERT INTO trends('+','.join(fields)+') VALUES('+','.join('?' for _ in fields)+') ON CONFLICT(series_id,query,week) DO UPDATE SET value=excluded.value,collected_at=excluded.collected_at,partial=excluded.partial',
                       [row['series_id'],row['query'],row['week'],value,row['source'],row['geo'],row['search_type'],match,scope,stamp(row.get('collected_at') or None),int(partial)])
    return len(rows)


def read(db, start, end):
    rows = [dict(r) for r in db.execute('SELECT * FROM trends WHERE week>=? AND week<? ORDER BY series_id,query,week',((start-timedelta(weeks=11)).isoformat(),end.isoformat()))]
    for row in rows:
        prev=db.execute('SELECT value,partial FROM trends WHERE series_id=? AND query=? AND week=?',(row['series_id'],row['query'],(date.fromisoformat(row['week'])-timedelta(days=7)).isoformat())).fetchone()
        valid = prev and not prev['partial'] and not row['partial']
        row['previous'] = prev['value'] if valid else None
        row['change_percent'] = round((row['value']/prev['value']-1)*100,1) if valid and prev['value'] else None
        row['change_label'] = ('不足完整周' if row['partial'] else f"从 0 增至 {row['value']:g}" if valid and prev['value']==0 else f"{row['change_percent']:+g}%" if row['change_percent'] is not None else '不可用')
        row['related'] = [dict(r) for r in db.execute('SELECT * FROM related_queries WHERE series_id=? AND query=?',(row['series_id'],row['query']))]
    return rows
