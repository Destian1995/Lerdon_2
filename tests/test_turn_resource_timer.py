import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from test_main_map_intrigues import fixture
import main_map_intrigues as plots


def timer():
    tree=ast.parse(Path('game_process.py').read_text(encoding='utf-8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and any(isinstance(m,ast.FunctionDef) and m.name=='update_cash' for m in n.body))
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='update_cash')
    ns={}
    exec(compile(ast.Module(body=[method],type_ignores=[]),'game_process.py','exec'),ns)
    return ns['update_cash']


class TurnResourceTimerTests(unittest.TestCase):
    def test_timer_cannot_commit_intrigue_savepoint_during_turn(self):
        db=fixture();self.addCleanup(db.close)
        writes=Mock(side_effect=db.commit)
        screen=SimpleNamespace(_turn_overlay=object(),faction=SimpleNamespace(update_cash=writes),resource_box=Mock())
        callback=timer()
        # Simulate the UI timer firing while the background worker is inside
        # the intrigue transaction, without timing-dependent real threads.
        with patch.object(plots,'_refresh_companion',side_effect=lambda *args:callback(screen,5)):
            plots.advance(db,'Север')
        writes.assert_not_called()
        screen.resource_box.update_resources.assert_not_called()
        self.assertEqual(db.execute('SELECT COUNT(*) FROM map_intrigue_offers').fetchone()[0],1)
        db.rollback()
        self.assertEqual(db.execute('SELECT COUNT(*) FROM map_intrigue_offers').fetchone()[0],0)

    def test_timer_resumes_after_turn_but_stays_stopped_after_failure(self):
        callback=timer()
        screen=SimpleNamespace(_turn_overlay=None,_turn_failed=True,faction=Mock(),resource_box=Mock())
        callback(screen,5)
        screen.faction.update_cash.assert_not_called()
        screen._turn_failed=False
        callback(screen,5)
        screen.faction.update_cash.assert_called_once_with()
        screen.resource_box.update_resources.assert_called_once_with()


if __name__=='__main__':unittest.main()
