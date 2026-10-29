# Q / RADAR · 竞品红人视频监控

Windows 11 本地安装与夜间运行：参见 [LOCAL_SETUP.md](LOCAL_SETUP.md)，依次运行 `01-install.cmd`、`02-dashboard.cmd`、`03-night.cmd`。安装包不包含密钥；本机启动需单独输入密钥。当前入口是手动启动，不是已经安装好的开机自启服务。

面向 Qronge 的中文竞品看板：美国英语市场，Yozma IN-10 / IN-10 Pro，Tuttio Soleil01 / Soleil01 GB Pro。目标回溯近90天，按洛杉矶时间周一至周日统计，导出 Excel 中文周报。

## 当前可用范围

- 网页看板：合作审核、品牌/平台筛选、车型与内容方向、标题词、高播放候选、红人及公开联系方式、数据覆盖和采集记录。
- SQLite 视频去重与历史快照；保留首次发现时间，重复采集不覆盖人工审核结论。
- Excel 六个工作表：口径与覆盖、本周发布视频、历史视频与效果、长短视频汇总、红人名单、搜索趋势。
- 可选 YouTube Data API v3：关键词发现与视频/账号指标更新。没有密钥时支持手动导入，不伪造数据。
- Instagram / TikTok：目前仅导入有来源的 JSON，**没有自动发现或全量采集**。Google Trends 目前仅导入整理后 CSV。
- 夜间调度程序已实现但**未启动、未部署**。运行时区已确认为北京时间，凌晨02:00采集、周二03:00出报。统计时区固定 `America/Los_Angeles`。
- 无 Codex API / 模型调用，不购买数据或 token；用户账户中的 Codex 额度不能当作平台接口密钥。程序不承诺无限免费采集或全网覆盖。

## 本地运行

Python 3.12+，仅第三方依赖为 openpyxl 3.1.5。无需 Node、Docker、PostgreSQL 或付费服务。

```sh
cd /workspace/competitor-social-media-monitor
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m monitor init
.venv/bin/python -m monitor serve --port 8000
```

浏览器访问本机8000端口。服务仅监听 loopback；还没有公网部署、登录或多人权限。上线前需添加身份验证、HTTPS、备份和持久化宿主机。数据库默认 `data/monitor.db`，周报默认 `reports/`；可用 `MONITOR_DB`、`MONITOR_REPORTS` 覆盖。两者均不提交 Git。

云任务已经隔离，直接使用现有 checkout；除非用户要求，不创建额外 Git worktree。

## 导入与审核

看板“数据与设置”上传 JSON / CSV，也可执行：

```sh
python3 -m monitor import /path/to/actual-videos.json
python3 -m monitor trends /path/to/actual-trends.csv
python3 -m monitor export
python3 -m monitor export --week 2026-10-19
```

`examples/` 只有结构模板，**不是采集结果，不能原样作为监控数据导入**。模板视频的占位 ID 应替换成真实11位 YouTube ID；必填的时间需带时区。未知指标使用 `null`，不能填0代替缺失。

视频必填 `platform`、`url`、`title`、`creator`、`published_at`、`source`。平台名为 `YouTube`、`Instagram`、`TikTok`。只支持对应平台 HTTPS 完整视频链接，自动去掉跟踪参数。更多字段参见模板与看板说明。

赞助、赠品、折扣码和联盟字样只生成**待核实线索**。在看板审核证据、市场和语言后，才进入美国英语确认合作汇总。搜索地区过滤、英语标题均不能证明美国受众；需人工依据账号信息和内容判断。`format` 为 `long`、`short` 或 `unknown`，不会仅按时长判断 Shorts。品牌官方自有内容可标记“排除”。

跨平台重复内容使用相同 `content_group` 人工关联；没有值则按不同发布计。公开邮箱/联系入口用 `contact`、`contact_source` 导入，不推测私人联系方式。

## 免费 YouTube 接入（可选，尚未实网验证）

在自己的 Google Cloud 项目启用 YouTube Data API v3，创建并限制 API key，安全设置环境变量 `YOUTUBE_API_KEY`，不要把值提交 Git 或发到聊天中。使用免费配额，不开通付费采集服务。没有 key 的情况下，本仓库不能自动搜索 YouTube；无须提供 Google 登录密码。

云环境草稿已登记可选个人密钥 `YOUTUBE_API_KEY` 和目标域名 `www.googleapis.com`，请在环境设置中安全填写。请求通过 `X-Goog-Api-Key` 头发送，保留平台代理注入路径。草稿保存不代表密钥已经生效或环境已发布；需要用户在环境设置中检查、保存并发布，之后再验证真实 API 调用。

