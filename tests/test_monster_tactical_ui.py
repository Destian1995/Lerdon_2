import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
import test_tactical_battle_ui as ui
from test_monster_sites import fixture
from monster_sites import sites,begin_hunt,expedition
from monster_tactical import armies,context
from tactical_battle_bridge import request_battle
from tactical_battle_ui import TacticalBattlePopup
from kivy.uix.popup import Popup


class MonsterTacticalUITests(unittest.TestCase):
    setUp=ui.TacticalUITests.setUp
    tearDown=ui.TacticalUITests.tearDown

    def test_real_worker_offers_tactical_mode_and_plays_scorpion_atlas(self):
        db=fixture();self.addCleanup(db.close)
        db.execute("UPDATE garrisons SET unit_image=CASE WHEN unit_name='hero' THEN 'files/army/people/vlad.jpg' ELSE 'files/army/people/predator.jpg' END")
        site=sites(db)[4];site['variant']=4
        eid=begin_hunt(db,site['id'],'Север');row=expedition(db,eid)
        attackers,defenders=armies(db,row,site);geography=context(db,row,site)
        answer={};app=SimpleNamespace(_game_audio=Mock())
        def work():
            try:answer['model']=request_battle(attackers,defenders,'attacker','Обсидиановый скорпион',geography,factions=('Север',''))
            except Exception as error:answer['error']=error
        worker=threading.Thread(target=work,daemon=True)
        def wait_for(test):
            deadline=time.monotonic()+6
            while time.monotonic()<deadline:
                ui.settle()
                result=test()
                if result:return result
            self.fail('The battle UI did not reach the expected state: '+str(answer))
        try:
            with patch('kivy.app.App.get_running_app',return_value=app),patch('tactical_battle_ui.get_audio',return_value=Mock()):
                worker.start()
                chooser=wait_for(lambda:next((p for p in ui.Window.children if isinstance(p,Popup) and p.title=='Выберите режим боя'),None))
                button=next(w for w in chooser.walk() if getattr(w,'text','')=='Тактический бой')
                self.assertFalse(button.disabled)
                button.dispatch('on_release')
                view=wait_for(lambda:next((p for p in ui.Window.children if isinstance(p,TacticalBattlePopup)),None))
                self.views.append(view)
                if view.clock_event:view.clock_event.cancel();view.clock_event=None
                monster=next(s for s in view.battle.stacks.values() if s.side=='defender')
                self.assertEqual(view.board.library.key(monster.unit),'monsters/monster_5_4')
                for action in ('idle','walk','attack','hit','death'):
                    texture,_,_=view.board.library.frame(monster.unit,action,.2)
                    self.assertIsNotNone(texture)
                ui.Window.size=(960,540);ui.settle();view.deploying=False;view.board.draw()
                view.export_to_png('.release/monster-tactical-scorpion.png')
                monster.hp=0;monster.count=0;view.battle._check_end();view.finish_result()
                wait_for(lambda:'model' in answer or 'error' in answer)
        finally:
            worker.join(timeout=2)
            for popup in list(ui.Window.children):
                if isinstance(popup,Popup) and popup not in self.views:popup.dismiss(animation=False)
        self.assertNotIn('error',answer)
        self.assertEqual(answer['model'].winner,'attacker')

if __name__=='__main__':unittest.main()
