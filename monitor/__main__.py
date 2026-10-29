import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .core import ROOT, connect, import_trends, import_videos, report
from .export import workbook
from .locking import lock_scheduler


def export(db, week=None):
    data = report(db, week)
    target = Path(os.environ.get('MONITOR_REPORTS', ROOT/'reports'))
    target.mkdir(parents=True, exist_ok=True)
    path = target / f'weekly-{data["week"]}.xlsx'
    temp = path.with_suffix('.tmp')
    temp.write_bytes(workbook(data))
    temp.replace(path)
    return path


def due_jobs(now, state, zone):
    today = now.date().isoformat()
    report_day = 0 if zone == 'America/Los_Angeles' else 1
    return (2 <= now.hour < 3 and state.get('collection') != today,
            now.weekday() == report_day and 3 <= now.hour < 4 and state.get('report') != today)


def schedule(zone):
    tz = ZoneInfo(zone)
    if zone not in ('America/Los_Angeles', 'Asia/Shanghai'):
        raise ValueError('支持 America/Los_Angeles 或 Asia/Shanghai')
    # Requires a continuously running host. No Codex/LLM calls are made.
    state_file = ROOT/'data/scheduler.json'
    state_file.parent.mkdir(parents=True, exist_ok=True)
    with (state_file.parent/'scheduler.lock').open('a+b') as lock:
        lock_scheduler(lock)
        _schedule_loop(zone, tz, state_file)


def _schedule_loop(zone, tz, state_file):
    print(f'调度器已启动：{zone} 每天02点采集，' + ('周一03点' if zone=='America/Los_Angeles' else '周二03点') + '出完整美国周报；不会调用模型或购买配额', flush=True)
    while True:
        now = datetime.now(tz)
        state = json.loads(state_file.read_text()) if state_file.exists() else {}
        if state.get('timezone') != zone:
            state = {'timezone': zone}
        today = now.date().isoformat()
        # Strict night window: missed runs are not replayed during the day.
        collect_due, report_due = due_jobs(now, state, zone)
        if collect_due:
            from .youtube import collect
            with connect() as db:
                try:
                    print(collect(db, backfill=not state.get('initial_backfill_completed')), flush=True)
                    state['initial_backfill_completed'] = True
                except RuntimeError as e:
                    print(str(e), flush=True)
            state['collection'] = today
        if report_due:
            with connect() as db:
                print('周报已生成：' + str(export(db)), flush=True)
            state['report'] = today
        state_file.parent.mkdir(parents=True, exist_ok=True)
        temp = state_file.with_suffix('.tmp')
        temp.write_text(json.dumps(state))
        temp.replace(state_file)
        time.sleep(30)


def main():
    parser = argparse.ArgumentParser(description='美国英语竞品红人视频监控（无付费服务依赖）')
    sub = parser.add_subparsers(dest='cmd', required=True)
    sub.add_parser('init')
    web = sub.add_parser('serve'); web.add_argument('--port', type=int, default=8000)
    imp = sub.add_parser('import'); imp.add_argument('path')
    trend = sub.add_parser('trends'); trend.add_argument('path')
    out = sub.add_parser('export'); out.add_argument('--week')
    collect = sub.add_parser('collect'); collect.add_argument('--backfill', action='store_true')
    sched = sub.add_parser('schedule'); sched.add_argument('--timezone', choices=['America/Los_Angeles','Asia/Shanghai'], default='Asia/Shanghai')
    args = parser.parse_args()
    if args.cmd == 'serve':
        from .web import serve
        return serve(port=args.port)
    if args.cmd == 'schedule':
        return schedule(args.timezone)
    with connect() as db:
        if args.cmd == 'init':
            print('数据库已初始化；未填充虚构监控数据')
        elif args.cmd == 'import':
            print('导入记录：', import_videos(db, json.loads(Path(args.path).read_text())))
        elif args.cmd == 'trends':
            print('导入趋势：', import_trends(db, Path(args.path).read_text()))
        elif args.cmd == 'export':
            print(export(db, args.week))
        elif args.cmd == 'collect':
            from .youtube import collect
            print(collect(db, args.backfill))


if __name__ == '__main__':
    main()
