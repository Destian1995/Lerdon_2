import unittest
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from turn_ui_guard import database_busy


class TurnUiGuardTests(unittest.TestCase):
    def test_busy_while_worker_alive_even_after_overlay_removed(self):
        worker=Mock()
        worker.is_alive.return_value=True
        screen=SimpleNamespace(conn=object(),_turn_thread=worker,_turn_overlay=None)
        self.assertTrue(database_busy(screen=screen))
        worker.is_alive.return_value=False
        self.assertFalse(database_busy(screen=screen))

    def test_different_database_is_not_blocked(self):
        screen=SimpleNamespace(conn=object(),_turn_overlay=object())
        self.assertFalse(database_busy(object(),screen))
        self.assertTrue(database_busy(screen.conn,screen))

    def test_failed_turn_does_not_restart_database_polling(self):
        self.assertTrue(database_busy(screen=SimpleNamespace(_turn_failed=True)))

    def test_capture_refresh_is_deferred_while_turn_worker_owns_database(self):
        tree=ast.parse(Path('game_process.py').read_text(encoding='utf-8'))
        method=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='refresh_map')
        screen=SimpleNamespace(_turn_overlay=object(),conn=Mock(),update_army_rating=Mock())
        namespace={'_active_game_screen':screen}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'game_process.py','exec'),namespace)
        namespace['refresh_map']()
        screen.conn.execute.assert_not_called()
        screen.update_army_rating.assert_not_called()
