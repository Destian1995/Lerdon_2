import unittest

from strategy_ui_fixture import Window,Image,Label
from test_dialog_layout import settle
from test_monster_sites import fixture
from monster_sites import sites,begin_hunt,resolve_hunt,finish_hunt
from monster_battle_ui import MonsterClashPopup,MonsterRewardReport,reward_rows
from window_theme import install_window_theme
from kivy.uix.popup import Popup


class MonsterBattleTests(unittest.TestCase):
    def setUp(self):
        from types import SimpleNamespace
        self.size=Window.size
        Window.size=(1280,576);settle()
        self.db=fixture();self.addCleanup(self.db.close)
        self.widget=SimpleNamespace(conn=self.db,current_player_kingdom='Север')
        install_window_theme()

    def tearDown(self):
        for _ in range(2):
            for popup in list(Window.children):
                if isinstance(popup,Popup):popup.dismiss(animation=False)
            settle()
        Window.size=self.size;settle()

    def viewer(self,tier=7):
        eid=begin_hunt(self.db,tier,'Север')
        result=resolve_hunt(self.db,eid)
        return MonsterClashPopup(self.widget,sites(self.db)[tier-1],result,lambda:None),result

    def test_shared_arena_has_speed_pause_particles_and_no_city_capture_text(self):
        view,result=self.viewer()
        snapshot=list(self.db.iterdump())
        view.open(animation=False);settle()
        view.toggle_pause();view.change_speed()
        self.assertTrue(view.paused);self.assertEqual(view.speed,2)
        pool=[id(p['shape']) for p in view.fx.particles]
        view.toggle_pause()
        for index in range(len(view.frames)):view.show_frame(index)
        view.reveal_result()
        self.assertEqual(view.attacker_panel.bar.target,1)
        self.assertEqual(view.defender_panel.bar.target,0)
        self.assertNotIn('город',view.result_detail.text)
        self.assertEqual(pool,[id(p['shape']) for p in view.fx.particles])
        self.assertEqual(list(self.db.iterdump()),snapshot)
        if view.clock_event:view.clock_event.cancel();view.clock_event=None
        settle()
        view.export_to_png('.release/monster-shared-battle.png')
        view.close_to_report();settle()
        report=view.reward_report
        captions={caption:value for caption,value,_ in report.rows}
        self.assertEqual(captions['Кроны'],'+850 000')
        self.assertEqual(captions['Кристаллы'],'+850 000')
        self.assertEqual(captions['Усиление войск'],'16 х.')
        self.assertIn('Дар бездны',captions)
        self.assertFalse(any('Потери' in w.text for w in report.content.walk() if isinstance(w,Label)))
        self.assertEqual(list(self.db.iterdump()),snapshot)
        report.export_to_png('.release/monster-rewards-report.png')

    def test_respawn_and_defeat_report_only_bonuses_actually_received(self):
        eid=begin_hunt(self.db,7,'Север');resolve_hunt(self.db,eid);finish_hunt(self.db,eid)
        self.db.execute('UPDATE turn SET turn_count=5')
        self.db.execute('UPDATE turn_check_move SET moves_left=2')
        eid=begin_hunt(self.db,7,'Север');result=resolve_hunt(self.db,eid)
        rows=dict((a,b) for a,b,_ in reward_rows(result))
        self.assertEqual(rows['Усиление войск'],'16 х. · всего 27 х.')
        self.assertEqual(rows['Кроны'],'0');self.assertEqual(rows['Кристаллы'],'0')
        self.assertEqual(rows['Опыт участвовавших войск'],'+1')
        self.assertNotIn('Дар бездны',rows)
        result=dict(result,won=False)
        self.assertEqual([(a,b) for a,b,_ in reward_rows(result)],[('Награды','0')])

    def test_reward_report_fits_phone_and_portrait_and_callback_runs_once(self):
        view,result=self.viewer()
        view.callback=None;view.cleanup()
        calls=[]
        report=MonsterRewardReport(result,lambda:calls.append(1))
        report.open(animation=False);settle()
        for size in ((640,360),(360,640),(1280,576)):
            Window.size=size;settle();report.fit();settle()
            self.assertLessEqual(report.right,Window.width+1)
            self.assertGreaterEqual(report.return_button.y,report.y)
            self.assertLessEqual(report.return_button.top,report.top)
        report.dismiss(animation=False);report.closed()
        self.assertEqual(calls,[1])

    def test_skip_then_reward_close_starts_exactly_one_return_march(self):
        from types import SimpleNamespace
        from monster_ui import play_hunt
        from monster_sites import expedition
        batches=[];completed=[]
        layer=SimpleNamespace(play_batch=lambda specs,arrive,cancel:batches.append((specs,arrive,cancel)))
        widget=SimpleNamespace(conn=self.db,current_player_kingdom='Север',map_pos=(0,0),map_scale=1,
                               _map_atmosphere=SimpleNamespace(marches=layer),update_cities=lambda:None)
        chosen=sites(self.db)[-1];eid=begin_hunt(self.db,7,'Север')
        play_hunt(widget,chosen,eid,completed.append)
        from unittest.mock import patch
        def run(conn,operation,complete,on_error=None):complete(operation(conn))
        with patch('tactical_battle_bridge.launch_operation',side_effect=run):
            batches[0][1]();settle()
        view=next(w for w in Window.children if isinstance(w,MonsterClashPopup))
        view.close_to_report();view.close_to_report();settle()
        self.assertEqual(len(batches),1)
        self.assertIsNotNone(expedition(self.db,eid))
        view.reward_report.dismiss(animation=False);view.reward_report.closed();settle()
        self.assertEqual(len(batches),2)
        batches[1][1]()
        self.assertEqual(len(completed),1)
        self.assertIsNone(expedition(self.db,eid))
        self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE resource_type='Кроны'").fetchone()[0],850100)

    def test_tactical_hunt_shows_rewards_without_replaying_quick_clash(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from monster_ui import play_hunt
        from monster_sites import expedition
        from tactical_combat import TacticalBattle
        batches=[];completed=[]
        layer=SimpleNamespace(play_batch=lambda specs,arrive,cancel:batches.append((specs,arrive,cancel)))
        widget=SimpleNamespace(conn=self.db,current_player_kingdom='Север',map_pos=(0,0),map_scale=1,
                               _map_atmosphere=SimpleNamespace(marches=layer),update_cities=lambda:None)
        site=sites(self.db)[4];eid=begin_hunt(self.db,site['id'],'Север')
        def run(conn,operation,complete,on_error=None):complete(operation(conn))
        def manual(attackers,defenders,*args,**kwargs):
            model=TacticalBattle(attackers,defenders)
            for s in model.stacks.values():
                if s.side=='defender':s.hp=0;s.count=0
            model._check_end();return model
        play_hunt(widget,site,eid,completed.append)
        with patch('tactical_battle_bridge.launch_operation',side_effect=run),patch('tactical_battle_bridge.request_battle',side_effect=manual):
            batches[0][1]();settle()
        self.assertFalse(any(isinstance(w,MonsterClashPopup) for w in Window.children))
        report=next(w for w in Window.children if isinstance(w,MonsterRewardReport))
        self.assertEqual(report.result['mode'],'tactical')
        self.assertTrue(any(row[0]=='Выжившие' for row in report.rows))
        report.dismiss(animation=False);settle();report.closed();settle()
        self.assertEqual(len(batches),2)
        batches[1][1]()
        self.assertIsNone(expedition(self.db,eid));self.assertEqual(len(completed),1)
        self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE resource_type='Кроны'").fetchone()[0],650100)


if __name__=='__main__':unittest.main()
