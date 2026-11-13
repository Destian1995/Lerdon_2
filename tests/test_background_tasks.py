import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from background_tasks import TaskGroup,WorkerCancelled


class BackgroundTaskTests(unittest.TestCase):
    def test_shutdown_waits_for_final_database_write_before_close(self):
        import sqlite3
        db=sqlite3.connect(':memory:',check_same_thread=False)
        self.addCleanup(db.close)
        db.execute('CREATE TABLE results(value)')
        group=TaskGroup();started=threading.Event()
        def work():
            started.set();group.stopping.wait()
            db.execute('INSERT INTO results VALUES(1)');db.commit()
        worker=group.start(work,'shutdown-db-test')
        self.assertFalse(worker.daemon)
        self.assertTrue(started.wait(2))
        group.shutdown()
        self.assertFalse(worker.is_alive())
        self.assertEqual(db.execute('SELECT value FROM results').fetchone()[0],1)
        with self.assertRaises(WorkerCancelled):group.start(lambda:None,'too-late')

    def test_closing_app_cancels_wait_for_unanswered_tactical_popup(self):
        from tactical_battle_bridge import request_battle
        from kivy.app import App
        from kivy.clock import Clock
        group=TaskGroup();scheduled=threading.Event()
        with patch('background_tasks.tasks',group),patch.object(App,'get_running_app',return_value=SimpleNamespace()), \
                patch.object(Clock,'schedule_once',side_effect=lambda *args:scheduled.set()):
            worker=group.start(lambda:request_battle([],[],'attacker'),'battle-wait-test')
            self.assertTrue(scheduled.wait(2))
            group.shutdown()
            self.assertFalse(worker.is_alive())

    def test_worker_exception_hook_is_finished_before_shutdown_returns(self):
        group=TaskGroup();reported=threading.Event();finished=threading.Event()
        def broken():raise RuntimeError('test failure')
        def hook(args):
            reported.set();group.stopping.wait();finished.set()
        with patch('threading.excepthook',hook):
            worker=group.start(broken,'exception-output-test')
            self.assertTrue(reported.wait(2));group.shutdown()
            self.assertTrue(finished.is_set());self.assertFalse(worker.is_alive())

    def test_original_exception_is_saved_before_interpreter_shutdown(self):
        import subprocess
        import sys
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as folder:
            log=Path(folder)/'crash.log'
            code="""
import sys
from runtime_diagnostics import install_crash_log
from background_tasks import tasks
install_crash_log(sys.argv[1])
def work():
    tasks.stopping.wait()
    print('worker stopped')
tasks.start(work,'shutdown-reproducer')
try:
    raise RuntimeError('original-mirror-error')
finally:
    tasks.shutdown()
"""
            result=subprocess.run([sys.executable,'-c',code,str(log)],capture_output=True,text=True,timeout=8)
            self.assertNotEqual(result.returncode,0)
            self.assertIn('original-mirror-error',log.read_text(encoding='utf-8'))
            self.assertNotIn('_enter_buffered_busy',result.stderr)
            self.assertIn('worker stopped',result.stdout)


if __name__=='__main__':unittest.main()
