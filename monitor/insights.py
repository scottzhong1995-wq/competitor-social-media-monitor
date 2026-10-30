"""Deterministic, evidence-bounded module summaries shared by UI and exports."""
import re
from collections import Counter

SCOPE_STATUSES = {
    'confirmed': {'明确合作'}, 'suspected': {'线索待核实'},
    'combined': {'明确合作','线索待核实'}, 'official': {'品牌官方内容'},
    'all': {'明确合作','线索待核实','普通提及','品牌官方内容'},
}


def number(value):
    return '不可用' if value is None else f'{value:,}'


def panel(title, facts, conclusion, actions, limitations, evidence=None):
    return dict(title=title, facts=facts, conclusion=conclusion, actions=actions,
                limitations=limitations, evidence=evidence or [])


def analyse_video(v):
    relative=v['relative_viral']; high=v['high_views']
    kind='相对爆款候选＋高播放' if relative and high else '相对爆款候选' if relative else '高播放视频'
    facts=[f"{kind}；{'本周发布' if v['new_in_week'] else '历史视频'}；合作状态：{v['cooperation']}。",
           f"最后有效展示快照：{v['observed_at'] or '不可用'}，播放 {number(v['views'])}，点赞 {number(v['likes'])}，评论 {number(v['comments'])}，分享 {number(v['shares'])}。"]
    if high:
        facts.append(f"达到 {v['platform']} / {v['content_form']} 的高播放阈值 {number(v['absolute_threshold'])}。")
    if v['baseline_multiple'] is not None:
        facts.append(f"发布后 {v['baseline_age_days']} 天：同账号同形式 {v['baseline_sample_count']} 条可比样本中位数 {number(v['baseline_median'])}，本片为基线 {v['baseline_multiple']:g} 倍。")
    else:
        facts.append(f"同龄样本 {v['baseline_sample_count']} 条；{v['baseline_confidence']}，不计算精确倍数。")
    if v['observed_growth'] is None:
        facts.append('增长速度不可用：尚无有效的两次观测窗口，累计播放不视为本周新增。')
    else:
        facts.append(f"实际观测窗口 {v['growth_from']} 至 {v['growth_to']}：变化 {number(v['observed_growth'])}，平均每天 {number(v['growth_per_day'])}；{'存在指标回调，不解读为传播下降。' if v['metric_correction'] else '不保证覆盖完整统计周。'}")
    observations=[f"原标题：{v['title']}",
                  '原标题品牌词：'+('、'.join(v['title_brands']) or '未匹配')+'；车型词：'+('、'.join(v['title_models']) or '未匹配')+'。',
                  '归纳主题标签（不等于原标题原词）：'+('、'.join(v['direction']) or '未知')+'。']
    labels={'thumbnail':'封面','opening':'开场','scene':'测试场景','structure':'内容结构','comments':'观众讨论点','transcript':'字幕/口播','title':'标题补充','opportunity':'合作机会'}
    materials=[];hypotheses=[]
    for key,label in labels.items():
        item=v['materials'].get(key)
        if item:
            materials.append(dict(field=key,label=label,status='人工提供观察记录' if item['kind']=='观察' else '推测，待核验',**item))
            text=f"{label}：{item['note']}（人工记录，来源：{item['source']}）"
            (observations if item['kind']=='观察' else hypotheses).append(text)
        elif key not in {'title','opportunity'}:
            materials.append(dict(field=key,label=label,status='不可用，未取得对应材料',note='',source='',kind=''))
    actions=[];text=v['title'].lower()
    for pattern,action in [
        (r'range|battery', 'Qronge选题验证：设计同载重、路况、速度和电量条件的续航对比，先核对原片是否披露这些条件。'),
        (r'speed|mph', 'Qronge选题验证：统一电量、轮胎、路面和载重条件做速度实测；标题可突出实测条件，结果必须来自真实测试。'),
        (r'climb|hill|trail|off.?road', 'Qronge选题验证：记录坡度、地形和骑手背景，比较操控与爬坡体验；先观看原片确认场景。'),
        (r'review|honest|verdict', 'Qronge选题验证：以适用人群、实际体验和优缺点清单组织评测，先复核原片的评测维度。'),
        (r'\bvs\b|versus|compar', 'Qronge选题验证：选择同定位车型做条件一致的对比，核实售价、版本和测试方法后再拟定结论。')]:
        if re.search(pattern,text):actions.append(action)
    if not actions:actions.append('Qronge选题验证：先观看原视频，核对标题承诺与实际内容，再决定是否借鉴主题。')
    actions.append(f"创作者机会：复核 {v['creator']} 的美国受众、内容定位及同龄历史表现；通过已记录的公开商务入口评估合作，不自动联系或推算报价。")
    if not relative:actions.append('补齐同账号最近10–12条同形式视频的同龄快照，再判断是否相对爆款。')
    if any(not m['source'] for m in materials):actions.append('补录带来源的封面、开场、场景、结构和评论观察，未取得前不下内容因果结论。')
    conclusion=('同龄可比指标支持其相对账号表现突出。' if relative else '目前只满足绝对高播放标准，尚不足以认定相对账号表现异常。')+'现有指标不能证明传播原因、自然流量比例或转化效果。'
    return dict(id=v['id'],url=v['url'],title=v['title'],kind=kind,
        period='本周新上线' if v['new_in_week'] else '历史内容复查',facts=facts,observations=observations,
        hypotheses=hypotheses,materials=materials,conclusion=conclusion,actions=actions,
        basis='规则归纳＋人工材料记录；系统未自动观看视频',
        limitations=['未取得的材料不分析；人工备注与系统直接读取指标分开。',
                      '候选遵循当前统计合作范围、市场和播放门槛；默认不含待审核或普通提及。',
                      '高播放不等于高转化，不推断订单、销售额、ROI或合作费用。'])


