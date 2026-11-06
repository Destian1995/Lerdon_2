import ast
import errno
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from turn_storage import check_turn_storage,is_storage_full,MIN_FREE_BYTES


def method(name,namespace):
    tree=ast.parse(Path('game_process.py').read_text(encoding='utf-8'))
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'game_process.py','exec'),namespace)
    return namespace[name]


class TurnStorageTests(unittest.TestCase):
    def test_checks_save_and_temporary_storage_without_writing(self):
        db=Mock();db.execute.return_value=[(0,'main',str(Path('game_data.db').resolve()))]
        with patch('turn_storage.shutil.disk_usage',return_value=SimpleNamespace(free=MIN_FREE_BYTES)) as usage:
            check_turn_storage(db)
            self.assertIn(Path('game_data.db').resolve().parent,[call.args[0] for call in usage.call_args_list])
        db.execute.assert_called_with('PRAGMA database_list')
        with patch('turn_storage.shutil.disk_usage',return_value=SimpleNamespace(free=0)):
            with self.assertRaises(OSError) as caught:check_turn_storage(db)
        self.assertEqual(caught.exception.errno,errno.ENOSPC)

    def test_full_disk_blocks_turn_before_increment_or_any_save(self):
        notify=Mock();process=method('process_turn',{'show_message':notify})
        screen=SimpleNamespace(conn=Mock(),end_turn_button=SimpleNamespace(disabled=False),turn_counter=4)
        with patch('turn_storage.check_turn_storage',side_effect=OSError(errno.ENOSPC,'full')):
            process(screen)
        self.assertEqual(screen.turn_counter,4)
        self.assertFalse(screen.end_turn_button.disabled)
        notify.assert_called_once()

    def test_abort_removes_overlay_and_does_not_claim_a_successful_turn(self):
        notify=Mock();abort=method('_abort_turn',{'show_message':notify})
        overlay=Mock();db=Mock()
        screen=SimpleNamespace(conn=db,end_turn_button=SimpleNamespace(disabled=True),_turn_overlay=overlay)
        abort(screen,sqlite3.OperationalError('database or disk is full'))
        self.assertTrue(screen._turn_failed)
        self.assertTrue(screen.end_turn_button.disabled)
        self.assertIsNone(screen._turn_overlay)
        overlay.dismiss.assert_called_once();db.rollback.assert_called_once()
        self.assertIn('Часть действий',notify.call_args.args[1])
        self.assertTrue(is_storage_full(OSError(errno.ENOSPC,'full')))
        self.assertFalse(is_storage_full(sqlite3.OperationalError('database is locked')))

    def test_worker_failure_calls_abort_even_when_error_logging_also_runs_out_of_space(self):
        callbacks=[]
        clock=SimpleNamespace(schedule_once=lambda callback,*args:callbacks.append(callback))
        process=method('process_turn',{'Clock':clock,'print':Mock(side_effect=OSError(errno.ENOSPC,'full'))})
        worker=next(n for n in ast.walk(ast.parse(Path('game_process.py').read_text(encoding='utf-8')))
                    if isinstance(n,ast.FunctionDef) and n.name=='_background_work')
        screen=SimpleNamespace(ensure_rebellion_ai_controller=Mock(side_effect=sqlite3.OperationalError('database or disk is full')),
                               _abort_turn=Mock(),_finish_turn=Mock())
        namespace=process.__globals__;namespace['self']=screen
        exec(compile(ast.Module(body=[worker],type_ignores=[]),'game_process.py','exec'),namespace)
        namespace['_background_work']()
        self.assertEqual(len(callbacks),1)
        callbacks[0](0)
        screen._abort_turn.assert_called_once();screen._finish_turn.assert_not_called()


if __name__=='__main__':unittest.main()
