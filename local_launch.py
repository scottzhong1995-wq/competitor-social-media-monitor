"""Local entry point. No credentials are included or saved by this launcher."""
import getpass
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    if sys.version_info < (3, 12):
        raise SystemExit('Please install Python 3.12 or newer from python.org first.')
    os.chdir(ROOT)
    action = sys.argv[1] if len(sys.argv) > 1 else 'help'
    python = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if action == 'setup':
        if not python.exists():
            subprocess.check_call([sys.executable, '-m', 'venv', str(ROOT/'.venv')])
        subprocess.check_call([str(python), '-m', 'pip', 'install', '-r', 'requirements.txt'])
        subprocess.check_call([str(python), '-m', 'monitor', 'init'])
        print('Installation complete. Start dashboard and night in separate windows.')
        return
    if action not in {'dashboard', 'night'}:
        print('Usage: python local_launch.py setup | dashboard | night')
        return
    if not python.exists():
        raise SystemExit('Run setup first.')
    if action == 'dashboard':
        # Open only a local dashboard; no credentials are exposed to the browser.
        print('After the server starts, open http://127.0.0.1:8000 in your browser.')
        command = ['serve', '--port', '8000']
    else:
        if not os.environ.get('YOUTUBE_API_KEY'):
            key = getpass.getpass('Paste your YouTube API key (input hidden; not saved): ').strip()
            if not key:
                raise SystemExit('No key entered; scheduler not started.')
            os.environ['YOUTUBE_API_KEY'] = key
        print('Keep this window open and the computer awake/online. Ctrl+C stops the scheduler.')
        print('Beijing time: daily 02:00 collection; Tuesday 03:00 Excel. No daytime catch-up.')
        print('The first successful nightly collection backfills 90 days. No email delivery is configured.')
        command = ['schedule', '--timezone', 'Asia/Shanghai']
    try:
        raise SystemExit(subprocess.call([str(python), '-m', 'monitor', *command]))
    except KeyboardInterrupt:
        print('\nStopped. Restart this launcher to resume.')


if __name__ == '__main__':
    main()
