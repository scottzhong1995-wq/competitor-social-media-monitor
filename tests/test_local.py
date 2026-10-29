import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from monitor.locking import lock_scheduler


class LocalTests(unittest.TestCase):
    def test_lock_rejects_second_process_and_releases_on_close(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/'scheduler.lock'
            command = [sys.executable, '-c',
                       'from monitor.locking import lock_scheduler; import sys; '
                       'f=open(sys.argv[1],"a+b"); lock_scheduler(f)', str(target)]
            with target.open('a+b') as handle:
                lock_scheduler(handle)
                blocked = subprocess.run(command, capture_output=True)
                self.assertNotEqual(blocked.returncode, 0)
                self.assertIn('RuntimeError', blocked.stderr.decode())
            released = subprocess.run(command, capture_output=True)
            self.assertEqual(released.returncode, 0, released.stderr.decode())

    def test_first_successful_night_backfills_then_switches_to_daily(self):
        self._night_sequence([None, None], [True, False])

    def test_failed_initial_backfill_is_retried_next_night(self):
        self._night_sequence([RuntimeError('test failure'), None], [True, True])

    def _night_sequence(self, outcomes, expected):
        main = importlib.import_module('monitor.__main__')
        real_connect = main.connect
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            moments = [datetime(2026,10,28,2,tzinfo=ZoneInfo('Asia/Shanghai')),
                       datetime(2026,10,29,2,tzinfo=ZoneInfo('Asia/Shanghai'))]
            with patch.object(main, 'ROOT', root), patch.object(main, 'datetime') as clock, \
                 patch.object(main, 'connect', side_effect=lambda: real_connect(root/'data/test.db')), \
                 patch('monitor.youtube.collect', side_effect=outcomes) as collect, \
                 patch.object(main.time, 'sleep', side_effect=[None, KeyboardInterrupt]):
                clock.now.side_effect = moments
                with self.assertRaises(KeyboardInterrupt):
                    main.schedule('Asia/Shanghai')
            self.assertEqual([c.kwargs['backfill'] for c in collect.call_args_list], expected)
            self.assertTrue(json.loads((root/'data/scheduler.json').read_text())['initial_backfill_completed'])


if __name__ == '__main__':
    unittest.main()
