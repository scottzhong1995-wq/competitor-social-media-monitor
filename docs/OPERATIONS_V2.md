# V2 运行与升级

已实现六个中文页面，统一周/品牌/平台/车型/形式/统计范围过滤，以及人工录入、审核、账号档案、词库和阈值配置。默认美国英语；“纳入其他/未知市场”显式切换统计范围。

## 本地启动

先停止旧的夜间任务和看板进程。升级时替换代码，保留 `data/`（先停止写入再备份）。

```sh
python -m venv .venv
# Windows使用 .venv\Scripts\python.exe；Linux/macOS使用 .venv/bin/python
python -m pip install -r requirements.txt
python -m monitor init
python -m monitor serve --port 8000
```

上述命令须使用同一虚拟环境解释器；Windows仍可使用 `01-install.cmd`、`02-dashboard.cmd`、`03-night.cmd`。`YOUTUBE_API_KEY` 只通过环境变量或本机隐藏提示传入，不写入代码。云端的代理密钥不会自动传入你的Windows电脑。

```sh
python -m monitor export
python -m monitor verify
python -m monitor schedule --timezone Asia/Shanghai
```

示例文件在 `examples/demo-output/`（全部合成）和 `examples/live-check/`（单条真实API验证，非正式监控库）。

`export` 生成相同统计范围的 XLSX 和中文 Markdown，目录 `reports/`。页面导出沿用页面统一筛选条件。默认上一完整周；要看刚采到的播放量，选择当前周周一日期（标记为进行中）。旧视频可以本周更新，不能计入本周发布。`MONITOR_DB`、`MONITOR_REPORTS`、`MONITOR_CONFIG` 可重定向存储，配置默认 `data/settings.json`，初始值来自 `config/brands.json`。

## 定时配置（交付，未在云端安装启用）

保持原约定：北京时间每天02点采集，周二03点生成完整洛杉矶周报；不白天补跑。运行时区与统计时区分开配置，统计时区可在看板修改。调度时区支持上海和洛杉矶两个经过测试的预设，其他调度时区需另配外部调度器；不能宣称任意时区的出报窗口都已经验证。自定义统计时区时须确保出报时上周已结束。

Windows手动方式：保持 `03-night.cmd` 窗口运行。自动方式模板：

1. 在Windows当前用户的环境变量中安全设置 `YOUTUBE_API_KEY`。
2. 在项目目录执行 `powershell -NoProfile -File deploy\install-windows-task.ps1`。该脚本登记**用户登录后**启动的任务，不自动启动它；需要符合本机PowerShell策略，不建议全局关闭执行策略。
3. 关闭旧夜间窗口，在“任务计划程序”中找到 `QrongeMonitor`，手动运行一次验证。日志 `data/scheduler.log`。该交互用户任务要求保持登录；锁屏可，注销/关机不可。
4. 停止并删除该任务即可撤销自动运行。此脚本未在Windows真机执行，只交付配置，需本机验证。

Linux服务器方式：`deploy/qronge-monitor.service` 是 systemd 模板；把代码/虚拟环境部署到 `/opt/qronge-monitor`，建立 `qronge` 运行用户，授予该用户data/reports目录写权限，在 `/etc/qronge-monitor.env` 安全设置密钥并限制文件权限，再安装/启用服务。此环境未执行systemd部署，也没有购买服务器或配置公网访问。

发布Codex快照不保证持续进程或定时调度。当前服务仅本机监听；公网多人部署仍需HTTPS、认证、备份策略。没有自动邮件或飞书推送，没有自动联系红人。

## 验收

`python -m unittest discover -s tests -v` 验证去重、合作/官方分类、时区及夏令时、快照增长、零基数、缺失、同龄基线、人工审核保护、身份合并证据与网页/Excel一致性。运行隔离浏览器验证后，可查看 `docs/dashboard-v2.png`。演示样本与真实验证样本分别有清晰标签，均不写入真实数据库。

官网核验尚未通过：需要环境允许 `yozmasport.com`、`tuttiosport.com` 并实际连通后运行 `verify`。网络域名已追加到草稿，保存草稿不代表运行实例已经应用或发布。当前可继续录入和采集YouTube，但不能声称已核验官方账号和车型拼写。


## 看板模块分析（保留）

六个页面及总览的品牌/车型、内容方向、曝光表现仍提供数据事实、总结、Qronge待验证行动和证据限制。分析基于顶部筛选与规则计算，不调用收费模型。列表内搜索仅缩小明细。爆款卡片仍可查看人工材料、同龄基线和增长窗口，但周报不再展开这些长篇内容。

## 最新统计与简版周报口径

优先从真实折扣码和联盟链接识别商业合作关联，证据按“折扣码、联盟链接、其他披露”排序。没有两类证据的新内容进入待审核；人工确认后照常纳入合作。自动识别表示商业关联，不表示确认付费赞助、赠品安排或费用。已人工修正和明确导入的分类保留，普通购买链接、UTM标签、否定的折扣码措辞不自动确认。

统计门槛 `minimum_views=1000`（可提高，不可低于1000）。以对应周截止前快照为准；低于1000、播放量未知均不计合作数量、播放合计、内容分布及爆款清单，仍保留在视频库和账号档案供补数/审核。已确认或官方内容也遵守门槛。历史周比较使用历史截止点的播放量，不以今天跨过门槛回填；基线样本不按此门槛删减，避免抬高基线。

爆款清单遵循当前合作范围与市场，默认不包含待审核和普通提及；可切换范围单独查看。周报只保留“关键信号、核心数据、趋势、爆款视频”。爆款表固定五列：视频、标题、数据、关键词、内容方向；不再输出长篇分析、材料备注或行动建议。Excel同样使用五列爆款表，保留必要数据明细；看板分析区仍可查看细节。此前文档中关于长版周报/深度分析工作表的说明由本段替代。
