# Q / RADAR · Qronge竞品红人合作视频监控 V2

美国英语市场起步，首批Yozma、Tuttio。品牌、车型、检索词、平台、目标国家、语言和统计时区可在看板配置。国家不明保留未知，不按语言推断所在地。

## 已实现

- 六个中文页面：周度总览、视频监控、爆款候选、12周搜索趋势、红人名单、配置与采集状态。
- 合作证据和人工审计；确认/疑似/普通提及/官方内容分开，默认确认合作口径。
- 分别统计本周发布、发现、更新；视频ID去重、账号去重、有依据的跨平台身份合并和内容组。
- 历史快照、真实观察窗口增量、长短形式、7/30天观察期、均值/中位数、来源与缺失值。
- 平台/形式绝对高播放阈值；同账号同形式同龄快照的最近10–12条中位数基线，默认3倍。样本不足不输出精确倍数。
- 红人公开商务档案、关注/备注、公开来源、可搜索筛选；不自动联系红人。
- Excel多工作表和中文Markdown周报，共用后端统计结果，保留证据链接和数据限制。
- YouTube实际单条API验证成功；关键词分页发现、指定账号最新视频/基线样本、刷新、限流重试、删除隐藏标记和日志。

## 当前限制

- **Instagram、TikTok仅手动导入，未接授权自动发现。Google Trends为CSV与相关查询JSON导入，未接自动接口。**
- **品牌官网请求当前未连通，车型显示名、匹配拼写与官方账号仍待官方核验。** 用户提供的官网/产品URL保留，未凭记忆补全账号。核验台账见 [docs/official-verification.json](docs/official-verification.json)。
- 自动分类只提出线索；国家、合作、YouTube Shorts需审核。视频/字幕/封面/评论未实际获取时，不分析相关内容。中文摘要默认是明确标记的标题/描述规则概括，不代表观看视频或完整翻译。
- 首次采集不能恢复过去90天逐日播放历史；搜索/账号最新视频分页有上限，不保证全网覆盖。播放量不是独立触达，不推算订单或ROI。
- 定时任务模板已交付，**未在云环境或你的Windows电脑自动安装启用**。Codex快照不保证常驻运行；没有邮件或飞书自动推送。

## Windows 11使用

先停止旧的看板/夜间进程，备份并保留原 `data/`。解压新版代码到固定目录；安装Python3.12+（勾选Add Python to PATH），依次双击：

1. `01-install.cmd`：安装依赖，自动迁移数据库，保留旧数据。
2. `02-dashboard.cmd`：启动本机看板，按终端提示在浏览器打开。
3. `03-night.cmd`：在隐藏提示中输入本机的YouTube key，保持该窗口运行；云端密钥不会同步到本机。

当前为手动启动，重启后需重新启动；登录自动任务模板及服务器配置见 [运行与升级说明](docs/OPERATIONS_V2.md)。锁屏可以，电脑仍需开机联网且不睡眠。默认北京时间每天02点采集、周二03点生成完整美国周报，不白天补跑。

## 开发运行

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m monitor init
.venv/bin/python -m monitor serve --port 8000
.venv/bin/python -m monitor export
```

Windows解释器路径为 `.venv\Scripts\python.exe`。报告生成到 `reports/`，数据库在 `data/`，密钥通过环境变量 `YOUTUBE_API_KEY`；都不提交Git。`MONITOR_DB`、`MONITOR_REPORTS`、`MONITOR_CONFIG` 可覆盖默认路径。每个云任务已隔离，使用现有checkout；用户没有明确要求时不创建Git worktree。

YouTube可使用免费API配额，不购买数据服务；实际配额规则以Google控制台为准。服务只监听本机，尚未配置公网认证或多人权限。

## 文档、示例与验收

- [数据源能力与字段说明](docs/DATA_SOURCES.md)
- [运行、升级与定时配置](docs/OPERATIONS_V2.md)
- [Windows详细步骤](LOCAL_SETUP.md)
- [合成演示周报](examples/demo-output/demo-weekly.md) / [Excel](examples/demo-output/demo-weekly.xlsx)：全部标记DEMO，与真实数据隔离。
- [真实单条接口验证](examples/live-check/validation.json) / [报告](examples/live-check/live-check.md)：非全量监控，不认定合作。
- [看板截图](docs/dashboard-v2.png)：使用隔离DEMO库，未填充真实监控库。

```sh
.venv/bin/python -m unittest discover -s tests -v
# 可选浏览器验证，需要Playwright和Chromium
python3 scripts/browser_check.py
# 会使用API配额的真实单条验证；不修改正式监控库
python3 scripts/live_check.py
```

核心验证覆盖去重、合作/官方分类、周界与夏令时、长短分组、快照增长、零基数、缺失、同龄基线、审核保护、身份合并依据、限流/分页/删除保留，以及看板/Excel一致性。Linux测试和浏览器已执行，Windows原生任务/锁及systemd部署仍需在目标机器验证。
