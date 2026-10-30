from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter


def workbook(data):
    wb = Workbook()
    wb.remove(wb.active)

    def sheet(name, headers, rows):
        ws = wb.create_sheet(name)
        ws.append(headers)
        for row in rows:
            clean = [', '.join(map(str, x)) if isinstance(x, list) else ('不可用' if x is None else x) for x in row]
            ws.append(clean)
        for row in ws:
            for cell in row:
                if isinstance(cell.value, str):
                    # Untrusted titles/contacts must never become spreadsheet formulas.
                    cell.data_type = 's'
                    cell.alignment = Alignment(vertical='top', wrap_text=True)
        for cell in ws[1]:
            cell.font = Font(color='FFFFFF', bold=True)
            cell.fill = PatternFill('solid', fgColor='183D3A')
        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = ws.dimensions
        for col in range(1, len(headers)+1):
            ws.column_dimensions[get_column_letter(col)].width = min(60, max(16, max(len(str(ws.cell(r, col).value or '')) for r in range(1, min(ws.max_row, 100)+1))+2))

    s = data['summary']
    sheet('口径与覆盖', ['项目', '说明'], [
        ['统计周', data['week']+' 至 '+data['end']], ['统计时区', data['timezone']],
        ['报告状态', '完整周' if data['complete'] else '进行中，非完整周'],
        ['数据截止', data['generated_at']], ['合作视频（折扣/联盟商业关联或人工确认）', s['confirmed_videos']],
        ['合作账号数', s['confirmed_creators']],['统计门槛',f"播放量≥{data['minimum_views']:,}；未知播放待补；历史周按当时快照判断"], ['已知累计播放', s['known_views']],
        ['播放量覆盖', f"{s['measured_videos']}/{s['confirmed_videos']} 条视频"],
        ['累计播放含义', '本周新发布、已确认合作、美国英语视频在周末前最后一次快照的播放量；非去重触达'],
        ['新增播放', '仅提供两次真实观测间的增量及起止时间；没有基线则留空，不推算整周'],
        ['历史覆盖', '目标近90天；首次采集无法恢复过去逐日播放量；导入/查询结果不代表全网总量'],
        ['独立内容', '仅在人工提供 content_group 时跨平台合并，未提供时按独立发布计'],
        ['搜索趋势', '美国 Google Web 相对热度0–100；同 series_id 同 query 相邻完整周比较；非绝对搜索量'],
        ['爆款候选', '按平台内内容格式的绝对播放阈值筛选；不代表因果分析或保证自然流量'],
        *[[k, v] for k, v in data['coverage'].items() if k != 'video_records']])
    fields = ['platform','title','url','creator','brands','models','format','published_at','discovered_at',
              'cooperation','evidence','market','language','direction','keywords','views','observed_at',
              'observed_growth','growth_from','growth_to','viral_candidate','viral_reason','source','metric_source','content_group']
    headers = ['平台','标题','视频链接','红人','品牌','车型','长短格式','发布时间','首次发现',
               '合作状态','合作证据','市场','语言','内容方向','标题关键词','累计播放','快照时间',
               '观测区间增量','区间起点','区间终点','高播放候选','筛选原因','视频来源','指标来源','跨平台内容组']
    sheet('本周发布视频', headers, [[v.get(k) for k in fields] for v in data['videos'] if v['new_in_week'] and v['statistics_eligible']])
    sheet('历史视频与效果', headers, [[v.get(k) for k in fields] for v in data['videos'] if v['statistics_eligible']])
    sheet('长短视频汇总', ['平台','格式','确认合作视频','已知累计播放','有播放数据条数'],
          [[r[k] for k in ['platform','format','videos','views','measured']] for r in data['breakdown']])
    fields = ['platform','creator','creator_url','followers','observed_at','creator_type','contact','contact_source','videos','confirmed']
    sheet('红人名单', ['平台','账号','主页','粉丝数','数据时间','红人类型','公开商务联系方式','联系方式来源','收录视频','确认合作视频'],
          [[r[k] for k in fields] for r in data['creators']])
    sheet('搜索趋势', ['同批次系列ID','搜索词','周起始','相对热度','周环比百分比','来源'],
          [[t[k] for k in ['series_id','query','week','value','change_percent','source']] for t in data['trends']])
    sheet('周度汇总', ['指标','数值'], [['数据标签',data.get('data_label','真实记录；覆盖受限')],['统计范围',data['scope']],['快照截止',data['snapshot_cutoff']],
          *[[k,v] for k,v in data['summary'].items()],['口径','多标签占比可超过100%；跨平台播放量未去重受众']])
    sheet('品牌平台车型', ['品牌','平台','车型','视频数','账号数','播放合计','均值','中位数'],
          [[r[k] for k in ('brand','platform','model','videos','creators','views','average_views','median_views')] for r in data['brand_breakdown']])
    sheet('爆款视频', ['视频','标题','数据','关键词','内容方向'],
          [[v['url'],v['title'],video_metrics(v),v['keywords'],v['direction']] for v in data['viral_candidates']])
    sheet('效果与观察期', ['视频','形式','时长秒','分享','互动率百分比','公式','7天状态','7天播放','7天快照','30天状态','30天播放','30天快照','是否过期','可用状态'],
          [[v['url'],v['content_form'],v['duration_seconds'],v['shares'],v['interaction_rate'],v['interaction_formula'],v['age7']['status'],v['age7']['views'],v['age7']['observed_at'],
            v['age30']['status'],v['age30']['views'],v['age30']['observed_at'],v['stale'],v['availability']] for v in data['videos'] if v['statistics_eligible']])
    sheet('趋势口径与查询', ['系列','词','地区','渠道','范围','匹配','周','本周','上周','环比','部分周','采集时间','相关查询'],
          [[t[k] for k in ('series_id','query','geo','search_type','range_label','match_type','week','value','previous','change_label','partial','collected_at')]+[str(t['related']) if t['related'] else '不可用'] for t in data['trends']])
    sheet('红人扩展档案', ['平台','ID','名称','国家','所在地依据','语言','身份组','身份依据','首次观察合作','最近观察合作','基线样本','中位播放','爆款数','关注','备注','经纪信息','经纪来源'],
          [[c.get(k) for k in ('platform','account_id','creator','market','market_evidence','language','identity_group','identity_evidence','first_cooperation','last_cooperation','baseline_sample_count','baseline_median','viral_count','followed','notes','agency','agency_source')] for c in data['creators']])
    sheet('内容方向变化', ['方向','数量','占比百分比','对上周变化百分点'],[[r[k] for k in ('name','count','share','share_change_pp')] for r in data['directions']])
    sheet('关键信号', ['信号'], [[x] for x in data['weekly_signals']])
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()


