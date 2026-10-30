import copy
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent


def load():
    path = Path(os.environ.get('MONITOR_CONFIG', ROOT/'data/settings.json'))
    value = json.loads((path if path.exists() else ROOT/'config/brands.json').read_text(encoding='utf-8'))
    value.setdefault('platforms', ['YouTube', 'Instagram', 'TikTok'])
    value.setdefault('countries', ['US'])
    value.setdefault('languages', ['en'])
    value.setdefault('baseline', {'size': 12, 'minimum': 10, 'multiple': 3, 'age_days': 7, 'tolerance_hours': 24})
    value.setdefault('absolute_thresholds', {p: copy.deepcopy(value['viral_candidate_views']) for p in value['platforms']})
    value.setdefault('schedule_timezone', 'Asia/Shanghai')
    value.setdefault('youtube_max_pages', 2)
    return value


def save(value):
    if not isinstance(value, dict):
        raise ValueError('配置必须为 JSON 对象')
    required = {'brands','platforms','countries','languages','history_days','report_timezone','viral_candidate_views','youtube_queries','baseline','absolute_thresholds'}
    if not required <= value.keys():
        raise ValueError('配置缺少字段：'+','.join(sorted(required-value.keys())))
    for key in ('brands','platforms','countries','languages','youtube_queries'):
        if not isinstance(value[key],list) or len(value[key])>100:
            raise ValueError(key+' 必须为不超过100项的列表')
    value['history_days']=int(value['history_days'])
    ZoneInfo(value['report_timezone'])
    ZoneInfo(value.get('schedule_timezone', 'Asia/Shanghai'))
    if not 7 <= int(value['history_days']) <= 3650:
        raise ValueError('历史天数应在7至3650之间')
    names = []
    for brand in value['brands']:
        names.append(brand['name'])
        if not brand['name'].strip() or not isinstance(brand['models'], list):
            raise ValueError('品牌名称和车型列表无效')
        for model in brand['models']:
            if not model['name'] or not model['aliases']:
                raise ValueError('车型必须提供名称与拼写列表')
    if len(set(names)) != len(names):
        raise ValueError('品牌名不能重复')
    b = value['baseline']
    if not 3 <= b['minimum'] <= b['size'] <= 50 or b['age_days'] not in (7,30) or b['multiple'] <= 1 or not 0 < b['tolerance_hours'] <= 72:
        raise ValueError('基线样本、观察期、倍数或时间容差无效')
    for platform in value['platforms']:
        if not platform.strip() or any(value['absolute_thresholds'][platform][f] <= 0 for f in ('long','short','unknown')):
            raise ValueError('每个平台需配置正数的长/短/未知格式阈值')
    path = Path(os.environ.get('MONITOR_CONFIG', ROOT/'data/settings.json'))
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)
    return value
