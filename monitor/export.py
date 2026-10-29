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
            clean = [', '.join(map(str, x)) if isinstance(x, list) else x for x in row]
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
        ['数据截止', data['generated_at']], ['美国英语已确认新合作视频', s['confirmed_videos']],
        ['合作账号数', s['confirmed_creators']], ['已知累计播放', s['known_views']],
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
    sheet('本周发布视频', headers, [[v.get(k) for k in fields] for v in data['videos'] if v['new_in_week']])
    sheet('历史视频与效果', headers, [[v.get(k) for k in fields] for v in data['videos']])
    sheet('长短视频汇总', ['平台','格式','确认合作视频','已知累计播放','有播放数据条数'],
          [[r[k] for k in ['platform','format','videos','views','measured']] for r in data['breakdown']])
    fields = ['platform','creator','creator_url','followers','observed_at','creator_type','contact','contact_source','videos','confirmed']
    sheet('红人名单', ['平台','账号','主页','粉丝数','数据时间','红人类型','公开商务联系方式','联系方式来源','收录视频','确认合作视频'],
          [[r[k] for k in fields] for r in data['creators']])
    sheet('搜索趋势', ['同批次系列ID','搜索词','周起始','相对热度','周环比百分比','来源'],
          [[t[k] for k in ['series_id','query','week','value','change_percent','source']] for t in data['trends']])
    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()