def video_metrics(v):
    def n(x):return '不可用' if x is None else f'{x:,}'
    text=f"播放 {n(v['views'])}；赞 {n(v['likes'])}；评 {n(v['comments'])}；分享 {n(v['shares'])}"
    if v['observed_growth'] is not None:
        text+=f"；窗口增量 {n(v['observed_growth'])}（{v['growth_from']} 至 {v['growth_to']}）"
    if v['baseline_multiple'] is not None:text+=f"；同龄基线 {v['baseline_multiple']:g}倍"
    return text+f"；快照 {v['observed_at'] or '不可用'}"


def markdown(data):
    def n(x):return '不可用' if x is None else f'{x:,}'
    def cell(value):return str(value).replace('|','\\|').replace('\n',' ')
    s=data['summary']
    lines=[f"# Qronge 竞品周报 · {data['week']} 至 {data['end']}",
      f"{data.get('data_label','真实收录记录，覆盖受限')}。时区 {data['timezone']}；生成 {data['generated_at']}；快照截止 {data['snapshot_cutoff']}。",
      f"口径：{data['scope']}；折扣码/联盟链接优先，无两类线索的需人工审核；播放量至少 {data['minimum_views']:,}，未知播放不计。合作表示商业关联，不表示已核实付费赞助。",
      '## 关键信号',*['- '+x for x in data['weekly_signals']],
      '## 核心数据','| 指标 | 本周 |','|---|---:|',
      f"| 合作发布视频 | {s['published']} |",f"| 合作平台账号 | {s['creators']} |",
      f"| 达标待审核视频 | {s['pending']} |",f"| 官方内容（单列） | {s['official']} |",
      f"| 新发布视频累计播放 | {n(s['known_views'])} |",f"| 单条平均 / 中位播放 | {n(s['average_views'])} / {n(s['median_views'])} |",
      f"| 实际观察窗口增量（含历史视频） | {n(s['all_growth'])} |",f"| 本周首次发现 / 更新 | {s['discovered']} / {s['updated']} |",
      '## 趋势','| 搜索词 | 地区/渠道 | 本周热度 | 上周热度 | 环比 | 批次 |','|---|---|---:|---:|---|---|']
    rows=[t for t in data['trends'] if t['week']==data['week']]
    for t in rows:
        lines.append('| '+' | '.join(cell(v) for v in [t['query'],t['geo']+'/'+t['search_type'],n(t['value']),n(t['previous']),t['change_label'],t['series_id']])+' |')
    if not rows:lines.append('| 不可用：尚无本周可靠趋势数据 | — | — | — | — | — |')
    lines.append('内容方向：'+('；'.join(f"{r['name']} {r['count']}条（{r['share']:g}%）" for r in data['directions'][:5]) or '不可用')+'。')
    lines+=['## 爆款视频','| 视频 | 标题 | 数据 | 关键词 | 内容方向 |','|---|---|---|---|---|']
    for v in data['viral_candidates']:
        lines.append('| '+' | '.join([f"[打开视频]({v['url']})",cell(v['title']),cell(video_metrics(v)),cell('、'.join(v['keywords'])),cell('、'.join(v['direction']))])+' |')
    if not data['viral_candidates']:lines.append('| 暂无达标候选 | — | — | — | — |')
    lines.append('注：只统计已收录达标记录，非全网总量；播放未去重受众，增长为实际快照窗口；搜索指数为同批次相对热度，不跨批次相加。')
    formatted=[]
    for line in lines:
        if line.startswith('#'):
            if formatted and formatted[-1]!='':formatted.append('')
            formatted.extend([line,''])
        elif line.startswith(('|','- ')):
            marker='|' if line.startswith('|') else '- '
            if formatted and formatted[-1] and not formatted[-1].startswith(marker):formatted.append('')
            formatted.append(line)
        else:
            if formatted and formatted[-1]!='':formatted.append('')
            formatted.append(line)
    return '\n'.join(formatted)+'\n'