def enrich(data):
    videos=data['videos'];s=data['summary']
    selected=[v for v in videos if v['statistics_eligible'] and v['cooperation'] in SCOPE_STATUSES[data['scope']] and (v['target_market'] or data['filters'].get('include_other')=='1')]
    current=[v for v in selected if v['new_in_week']]
    references=[dict(label=v['title'],url=v['url']) for v in current[:5]]
    scopes=f"统计须播放量至少{data['minimum_views']:,}；低播放及未知播放保留在库但不计数。按顶部筛选；列表内搜索不改变汇总。"
    insights={}
    change=f"较上周 {s['previous_videos']} 条变化 {s['count_change']:+} 条；"+(f"环比 {s['count_change_percent']:+g}%。" if s['count_change_percent'] is not None else s['change_note']+'。')
    insights['overview']=panel('本周动态分析与总结',
        [f"选定统计范围本周发布 {s['published']} 条，涉及 {s['creators']} 个平台账号；{change}",
         f"同范围本周发现 {s['discovered']} 条、更新 {s['updated']} 条；疑似合作 {s['pending']} 条和官方内容 {s['official']} 条单独展示。"],
        '发布数量变化只描述已收录、已审核样本，不足以判断竞品投放预算或策略变化。' if current else '当前范围缺少本周发布样本，不能解读为竞品没有开展合作。',
        ['优先检查折扣码和联盟链接；两者都没有的先审核，再核对所在地与形式。'],
        [scopes,'疑似/官方计数来自视频列表，与选定合作汇总范围不同，不相加为确认合作。'],references)
    brands=Counter(b for v in current for b in v['brands']);models=Counter(m for v in current for m in v['models'])
    from .core import week_bounds
    start,_=week_bounds(data['week'],timezone_name=data['timezone'])
    previous=[v for v in videos if v['previous_views'] is not None and v['previous_views']>=data['minimum_views'] and v['cooperation'] in SCOPE_STATUSES[data['scope']] and (v['target_market'] or data['filters'].get('include_other')=='1') and data['previous_week_start']<=v['published_at']<start.isoformat()]
    previous_brands=Counter(b for v in previous for b in v['brands'])
    contributions=[f"{brand} {brands[brand]-previous_brands[brand]:+} 条" for brand in sorted(set(brands)|set(previous_brands)) if brands[brand]!=previous_brands[brand]]
    if contributions:insights['overview']['facts'].append('已收录数量变化分布：'+'；'.join(contributions)+'。这是样本构成变化，不是投放策略的因果解释；多品牌视频可能重复进入品牌分布。')
    insights['brands']=panel('品牌与车型分布解读',
        ['本周品牌发布分布：'+('；'.join(f'{k} {n} 条' for k,n in brands.most_common()) or '不可用')+'。',
         '本周车型标签分布：'+('；'.join(f'{k} {n} 条' for k,n in models.most_common()) or '不可用')+'。'],
        (f"当前样本中出现最多的是 {brands.most_common(1)[0][0]}，覆盖 {brands.most_common(1)[0][1]}/{len(current)} 条发布记录。" if brands else '尚无本周品牌分布样本。')+'分布反映当前样本覆盖，不能据此推断竞品车型销量或合作费用。',
        ['对集中出现的车型补查产品版本、合作证据和创作者类型，形成Qronge选题对照。'],
        ['同片出现多品牌/车型会分别进入标签分布，不应相加当去重视频数。'],references)
    directions=data['directions'][:3];keywords=[r['name'] for r in data['keywords'] if r['name']!='demo'][:8]
    insights['content']=panel('内容方向与标题分析',
        ['主要方向：'+('；'.join(f"{r['name']} {r['count']} 条，占 {r['share']:g}%，较上周变化 {r['share_change_pp']:+g} 个百分点" for r in directions) or '不可用')+'。',
         '原标题高频词：'+('、'.join(keywords) or '不可用')+'。'],
        '方向标签是系统归纳，标题词是原标题中的真实词；频次不等于选题效果或爆款成因。',
        ['将高频主题与同龄表现交叉复核，再安排Qronge选题测试；不只模仿标题词。'],
        ['多标签占比可超过100%；未取得视频材料时不能判断封面、开场或结构。'],references)
    growth_count=sum(v['observed_growth'] is not None for v in selected)
    insights['effects']=panel('曝光表现分析与总结',
        [f"新上线内容已知累计播放 {number(s['known_views'])}，覆盖 {s['measured_videos']}/{s['published']} 条；均值 {number(s['average_views'])}，中位数 {number(s['median_views'])}。",
         f"选定范围 {growth_count}/{len(selected)} 条有可用增长窗口；历史内容观测区间增量 {number(s['historical_growth'])}。"],
        '当前累计播放只能作为曝光代理；缺失指标和不同视频年龄会影响均值、中位数及比较。',
        ['先补齐缺失快照，长短视频分组比较；优先采用发布后7天或30天的同龄表现。'],
        ['没有基线不计算新增；观察窗口可能跨周界。跨平台播放量未去重受众。'],references)
    measured=[v for v in current if v['views'] is not None]
    if measured and sum(v['views'] for v in measured)>0:
        top=max(measured,key=lambda v:v['views']);share=top['views']/sum(v['views'] for v in measured)*100
        insights['effects']['facts'].append(f"单条最高播放占已知播放的 {share:.1f}%（{len(measured)} 条有播放数据）。缺失指标未计入分母，不等于整体受众集中度。")
        insights['effects']['evidence']=[dict(label=top['title'],url=top['url'])]
    if s['median_views'] and s['average_views']>1.5*s['median_views']:
        insights['effects']['conclusion']+='均值与中位数差距较大，应避免只用均值评价合作表现。'
    pending=[v for v in videos if v['cooperation']=='线索待核实'];unknown=sum(v['market']=='unknown' for v in videos)
    insights['videos']=panel('视频监控分析与审核重点',
        [f"视频列表收录 {len(videos)} 条非基线记录；其中本周发布 {sum(v['new_in_week'] for v in videos)}、本周发现 {sum(v['discovered_in_week'] for v in videos)}、本周更新 {sum(v['updated_in_week'] for v in videos)}，三个集合可重叠。",
         f"待核实商业线索 {len(pending)} 条，所在地未知 {unknown} 条，观察截止点数据过期 {sum(v['stale'] for v in videos)} 条。"],
        '视频列表包含各种合作状态，数量不能直接当作已确认合作量。',
        ['先复核折扣码和联盟链接；两者都没有的必须人工审核，对过期记录检查采集日志。'],
        [scopes,'本模块覆盖视频列表所有状态；选定合作指标见周度总览。'],[dict(label=v['title'],url=v['url']) for v in pending[:5]])
    candidates=[v for v in selected if v['viral_candidate'] and v['cooperation']!='排除']
    candidates.sort(key=lambda v:(v['relative_viral'],v['baseline_multiple'] or 0,v['views'] or 0,v['id']),reverse=True)
    for v in candidates:v['analysis']=analyse_video(v)
    insights['viral']=panel('爆款候选分析与总结',
        [f"当前视频列表有 {len(candidates)} 条候选：绝对高播放 {sum(v['high_views'] for v in candidates)} 条，相对账号爆款候选 {sum(v['relative_viral'] for v in candidates)} 条，两类可重叠。",
         f"其中本周新上线 {sum(v['new_in_week'] for v in candidates)} 条、历史内容 {sum(not v['new_in_week'] for v in candidates)} 条。"],
        '优先复核同龄基线充分的相对候选；绝对高播放不能替代相对异常判定。' if candidates else '暂无达到当前规则的已收录候选，覆盖不足时不能判断竞品没有爆款。',
        ['逐条查看合作证据、实际观察窗口和材料来源；将可验证选题和创作者机会纳入下周研究清单。'],
        ['候选按当前合作范围、市场及播放门槛筛选；待审核需切换范围后单独查看。'])
    from .core import identify
    for field,index in [('brand',0),('model',1)]:
        if data['filters'].get(field):
            data['trends']=[t for t in data['trends'] if data['filters'][field] in identify(t['query'])[index]]
    week_trends=[t for t in data['trends'] if t['week']==data['week']]
    full=[t for t in week_trends if not t['partial']]
    increases=[t for t in full if t['previous'] is not None and t['value']>t['previous']]
    insights['trends']=panel('搜索趋势分析与总结',
        [f"当前周有 {len(full)} 条完整周指数、{len(week_trends)-len(full)} 条部分周记录；可比上周的上升记录 {len(increases)} 条。",
         '上升词：'+('；'.join(f"{t['query']} {t['change_label']}（{t['geo']}/{t['search_type']}，系列 {t['series_id']}）" for t in increases[:6]) or '暂无可确认的上升记录')+'。'],
        '尚无足够数据判断搜索热度变化。' if not full else '变化只代表各查询自身在相同归一化批次内的相对热度，不能直接归因于红人合作。',
        ['补齐同地区、同渠道、同查询范围的12周指数和相关查询；把搜索变化与发布时间并列观察。'],
        ['不相加跨批次指数；零基数不算百分比；缺失不补0。搜索渠道独立于视频平台筛选。'],[dict(label=t['query'],url=t['source']) for t in full[:5]])
    accounts=data['creators'];with_contact=sum(bool(c.get('contact') and c.get('contact_source')) for c in accounts)
    insights['creators']=panel('红人库分析与合作机会',
        [f"当前账号库 {len(accounts)} 个平台账号，含确认合作记录 {sum(c['confirmed']>0 for c in accounts)} 个，已有公开商务联系方式及来源 {with_contact} 个，已关注 {sum(bool(c.get('followed')) for c in accounts)} 个。",
         f"有爆款候选记录的账号 {sum(c['viral_count']>0 for c in accounts)} 个；这不代表其全部内容的爆款率。"],
        '可先复核有候选表现和定位匹配的账号，粉丝规模或单条高播放不足以确定合作价值。',
        ['核对美国受众依据、同龄样本、内容类型和公开商务入口；保留低表现及暂无合作的账号供后续筛选。'],
        ['账号库按平台/品牌筛选，保留历史档案；不等同于本周新合作名单。身份未经核实不跨平台合并。'])
    latest=data['runs'][0] if data['runs'] else None
    insights['sources']=panel('采集覆盖分析与下一步',
        ['最近任务：'+(f"{latest['started_at']} / {latest['status']}。" if latest else '尚无运行记录。'),
         f"最近展示的 {len(data['queries'])} 条查询记录中，页数截断 {sum(q['status']=='page_limit' for q in data['queries'])} 条、失败 {sum(q['status']=='failed' for q in data['queries'])} 条。"],
        '接口成功只验证对应查询，不代表三平台全量覆盖；任务记录也不证明常驻进程仍在运行。',
        ['对失败和截断查询先查日志与配额；补录未接自动接口的平台数据，并定期验证本机夜间进程。'],
        ['Instagram/TikTok与Google Trends自动接口未接通；数据量不足时保留限制说明。'])
    data['insights']=insights
    data['viral_candidates']=candidates
    data['weekly_signals']=[f"合作发布 {s['published']} 条，{s['creators']} 个平台账号；较上周变化 {s['count_change']:+} 条。",
        ('主要车型：'+'、'.join(f'{name} {count}条' for name,count in models.most_common(3))+'。') if models else '当前范围无达标的新上线车型数据。',
        f"达标爆款候选 {len(candidates)} 条，其中本周发布 {sum(v['new_in_week'] for v in candidates)} 条，历史视频 {sum(not v['new_in_week'] for v in candidates)} 条。"]
    return data
