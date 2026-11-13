import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
import sys
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
    def test_cleanup_cancels_periodic_events_once(self):
        tree=ast.parse(Path('game_process.py').read_text(encoding='utf-8'))
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GameScreen')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='cleanup')
        clock=Mock()
        namespace={'Clock':clock,'Window':Mock()}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'game_process.py','exec'),namespace)
        event=Mock()
        screen=SimpleNamespace(tutorial_enabled=False,scheduled_events={'update_cash':event},
                               portal_shortcut=Mock(),btn_advisor=Mock(),resource_box=Mock(),
                               update_resource_box_position=Mock())
        namespace['cleanup'](screen)
        namespace['cleanup'](screen)
        clock.unschedule.assert_called_once_with(event)
        screen.portal_shortcut.close.assert_called_once_with()
        screen.resource_box.cleanup.assert_called_once_with()
        self.assertEqual(screen.scheduled_events,{})

    def test_previous_campaign_timer_cannot_touch_new_campaign_worker(self):
        conn=object()
        old=SimpleNamespace(conn=conn,_turn_overlay=None,faction=Mock(),resource_box=Mock())
        current=SimpleNamespace(conn=conn,_turn_overlay=object())
        with patch.dict(sys.modules,game_process=SimpleNamespace(_active_game_screen=current)):
            timer()(old,5)
        old.faction.update_cash.assert_not_called()
        old.resource_box.update_resources.assert_not_called()

    def test_cleaned_screen_never_updates_resources_again(self):
        old=SimpleNamespace(_cleaned_up=True,faction=Mock(),resource_box=Mock())
        timer()(old,5)
        old.faction.update_cash.assert_not_called()

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
