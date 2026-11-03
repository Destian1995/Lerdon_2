import unittest
from types import SimpleNamespace

from strategy_ui_fixture import Window,Widget,Image,BoxLayout,Clock
from test_dialog_layout import settle
from test_monster_sites import fixture
from monster_sites import sites,begin_hunt,resolve_hunt
from monster_ui import MonsterPopup,open_relic_choice,MonsterClashPopup,draw_monsters
from kivy.metrics import Metrics
from kivy.uix.popup import Popup
from window_theme import install_window_theme


class MonsterUITests(unittest.TestCase):
    def setUp(self):
        self.size=Window.size
        self.metrics=Metrics.density,Metrics.fontscale
        self.db=fixture();self.addCleanup(self.db.close)
        self.map=SimpleNamespace(conn=self.db,current_player_kingdom='Север')
        install_window_theme()

    def tearDown(self):
        for _ in range(2):
            for popup in list(Window.children):
                if isinstance(popup,Popup):popup.dismiss(animation=False)
            settle()
        Metrics.density,Metrics.fontscale=self.metrics
        Window.size=self.size
        settle()

    def test_monster_art_garrison_and_actions_fit_phone_and_portrait(self):
        popup=MonsterPopup(self.map,sites(self.db)[-1])
        popup.open(animation=False)
        for size,density in (((1280,576),1),((640,360),1),((360,640),1),((1280,576),2)):
            Metrics.density=density;Window.size=size;settle();popup.fit();settle()
            with self.subTest(size=size,density=density):
                self.assertGreater(popup.art.width,60)
                self.assertGreater(popup.art.height,60)
                self.assertEqual(len(popup.summary.tiles),3)
                self.assertGreater(popup.summary.height,60)
                self.assertLessEqual(popup.right,Window.width+1)
                self.assertGreaterEqual(popup.hunt.y,popup.y)
                self.assertLessEqual(popup.hunt.top,popup.top)
                self.assertEqual(len(popup.unit_cards),2)
                self.assertFalse(popup.hunt.disabled)
                if size==(1280,576) and density==1:
                    popup.export_to_png('.release/monster-lair-preview.png')

    def test_relic_dialog_choice_is_persistent_and_only_contains_owned_artifacts(self):
        eid=begin_hunt(self.db,7,'Север');resolve_hunt(self.db,eid)
        popup=open_relic_choice(self.map)
        settle()
        labels=[w.text for w in popup.content.walk() if hasattr(w,'text')]
        self.assertTrue(any('120%' in s and '670%' in s for s in labels))

    def test_respawn_popup_displays_experience_only_and_no_relic_drop(self):
        from monster_sites import finish_hunt
        eid=begin_hunt(self.db,7,'Север');resolve_hunt(self.db,eid);finish_hunt(self.db,eid)
        popup=MonsterPopup(self.map,sites(self.db)[-1])
        popup.open(animation=False);settle()
        self.assertEqual(popup.summary.reward.value.text,'+1 опыта войскам')
        self.assertEqual(popup.summary.training.value.text,'9 х.')
        self.assertNotIn('550%',popup.summary.reward.value.text)

    def test_foreign_lair_has_large_coloured_stat_cards(self):
        Window.size=(1280,576);settle()
        self.db.execute("UPDATE cities SET faction='Эльфы' WHERE name='Home'")
        popup=MonsterPopup(self.map,sites(self.db)[0])
        popup.open(animation=False);settle()
        self.assertGreaterEqual(popup.summary.defense.value.font_size,26)
        self.assertGreaterEqual(popup.summary.training.value.font_size,26)
        self.assertGreaterEqual(popup.summary.reward.value.font_size,20)
        for tile in popup.summary.tiles:
            self.assertGreaterEqual(tile.icon.width,36)
            self.assertGreaterEqual(tile.y,popup.body.y-1)
            self.assertLessEqual(tile.top,popup.body.top+1)
            self.assertLessEqual(tile.value.texture_size[1],tile.value.height+1)
        self.assertNotEqual(popup.summary.defense.value.color,popup.summary.training.value.color)
        popup.export_to_png('.release/monster-colourful-stats.png')

    def test_lair_and_clash_use_the_same_persisted_appearance(self):
        self.db.execute('UPDATE monster_sites SET variant=4 WHERE id=6')
        chosen=sites(self.db)[5]
        popup=MonsterPopup(self.map,chosen)
        self.assertEqual(popup.title,'Снежная химера')
        self.assertTrue(popup.art.source.endswith('monster_6_4.png'))
        eid=begin_hunt(self.db,6,'Север');result=resolve_hunt(self.db,eid)
        self.assertEqual(result['name'],'Снежная химера')
        clash=MonsterClashPopup(self.map,chosen,result,lambda:None)
        images=[w.source for w in clash.content.walk() if isinstance(w,Image)]
        self.assertTrue(any(p.endswith('monster_6_4.png') for p in images))
        clash.callback=None;clash.cleanup()

    def test_battle_replay_can_close_once_without_double_return(self):
        eid=begin_hunt(self.db,7,'Север');result=resolve_hunt(self.db,eid)
        calls=[]
        popup=MonsterClashPopup(self.map,sites(self.db)[-1],result,lambda:calls.append(1))
        popup.open(animation=False);settle()
        from battle_ui import BattleViewer
        self.assertIsInstance(popup,BattleViewer)
        popup.show_frame(len(popup.frames)-1)
        popup.reveal_result()
        self.assertEqual(popup.defender_panel.bar.target,0)
        popup.dismiss(animation=False);settle()
        popup.cleanup()
        self.assertEqual(calls,[])
        self.assertIsNotNone(popup.reward_report)
        popup.reward_report.dismiss(animation=False);settle()
        popup.reward_report.closed()
        self.assertEqual(calls,[1])

    def test_player_marches_both_ways_with_hero_flag_and_returns_real_camp_only_once(self):
        from monster_ui import play_hunt
        from unittest.mock import patch
        from monster_sites import expedition
        batches=[];completed=[]
        layer=SimpleNamespace(play_batch=lambda specs,arrive,cancel:batches.append((specs,arrive,cancel)))
        widget=SimpleNamespace(conn=self.db,current_player_kingdom='Север',map_pos=(0,0),map_scale=1,
                               _map_atmosphere=SimpleNamespace(marches=layer),update_cities=lambda:None)
        class Clash:
            def __init__(self,widget,site,result,done):self.done=done
            def open(self):self.done()
        site=sites(self.db)[-1];eid=begin_hunt(self.db,site['id'],'Север')
        with patch('monster_ui.MonsterClashPopup',Clash):
            play_hunt(widget,site,eid,completed.append)
            self.assertEqual(len(batches),1)
            self.assertTrue(batches[0][0][0][-1])
            outbound=batches[0][0][0][0]()
            self.assertEqual(outbound.points[-1],(site['x'],site['y']))
            batches[0][1]()
            self.assertEqual(len(batches),2)
            self.assertIsNotNone(expedition(self.db,eid))
            self.assertEqual(batches[1][0][0][0]().points[0],outbound.points[-1])
            batches[1][1]()
            self.assertIsNone(expedition(self.db,eid))
            self.assertEqual(len(completed),1)

    def test_all_new_art_is_drawn_and_map_uses_saved_dead_end_paths(self):
        root=Widget(size_hint=(None,None),size=(1024,1024))
        board=BoxLayout(orientation='vertical',size_hint=(None,None),size=(1024,1024))
        from kivy.uix.gridlayout import GridLayout
        from monster_sites import art_path
        from terrain_icons import icon_path
        grid=GridLayout(cols=4)
        paths=[art_path(t) for t in range(1,8)]+[icon_path(k,v,'dead')
               for k,n in (('forest',5),('swamp',4)) for v in range(1,n+1)]
        for path in paths:
            grid.add_widget(Image(source=str(path),allow_stretch=True,keep_ratio=True))
        board.add_widget(grid);root.add_widget(board);Window.add_widget(root)
        try:
            settle();root.export_to_png('.release/monster-dead-art-board.png')
            widget=Widget();widget.conn=self.db;widget.map_pos=(0,0);widget.map_scale=1
            draw_monsters(widget)
            self.assertEqual(len(widget._monster_hits),7)
        finally:Window.remove_widget(root)


if __name__=='__main__':unittest.main()