网络需允许 `www.googleapis.com`。品牌链接仅作监控清单，不代表已抓取官网。

```sh
python3 -m monitor collect --backfill
python3 -m monitor collect
```

首次回溯90天，6个搜索词每词最多2页，每页50条；常规任务发现近7天视频，每词1页，并刷新已收录90天视频。按现行配额计价，搜索部分最多约1200/600单位，另加详情与账号请求。请以 Google 控制台实际配额为准。结果不保证全量；删除、隐藏指标或搜索遗漏需在覆盖说明中保留。最多2000条待更新视频，超限报错，不静默丢弃。

`regionCode=US` / `relevanceLanguage=en` 是搜索相关性过滤，API导入的市场仍为未知。API无可靠 Shorts 字段，格式保持未知。新增视频先审核，避免把普通提及计为合作。接入验证目前依靠模拟响应测试；没有真实 key，不声称真实采集成功。

## 搜索趋势

从 Google Trends 选择 United States、Web Search、品牌词/车型词，下载周数据并整理成 `examples/trends.template.csv` 的列。只导入完整周，`week` 是周一日期，`value` 在0–100，`geo=US`，`search_type=web`。日数据不可直接当周数据导入。Google导出如以周日起算，需依据日期区间重新整理，不能只改日期标签。

`series_id` 表示**相同查询集合、时间范围、筛选条件、同次下载**的归一化批次。每次重新下载用新 ID，不能跨下载复用。环比只比较同系列同词相邻完整周；前周为0时环比留空。Google Web 热度不是绝对搜索量，也不是社交平台站内搜索量。低量词缺数据不补0。

## 时区与夜间运行

运行时区**已确认为北京时间**，默认每天02:00采集、周二03:00出完整美国周报。调度尚未启用；保留以下两种显式模式：

| 模式 | 采集窗口 | 出报窗口 | 统计周 |
|---|---|---|---|
| 洛杉矶 | 每天02:00–02:59 | 周一03:00–03:59 | 洛杉矶周一00:00至下周一00:00 |
| 北京 | 每天02:00–02:59 | 周二03:00–03:59 | 同上 |

北京时间周一凌晨美国周日尚未结束，所以北京凌晨出完整美国周报需到周二。夏令时由 IANA 时区规则处理，洛杉矶春季跳过02点时当日采集跳过，**不白天补跑**。任务睡眠检查不调用模型。调用 `collect`/`export` 是手动执行，不受调度窗口约束。

在可持续运行、支持安全环境变量和持久磁盘的宿主机上启动（默认北京时间）：

```sh
python3 -m monitor schedule --timezone Asia/Shanghai
# 默认等价于 python3 -m monitor schedule
```

调度器在窗口内最多尝试一次，用磁盘状态避免重复；失败写运行记录，下次计划再尝试，不在白天补采。单机文件锁防止重复启动。必须由宿主机进程管理器保持进程存活；关闭Codex任务不等于程序会继续运行。报告保存在本机，不自动发邮件或飞书。

## 数据口径与局限

- 合作数：本周发布＋明确合作＋市场US＋语言en。品牌同时出现的视频可能分属两个品牌，品牌数不能简单相加当去重总数。
- 默认显示上个完整周；选择进行中的周会标记不完整。历史报告只用该周末以前的快照，不把今天的累计播放伪装成过去的数值。
- 累计播放是已知快照汇总，空值不计，显示指标覆盖条数；跨平台播放量不是去重触达。
- “观测区间增量”仅两次真实观测相减，显示起止时间；无基线留空，负值标记指标回调。它可能不覆盖整个统计周，不能当整周新增播放。无法事后恢复过去90天逐日播放变化。
- 高播放候选：长视频5万、短视频/未知格式10万。无红人历史基线和自然流量数据，不能据此确认相对爆款或解释因果；可人工查看原视频分析选题、开场、卖点和评论。
- 红人账号按平台＋主页识别；主页缺失时用账号名，可能需要人工合并。粉丝数据附观测时间。
- 当前包含规则分类与标题词提取，没有模型驱动的完整爆款复盘、自动 Google Trends 或 Instagram/TikTok 采集。

## 验证

```sh
python3 -m unittest discover -s tests -v
```

测试使用隔离临时数据库和明确的测试内容，不写入实际监控库。覆盖合作审核、去重、车型、快照、跨时区周界、夜间调度、搜索趋势系列隔离、Excel、YouTube适配器。启动后 `/health` 检查服务与数据库，`/api/report` 检查看板数据，`/api/export` 下载真实 XLSX。
