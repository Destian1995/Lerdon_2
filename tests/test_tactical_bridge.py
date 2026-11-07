import threading
import unittest
from unittest.mock import patch
from test_tactical_battle_ui import Window,settle
from kivy.app import App
from kivy.uix.popup import Popup
from strategy_ui import StrategyButton
from test_tactical_combat import unit
from tactical_battle_bridge import request_battle
from tactical_battle_ui import TacticalBattlePopup


def descendants(root):
    for child in root.children:
        yield child
        yield from descendants(child)


class TacticalBridgeTests(unittest.TestCase):
    def tearDown(self):
        for popup in list(Window.children):
            if isinstance(popup,Popup):popup.dismiss(animation=False)
        settle()

    def start(self):
        result=[]
        worker=threading.Thread(target=lambda:result.append(request_battle(
            [unit(attack=1e9,initiative=100)],[unit('Враг')],'attacker','Город')),
            daemon=True)
        worker.start()
        settle()
        chooser=next(w for w in Window.children if isinstance(w,Popup) and w.title=='Выберите режим боя')
        return worker,result,chooser

    def test_main_thread_never_waits_and_quick_choice_releases_worker(self):
        self.assertIsNone(request_battle([],[],'attacker'))
        with patch.object(App,'_running_app',App()):
            worker,result,chooser=self.start()
            self.assertTrue(worker.is_alive())
            button=next(w for w in descendants(chooser) if isinstance(w,StrategyButton) and w.text=='Быстрый бой')
            button.dispatch('on_release')
            worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(result,[None])

    def test_manual_choice_waits_for_actual_finish_not_opening_the_window(self):
        with patch.object(App,'_running_app',App()):
            worker,result,chooser=self.start()
            button=next(w for w in descendants(chooser) if isinstance(w,StrategyButton) and w.text=='Тактический бой')
            button.dispatch('on_release');settle()
            view=next(w for w in Window.children if isinstance(w,TacticalBattlePopup))
            self.assertTrue(worker.is_alive())
            self.assertEqual(result,[])
            self.assertTrue(view.deploying)
            view.deploying=False
            a=view.battle.stacks['attacker:0'];b=view.battle.stacks['defender:0']
            a.pos=(3,4);b.pos=(4,4)
            view.refresh()
            view.perform(lambda:view.battle.attack(b.id))
            for _ in range(25):view.tick(.1)
            self.assertEqual(view.battle.winner,'attacker')
            self.assertTrue(worker.is_alive())
            view.confirm();worker.join(1)
            self.assertFalse(worker.is_alive())
            self.assertEqual(result,[view.battle])
            self.assertIsNone(view.clock_event)


if __name__=='__main__':unittest.main()
