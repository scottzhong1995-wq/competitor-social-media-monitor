import json
from .core import stamp

STATUSES = {'明确合作', '线索待核实', '普通提及', '品牌官方内容', '排除'}


def validate_materials(materials):
    if not isinstance(materials, dict):
        raise ValueError('materials 需为对象')
    for name, value in materials.items():
        if name not in {'title','thumbnail','opening','scene','structure','comments','transcript','opportunity'}:
            raise ValueError('未知的分析材料字段')
        if not isinstance(value, dict) or not value.get('source','').startswith('https://') or not value.get('note') or value.get('kind') not in {'观察','推测'}:
            raise ValueError('分析必须提供实际材料来源、note 及 kind=观察/推测')
    return materials


def upsert_account(db, item, preserve=False):
    platform, aid = item['platform'], item.get('account_id') or item.get('creator_id') or item.get('creator_url')
    if not aid or not item.get('creator'):
        raise ValueError('账号需提供 platform、account_id、creator')
    fields = ('creator','creator_url','market','language','market_evidence','language_evidence','creator_type',
              'contact','contact_source','agency','agency_source','notes','followed','identity_group','identity_evidence','monitor')
    old = db.execute('SELECT profile FROM creators WHERE platform=? AND account_id=?',(platform,aid)).fetchone()
    profile = json.loads(old[0]) if old else {}
    for key in fields:
        if key in item and (not preserve or not profile.get(key)):
            profile[key] = item[key]
    if profile.get('contact') and not profile.get('contact_source'):
        raise ValueError('公开商务联系方式必须有来源')
    if profile.get('identity_group') and not profile.get('identity_evidence'):
        raise ValueError('跨平台身份合并需要可核验的身份依据')
    if profile.get('agency') and not profile.get('agency_source'):
        raise ValueError('经纪信息需有公开来源')
    db.execute('INSERT INTO creators VALUES (?,?,?,?) ON CONFLICT(platform,account_id) DO UPDATE SET profile=excluded.profile,updated_at=excluded.updated_at',
               (platform,aid,json.dumps(profile,ensure_ascii=False),stamp()))
    return dict(platform=platform,account_id=aid,**profile)


def revise_video(db, item):
    original = db.execute('SELECT * FROM videos WHERE id=?',(item['id'],)).fetchone()
    if not original:
        raise ValueError('视频不存在')
    old = dict(original)
    aliases={'已确认合作':'明确合作','疑似合作':'线索待核实','普通品牌提及':'普通提及'}
    changed = {k:v for k,v in item.items() if k in {
      'cooperation','evidence','evidence_source','format','market','language','market_evidence','language_evidence',
      'review_note','models','direction','summary_zh','materials','content_group','baseline_only'}}
    if 'cooperation' in changed:
        changed['cooperation'] = aliases.get(changed['cooperation'],changed['cooperation'])
    status = changed.get('cooperation',old['cooperation'])
    if status not in STATUSES:
        raise ValueError('无效合作状态')
    if status in {'明确合作','品牌官方内容'} and not changed.get('evidence',old['evidence']).strip():
        raise ValueError('确认合作/官方内容需要证据')
    if changed.get('format',old['format']) not in {'long','short','unknown'}:
        raise ValueError('无效内容形式')
    if 'materials' in changed:
        changed['materials'] = json.dumps(validate_materials(changed['materials']),ensure_ascii=False)
    for key in ('models','direction'):
        if key in changed:
            if not isinstance(changed[key],list):
                raise ValueError(key+' 必须为列表')
            changed[key] = json.dumps(changed[key],ensure_ascii=False)
    changed['reviewed_at'] = stamp()
    with db:
        db.execute('UPDATE videos SET '+','.join(k+'=?' for k in changed)+' WHERE id=?',[*changed.values(),item['id']])
        db.execute('INSERT INTO reviews(video_id,reviewed_at,before_json,after_json) VALUES (?,?,?,?)',
                   (item['id'],changed['reviewed_at'],json.dumps(old),json.dumps(changed)))


def capabilities():
    return [
      dict(source='YouTube Data API v3',mode='自动搜索/手动指定视频与账号',fields='标题、描述、发布时间、账号ID、订阅数、播放、点赞、评论、时长、封面URL',
           unavailable='分享量、观众国家、可靠Shorts标记、一般视频字幕与私有商务邮箱',refresh='每天一次；按配额和分页上限',limitations='搜索仅相关性过滤；非全量；需审核合作和地域'),
      dict(source='Instagram',mode='JSON手动导入；未接授权接口',fields='导入提供的公开字段、快照、商务联系方式',unavailable='未授权自动发现/刷新',refresh='导入时',limitations='Reels独立分组；缺失字段不可用'),
      dict(source='TikTok',mode='JSON手动导入；未接授权接口',fields='导入提供的公开字段、快照、商务联系方式',unavailable='未授权自动发现/刷新',refresh='导入时',limitations='独立分组，不声称全网覆盖'),
      dict(source='Google Trends',mode='CSV导入',fields='周指数、地区、渠道、匹配方式、范围、批次、可选相关查询',unavailable='无授权自动接口；未导入相关查询时不可用',refresh='每周导入',limitations='同批次归一化；非绝对搜索量；YouTube搜索仅接受显式youtube渠道数据')]
