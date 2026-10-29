# 在你自己的电脑上运行

已确认使用 **Windows 11**。安装 Python 后，解压到固定目录，依次双击 `01-install.cmd`、`02-dashboard.cmd`、`03-night.cmd`。如双击无效，可使用下面的 PowerShell 命令排查。三个 CMD 文件会保留窗口以显示结果或错误。

此包不包含 API 密钥、历史监控数据、Linux虚拟环境或已生成的周报。它没有替你远程安装、开机自启或开启邮件推送。

## 第一次安装

1. 安装 Python 3.12 或更高版本：[python.org/downloads](https://www.python.org/downloads/)。Windows 安装时勾选 **Add python.exe to PATH**。
2. 解压安装包到固定目录，不要在 ZIP 内直接运行；避免 OneDrive/iCloud 同步目录。
3. 在该目录打开终端。Windows 使用 PowerShell，Mac 使用“终端”。
4. 执行安装命令：

Windows：
```powershell
py -3 local_launch.py setup
```

Mac：
```sh
python3 local_launch.py setup
```

如果提示版本不符，请先安装新版本 Python，不要使用 macOS 自带的旧版解释器。安装只下载公开 Python 依赖，不需要 Google Cloud 付费服务。

## 打开看板

Windows：`py -3 local_launch.py dashboard`

Mac：`python3 local_launch.py dashboard`

等待看到服务启动消息后，在本机浏览器打开 `http://127.0.0.1:8000`。这是你的电脑本地地址，不是已经部署好的公网网站；从其他设备无法访问。初始看板没有数据是正常的。

## 开启夜间任务

另开一个终端，进入同一目录执行：

Windows：`py -3 local_launch.py night`

Mac：`python3 local_launch.py night`

按提示粘贴你在 Google 创建的真实 API key；输入不会显示，不会写入文件，也不要把它贴到聊天中。云环境保存的密钥不会自动同步到你自己的电脑。某些终端按 Ctrl+V 无效时用右键粘贴。输入完成按 Enter。

保持该窗口打开；锁屏或熄屏可以，不能关闭该窗口、关机、睡眠或休眠。程序不调用模型，不消耗 Codex token。首次成功的北京时间02点采集回溯近90天（关键词和分页有上限，不保证全量），以后每日02点发现近7天内容并刷新已有90天视频。北京时间周二03点生成完整美国上周周报；白天不会补跑。

周报在安装目录 `reports/` 下，也可在看板下载；Excel“已确认合作”需要先在看板审核合作证据、美国市场、英语及长短视频。待核实视频仍会保留在报表中。

## 重启与数据

- 当前是**手动启动的夜间调度**，还没有安装系统开机自启任务。重新开机后需要重新执行 `night` 并输入密钥；看板也需重新启动。
- 关闭终端会停止对应进程。`Ctrl+C` 可主动停止。不要启动多个夜间调度进程。
- 数据存放在 `data/`，周报在 `reports/`。升级时保留这些目录；备份时不要对正在写入的数据库直接做不一致的复制。
- Instagram / TikTok 与 Google Trends 当前仅支持导入，不会因 YouTube key 配好而自动接通。
- 安装包在 Linux 环境完成自动化与浏览器验证；Windows/macOS 真机仍需要按上述步骤完成首次启动验证。如报错，提供错误文字，不要提供密钥。
