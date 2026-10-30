import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from statistics import median, mean
from zoneinfo import ZoneInfo

from .core import stamp, week_bounds, identify
from .settings import load
from .profiles import capabilities
from .trends import read as read_trends


def total(values):
    known = [v for v in values if v is not None]
    return sum(known) if known else None


def age_snapshot(video, snaps, days, cutoff, tolerance):
    target = datetime.fromisoformat(video['published_at'])+timedelta(days=days)
    if cutoff < target:
        return dict(status='未满观察期', views=None, observed_at=None)
    eligible = [s for s in snaps if s['views'] is not None and target<=datetime.fromisoformat(s['observed_at'])<=target+timedelta(hours=tolerance)]
    if not eligible:
        return dict(status='缺少同龄快照', views=None, observed_at=None)
    return dict(status='可比快照', views=eligible[0]['views'], observed_at=eligible[0]['observed_at'])


def form(v):
    if v['platform']=='Instagram':
        return 'Instagram Reels' if '/reel/' in v['url'] else 'Instagram 未知/帖子'
    if v['platform']=='TikTok':
        return 'TikTok 视频'
    return {'long':'YouTube 普通视频' if v['platform']=='YouTube' else '长视频',
            'short':'YouTube Shorts' if v['platform']=='YouTube' else '短视频','unknown':'未知形式'}[v['format']]


def aggregate(rows):
    measured=[r['views'] for r in rows if r['views'] is not None]
    return dict(videos=len(rows), creators=len({(v['platform'],v['creator_id']) for v in rows}),
        views=sum(measured) if measured else None, measured=len(measured),
        average_views=round(mean(measured),2) if measured else None,
        median_views=median(measured) if measured else None,
        observed_growth=total([v['observed_growth'] for v in rows]), growth_measured=sum(v['observed_growth'] is not None for v in rows))


def distribution(rows, key):
    counts=Counter()
    for v in rows:
        for item in v[key] if isinstance(v[key],list) else [v[key]]:
            counts[item]+=1
    return [dict(name=k,count=c,share=round(c/len(rows)*100,2) if rows else None) for k,c in counts.most_common()]


