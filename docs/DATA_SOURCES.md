# 数据源与字段合同

| 来源 | 当前实现 | 可获得 | 缺口 |
|---|---|---|---|
| YouTube Data API v3 | 凭据已实际验证；分页、限流/5xx重试、关键词和指定账号发现、视频刷新 | 标题、描述、ID、发布时间、时长、播放、赞、评、订阅数 | 不提供一般视频分享数、真实受众国家、可靠Shorts标记或任意视频字幕；不抓取未授权评论 |
| Instagram | 有来源JSON导入、快照、账号补录 | 导入提供的字段，Reels单列 | 未接自动发现和刷新；不要以语言推断国家 |
| TikTok | 有来源JSON导入、快照、账号补录 | 导入提供的字段，TikTok独立形式 | 未接自动发现和刷新 |
| Google Trends | CSV导入，相关查询JSON导入 | 12周指数、零基数环比、地区/渠道/范围/匹配/批次 | 未接自动API；相关查询未导入时不可用 |
| 官网词库核验 | `python -m monitor verify` 输出证据台账 | 页面标题与官网直接链接的社交账号候选 | 当前官网连接未成功，显示名与账号仍待核验；未凭频道名称判定官方身份 |

YouTube参数和配额以Google控制台实际规则为准。当前初次回溯每词最多配置页数（默认2），常规1页，指定账号最新12条；查询日志记录完成、截断或失败。搜索地区和语言只是相关性参数。指定监控账号发现的无竞品词视频作为 baseline_only 样本持续积累同龄快照；不计合作数量。账号自有内容需人工核实官网链接后分类为“品牌官方内容”。

导入沿用 `examples/videos.template.json`。新增字段：`creator_id`、`duration_seconds`、`shares`、`summary_zh`、`market_evidence`、`language_evidence`、`evidence_source`、`baseline_only`、`materials`。`baseline_only=true` 可收录无竞品词的创作者普通视频作为基线样本，默认不进入监控视频和合作数量；同一个账号ID和内容形式应保持一致。

合作状态接受“已确认合作/明确合作”“疑似合作/线索待核实”“普通品牌提及/普通提及”“品牌官方内容”。“排除”保留作为人工排除状态。最新口径优先识别实际折扣码/联盟链接，归为商业关联合作（内部沿用“明确合作”字段，不表示已确认付款或赠品安排）；两类都没有的需审核。明确人工导入和审核结果保留。普通购买链接、UTM和否定的折扣码措辞不自动纳入。所有统计至少1000播放，未知值不计；基线样本仍保留，避免选择偏差。

账号录入字段：`platform, account_id, creator, creator_url, market, market_evidence, language, language_evidence, creator_type, contact, contact_source, agency, agency_source, notes, followed, monitor, identity_group, identity_evidence`。跨平台合并只在 identity_group 和 identity_evidence 都有值时发生。账号即使没有视频或表现低也不删除。YouTube账号监控需真实 `UC...` ID，不能以显示名当频道ID。

分析材料示例：
```json
{"opening":{"note":"开头展示了爬坡测试条件","source":"https://www.youtube.com/watch?v=真实ID","kind":"观察"}}
```
只有人工实际获取材料后才录入；`kind` 为“观察”或“推测”。系统默认摘要仅按标题、描述做规则概括，不代表观看视频或完整翻译；没有封面、字幕或评论就不分析它们。

趋势CSV必填：`series_id,query,week,value,source,geo,search_type`；可选 `range_label,match_type,collected_at,partial`。同系列固定地区、渠道、匹配方式和范围；每次重新下载/归一化需新系列ID。`search_type` 为 `web` 或可靠数据的 `youtube`。周一至周日；不足整周标记 `partial=1` 后不计算环比。低样本无值不补0。相关查询JSON数组字段 `series_id,query,kind,term,value,source`，`kind=top/rising`，来源不可缺。

数据库采用增量列迁移，旧数据保留；升级前停止本机采集并备份 `data/`。单条视频的人工审核有前后值日志，刷新不会覆盖已审核字段。删除/隐藏记录标记不可用并保留旧快照；接口失败不清零，超过48小时无有效快照在当前观察截止点标为过期。

所有指标都来自同一个 `report()` 结果供看板、Excel、Markdown使用。历史周默认排除周末后的快照，迟到数据不冒充过去播放量；当前人工修正会影响历史周分类，审计日志可追溯。观察期7/30天快照要求在目标年龄至容差内，默认24小时；无值则标记未满期或缺快照。互动率为(赞+评+[可用时分享])/播放量×100%，任何赞/评/播放缺失均不可用；缺失分享不声称完整互动率。