def build_report(db, week=None, **filters):
    config=load()
    start,end=week_bounds(week,timezone_name=filters.get('timezone') or config['report_timezone'])
    now=datetime.now(timezone.utc)
    cutoff=min(end,now)
    videos=[]; all_rows=[]
    for raw in db.execute('SELECT * FROM videos ORDER BY published_at DESC'):
        v=dict(raw)
        if datetime.fromisoformat(v['published_at'])>=cutoff:
            continue
        for k in ('brands','models','direction','keywords','materials'):
            v[k]=json.loads(v[k])
        snaps=[dict(s) for s in db.execute('SELECT * FROM snapshots WHERE video_id=? AND observed_at<? ORDER BY observed_at',(v['id'],cutoff.isoformat()))]
        latest=snaps[-1] if snaps else {}
        valid=[s for s in snaps if s['views'] is not None]
        inside=[s for s in valid if s['observed_at']>=start.isoformat()]
        before=[s for s in valid if s['observed_at']<=start.isoformat()]
        base=before[-1] if before else (inside[0] if inside else None)
        last=valid[-1] if valid else None
        growth=last['views']-base['views'] if inside and base and last and last['observed_at']!=base['observed_at'] else None
        v.update({k:latest.get(k) for k in ('views','likes','comments','followers','shares','observed_at')})
        v['metric_source']=latest.get('source')
        v.update(observed_growth=growth, growth_from=base['observed_at'] if growth is not None else None,
                 growth_to=last['observed_at'] if growth is not None else None, metric_correction=growth is not None and growth<0,
                 new_in_week=start.isoformat()<=v['published_at']<end.isoformat(),
                 discovered_in_week=start.isoformat()<=v['discovered_at']<end.isoformat(),
                 updated_in_week=bool([s for s in snaps if s['observed_at']>=start.isoformat()]),
                 target_market=v['market'] in config['countries'] and v['language'] in config['languages'])
        v['content_form']=form(v)
        v['growth_per_day']=round(growth/((datetime.fromisoformat(last['observed_at'])-datetime.fromisoformat(base['observed_at'])).total_seconds()/86400),2) if growth is not None else None
        v['stale']=not latest or (cutoff-datetime.fromisoformat(latest['observed_at'])).total_seconds()>48*3600
        v['interaction_rate']=round((v['likes']+v['comments']+(v['shares'] or 0))/v['views']*100,3) if v['views'] and v['likes'] is not None and v['comments'] is not None else None
        v['interaction_formula']='(点赞+评论'+('+分享' if v['shares'] is not None else '；分享不可用')+')/播放量 ×100%'
        v['age7']=age_snapshot(v,snaps,7,cutoff,config['baseline']['tolerance_hours'])
        v['age30']=age_snapshot(v,snaps,30,cutoff,config['baseline']['tolerance_hours'])
        v['title_brands'],v['title_models']=identify(v['title'])
        v['summary_zh']=v['summary_zh'] or '规则摘要：'+('、'.join(v['models']) or '车型未知')+'；内容标签：'+'、'.join(v['direction'])+'。依据：标题/描述；未观看视频。'
        v['evidence_source']=v['evidence_source'] or v['url']
        all_rows.append(v)
    # Same creator, platform, known format, older posts, identical post-age window.
    b=config['baseline']
    for v in all_rows:
        candidates=[r for r in all_rows if (r['platform'],r['creator_id'],r['format'])==(v['platform'],v['creator_id'],v['format']) and r['published_at']<v['published_at']]
        candidates=candidates[:b['size']]
        agekey='age'+str(b['age_days'])
        comparable=[r[agekey]['views'] for r in candidates if r[agekey]['views'] is not None] if v['format']!='unknown' else []
        base=median(comparable) if comparable else None
        eligible=len(comparable)>=b['minimum'] and base and v[agekey]['views'] is not None
        ratio=round(v[agekey]['views']/base,3) if eligible else None
        threshold=config['absolute_thresholds'].get(v['platform'],config['viral_candidate_views'])[v['format']]
        v.update(baseline_sample_count=len(comparable), baseline_median=base if eligible else None,
                 baseline_multiple=ratio, baseline_age_days=b['age_days'], baseline_confidence='同龄样本充分' if eligible else '样本不足/格式未知/缺少同龄快照',
                 high_views=v['views'] is not None and v['views']>=threshold,
                 relative_viral=ratio is not None and ratio>=b['multiple'], absolute_threshold=threshold)
        v['viral_candidate']=v['high_views'] or v['relative_viral']
        v['viral_reason']=('同账号同形式同龄中位数的 '+str(ratio)+' 倍；' if v['relative_viral'] else '')+(f'累计播放达到阈值 {threshold:,}；' if v['high_views'] else '')
        v['analysis_basis']=['标题','描述']+[k for k in v['materials']]
        v['action_suggestion']='研究标题中的“'+' / '.join(v['keywords'][:5])+'”表达，并人工核查原视频测试条件；尚不能判断转化。'
        age=datetime.fromisoformat(v['published_at'])
        if v['baseline_only'] or not (cutoff-timedelta(days=config['history_days'])<=age or v['discovered_in_week'] or v['updated_in_week']):
            continue
        if any(filters.get(k) and (filters[k] not in v[field] if isinstance(v[field],list) else filters[k]!=v[field]) for k,field in [('brand','brands'),('platform','platform'),('model','models'),('format','format'),('cooperation','cooperation'),('market','market'),('language','language')]):
            continue
        videos.append(v)
    scope=filters.get('scope','confirmed')
    statuses={'confirmed':{'明确合作'},'suspected':{'线索待核实'},'combined':{'明确合作','线索待核实'},'official':{'品牌官方内容'},'all':{'明确合作','线索待核实','普通提及','品牌官方内容'}}
    if scope not in statuses:
        raise ValueError('未知统计范围')
    eligible=[v for v in videos if v['cooperation'] in statuses[scope] and (v['target_market'] or filters.get('include_other')=='1')]
    current=[v for v in eligible if v['new_in_week']]
    previous=[v for v in eligible if (start-timedelta(days=7)).isoformat()<=v['published_at']<start.isoformat()]
    summary=aggregate(current)
    summary.update(confirmed_videos=sum(v['cooperation']=='明确合作' for v in current),confirmed_creators=len({(v['platform'],v['creator_id']) for v in current if v['cooperation']=='明确合作'}),
        known_views=summary['views'],measured_videos=summary['measured'],unique_content=len({v['content_group'] or v['id'] for v in current}),
        pending=sum(v['new_in_week'] and v['cooperation']=='线索待核实' for v in videos),
        official=sum(v['new_in_week'] and v['cooperation']=='品牌官方内容' for v in videos),
        published=len(current),discovered=sum(v['discovered_in_week'] for v in eligible),updated=sum(v['updated_in_week'] for v in eligible),
        historical_growth=total([v['observed_growth'] for v in eligible if not v['new_in_week']]),
        all_growth=total([v['observed_growth'] for v in eligible]),previous_videos=len(previous),count_change=len(current)-len(previous),
        count_change_percent=round((len(current)/len(previous)-1)*100,2) if previous else None,
        change_note='从 0 增至 '+str(len(current)) if not previous else '数量变化基于已收录和已审核记录；不推断营销预算或效果因果。')
    groups=defaultdict(list)
    for v in current:
        groups[(v['platform'],v['format'],v['content_form'])].append(v)
    breakdown=[dict(platform=k[0],format=k[1],content_form=k[2],**aggregate(rows)) for k,rows in groups.items()]
    brand_groups=defaultdict(list)
    for v in current:
        for brand in v['brands']:
            for model in v['models'] or ['未知']:
                # Assign a model only to its configured brand.
                if model!='未知' and not any(m['name']==model for b in config['brands'] if b['name']==brand for m in b['models']):
                    continue
                brand_groups[(brand,v['platform'],model)].append(v)
    brand_breakdown=[dict(brand=k[0],platform=k[1],model=k[2],**aggregate(rows)) for k,rows in brand_groups.items()]
    creators=[]; first_count=0; merged=set()
    for raw in db.execute('SELECT * FROM creators'):
        c=json.loads(raw['profile']);c.update(platform=raw['platform'],account_id=raw['account_id'])
        rows=[v for v in all_rows if v['platform']==c['platform'] and v['creator_id']==c['account_id'] and not v['baseline_only']]
        related=[v for v in rows if v['cooperation']=='明确合作']
        if filters.get('platform') and c['platform']!=filters['platform']: continue
        if filters.get('brand') and not any(filters['brand'] in v['brands'] for v in rows): continue
        recent=sorted(rows,key=lambda v:v['observed_at'] or '',reverse=True)
        follower=next((v for v in recent if v['followers'] is not None),{})
        c.update(followers=follower.get('followers'),observed_at=follower.get('observed_at'),videos=len(rows),confirmed=len(related),
          first_cooperation=min((v['discovered_at'] for v in related),default=None),last_cooperation=max((v['discovered_at'] for v in related),default=None),
          brands=sorted({b for v in related for b in v['brands']}),models=sorted({m for v in related for m in v['models']}),
          video_links=[v['url'] for v in related],viral_count=sum(v['viral_candidate'] for v in related),
          baseline_sample_count=recent[0]['baseline_sample_count'] if recent else 0,baseline_median=recent[0]['baseline_median'] if recent else None)
        for k in ('creator','creator_url','creator_type','contact','contact_source'): c.setdefault(k,'')
        first_scope=min((v['discovered_at'] for v in rows if v['cooperation'] in statuses[scope] and (v['target_market'] or filters.get('include_other')=='1')),default=None)
        if first_scope and start.isoformat()<=first_scope<end.isoformat(): first_count+=1
        if any(v in current for v in rows):
            merged.add('confirmed:'+c['identity_group'] if c.get('identity_group') and c.get('identity_evidence') else c['platform']+':'+c['account_id'])
        creators.append(c)
    summary['first_observed_creators']=first_count
    summary['cross_platform_creators']=len(merged)
    current_directions=distribution(current,'direction');previous_directions={r['name']:r['share'] for r in distribution(previous,'direction')}
    for d in current_directions: d['share_change_pp']=round(d['share']-previous_directions.get(d['name'],0),2)
    tz=ZoneInfo(filters.get('timezone') or config['report_timezone'])
    return dict(week=start.astimezone(tz).date().isoformat(),end=(end.astimezone(tz).date()-timedelta(days=1)).isoformat(),
        timezone=str(tz),generated_at=stamp(),snapshot_cutoff=cutoff.isoformat(),complete=end<=now,filters=filters,scope=scope,
        summary=summary,videos=videos,creators=creators,breakdown=breakdown,brand_breakdown=brand_breakdown,
        directions=current_directions,models=distribution(current,'models'),formats=distribution(current,'format'),keywords=distribution(current,'keywords'),
        trends=read_trends(db,start.astimezone(tz).date(),end.astimezone(tz).date()),rules=config['baseline'],thresholds=config['absolute_thresholds'],
        capabilities=capabilities(),coverage=dict(video_records=len(videos),youtube='已配置凭据；详见运行结果' if __import__('os').environ.get('YOUTUBE_API_KEY') else '未配置API key',instagram='仅导入',tiktok='仅导入',trends='CSV导入；相关查询未导入则不可用'),
        runs=[dict(r) for r in db.execute('SELECT * FROM runs ORDER BY id DESC LIMIT 20')],queries=[dict(r) for r in db.execute('SELECT * FROM queries ORDER BY id DESC LIMIT 30')],
        limitations=['播放量是曝光代理，跨平台未去重受众；不推算订单、销售额或ROI。','增长仅代表实际快照观察窗口，可能跨周界；不可冒充严格整周新增。',
          '未接通Instagram/TikTok自动发现、Google Trends自动接口；不代表全网合作总量。','历史周快照截至周末，后补数据不回填过去播放量；人工审核采用当前修正结果。',
          '内容多标签占比可能超过100%；未核实身份/内容不跨平台合并。','基线需另外收录同账号最近10–12条可比视频的同龄快照，不以当前累计量替代。'])
