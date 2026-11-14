import unittest

from strategy_ui_fixture import Window,Clock
from test_dialog_layout import settle
from test_otherworlds import fixture
from otherworld_ui import OtherworldMap,ForeignCityPopup
from window_theme import install_window_theme
from kivy.uix.popup import Popup


class OtherworldUITests(unittest.TestCase):
    def test_ambient_poll_retries_database_lock_without_losing_highlights(self):
        import sqlite3
        from unittest.mock import patch
        overview=OtherworldMap(self.db,'Север')
        self.addCleanup(overview._poll.cancel)
        effects=overview.map.effects
        effects.quest_targets={2};effects._quest_refresh=-1
        with patch('otherworld_quests.objectives',side_effect=sqlite3.OperationalError('database is locked')):
            effects.update(.01)
        self.assertEqual(effects.quest_targets,{2})
        effects.age+=.6
        with patch('otherworld_quests.objectives',return_value={3}):
            effects.update(.01)
        self.assertEqual(effects.quest_targets,{3})
        effects.stop()

    def setUp(self):
        import otherworlds
        self.db=fixture();self.addCleanup(self.db.close)
        self.size=Window.size
        Window.size=(1280,576)
        install_window_theme();settle()
        otherworlds.enter(self.db,'Север','Home')

    def tearDown(self):
        for popup in list(Window.children):
            if isinstance(popup,Popup): popup.dismiss(animation=False)
        settle();Window.size=self.size

    def test_map_foreign_city_and_five_unit_offers_fit_phone(self):
        import otherworlds
        overview=OtherworldMap(self.db,'Север');overview.open(animation=False);settle()
        self.assertEqual(len(overview.map.hits),7)
        self.assertEqual(len(overview.map.city_textures),7)
        self.assertTrue(overview.map.effects._event)
        city=otherworlds.cities(self.db)[0]
        popup=ForeignCityPopup(overview,city);popup.open(animation=False);settle()
        popup.recruit_button.dispatch('on_release');settle()
        self.assertEqual(len(popup.recruitment.slides),5)
        self.assertEqual(popup.recruitment.carousel.index,0)
        popup.recruitment.carousel.load_next();settle()
        self.assertEqual(popup.recruitment.carousel.index,1)
        popup.recruitment.popup.dismiss(animation=False);settle()
        self.assertGreater(popup.army_box.parent.height,100)
        self.assertGreater(popup.service_panel.height,100)
        self.assertFalse(popup.battle_button.disabled)

        self.assertTrue(popup.travel_button.disabled)
        for widget in (popup.info,popup.services,popup.feedback,popup.battle_button):
            self.assertGreaterEqual(widget.x,popup.x)
            self.assertGreaterEqual(widget.y,popup.y)
            self.assertLessEqual(widget.right,popup.right+1)
            self.assertLessEqual(widget.top,popup.top+1)

    def test_ambience_stops_when_world_map_closes(self):
        overview=OtherworldMap(self.db,'Север');overview.open(animation=False);settle()
        self.assertTrue(overview.map.effects._event)
        overview.dismiss(animation=False)
        self.assertIsNone(overview.map.effects._event)

    def test_geography_and_city_bases_stay_above_phone_action_bar(self):
        import otherworlds
        from otherworld_themes import THEMES
        for faction in THEMES:
            self.db.execute('UPDATE portal_parties SET faction=?',(faction,))
            for size in ((640,360),(320,568)):
                with self.subTest(faction=faction,size=size):
                    Window.size=size
                    overview=OtherworldMap(self.db,faction);overview.open(animation=False);settle()
                    overview.fit();settle();overview.map.draw()
                    self.assertGreater(overview.map.y,overview.action_bar.top)
                    for _,bottom,_,_,city_id in overview.map.city_bounds:
                        # Reserve a readable city-name line below each icon.
                        self.assertGreater(bottom-18,overview.action_bar.top,(faction,city_id))
                    for left,bottom,width,_,city_id in overview.map.city_label_bounds:
                        self.assertGreaterEqual(left,overview.map.x,(faction,city_id))
                        self.assertLessEqual(left+width,overview.map.right,(faction,city_id))
                        self.assertGreater(bottom,overview.action_bar.top,(faction,city_id))
                    overview.dismiss(animation=False);settle()

    def test_battle_window_receives_hero_portrait_and_keeps_guard_portrait(self):
        from types import SimpleNamespace
        from unittest.mock import patch,Mock
        import sys
        import otherworlds
        overview=OtherworldMap(self.db,'Север');overview.open(animation=False);settle()
        city=ForeignCityPopup(overview,otherworlds.cities(self.db,'Север')[0])
        result=dict(won=True,coins=100,city=city.city['name'],army=[],
                    guards=[dict(unit_image='files/army/people/predator.jpg')],
                    rounds=[],attacker_image='files/army/people/vlad.jpg')
        with patch.dict(sys.modules,{'fight':SimpleNamespace(generate_battle_report=Mock())}), \
             patch('otherworld_ui.worlds.fight_guards',return_value=result), \
             patch('tactical_battle_bridge.launch_operation',side_effect=lambda conn,op,done,error:done(op(conn))), \
             patch('otherworld_ui._refresh_main'), \
             patch('battle_ui.BattleViewer.open',autospec=True) as opened:
            city.battle()
            view=opened.call_args.args[0]
            self.assertEqual(view.attacker_panel.image.source,result['attacker_image'])
            self.assertEqual(view.defender_panel.image.source,result['guards'][0]['unit_image'])

    def test_faction_weather_uses_mountains_and_follows_map_projection(self):
        from types import SimpleNamespace
        from otherworld_effects import MirrorEffects,mountain_anchors
        from map_terrain import MOUNTAIN,WATER
        terrain=SimpleNamespace(grid=[MOUNTAIN,WATER],width=2,height=1,world_width=1200,world_height=800)
        self.assertEqual(mountain_anchors(terrain),[(300,400)])
        for faction in ('Вампиры','Эльфы','Север','Адепты','Элины'):
            owner=SimpleNamespace(faction=faction,accent=(.6,.5,1,1))
            m=SimpleNamespace(owner=owner,terrain=terrain,nodes=[dict(id=1,x=100,y=100)],
                              width=1200,height=800,camera=SimpleNamespace(zoom=1),point=lambda x,y:(x,y))
            effects=MirrorEffects(m);effects.update(.1)
            self.assertEqual(len(effects.snow),24 if faction=='Север' else 0)
            self.assertEqual(len(effects.lightning),6 if faction=='Вампиры' else 0)
            before=effects.fog[0][1].pos
            m.point=lambda x,y:(x+40,y+20)
            effects.update(0)
            for actual,expected in zip(effects.fog[0][1].pos,(before[0]+40,before[1]+20)):
                self.assertAlmostEqual(actual,expected,delta=1e-4)
            effects.start();effects.stop();self.assertIsNone(effects._event)

    def test_remote_market_disabled_and_travel_has_live_party(self):
        import otherworlds
        overview=OtherworldMap(self.db,'Север');overview.open(animation=False);settle()
        neighbor=self.db.execute('SELECT CASE WHEN city1=1 THEN city2 ELSE city1 END FROM portal_roads WHERE city1=1 OR city2=1 LIMIT 1').fetchone()[0]
        city=next(c for c in otherworlds.cities(self.db) if c['id']==neighbor)
        popup=ForeignCityPopup(overview,city);popup.open(animation=False);settle()
        self.assertFalse(popup.travel_button.disabled)
        self.assertTrue(popup.battle_button.disabled)
        self.assertTrue(all(button.disabled for button in popup.offer_buttons))
        popup.go();settle()
        self.assertEqual(otherworlds.party(self.db,'Север')['city_id'],1)
        self.assertIsNotNone(otherworlds.beam(self.db,'Север'))
        for _ in range(150):overview.map.effects.update(1/30)
        self.assertEqual(otherworlds.party(self.db,'Север')['city_id'],neighbor)
        self.assertTrue(overview.map.beam.finished)
        self.assertIsNone(otherworlds.beam(self.db,'Север'))

    def test_swipe_selects_unit_and_purchase_keeps_the_selected_card(self):
        from kivy.tests.common import UnitTestTouch
        import otherworlds
        overview=OtherworldMap(self.db,'Север');overview.open(animation=False);settle()
        popup=ForeignCityPopup(overview,otherworlds.cities(self.db,'Север')[0])
        popup.open(animation=False);popup.open_recruitment();settle()
        session=popup.recruitment
        carousel=session.carousel
        x,y=carousel.x+carousel.width*.8,carousel.center_y
        end_x=carousel.x+carousel.width*.15
        touch=UnitTestTouch(x,y)
        touch.touch_down()
        touch.touch_move(x-45,y)
        touch.touch_move(end_x,y)
        touch.touch_up();settle();settle()
        self.assertEqual(carousel.index,1)
        unit=otherworlds.unit_offers(self.db,'Север')[1]
        current=session.cards[1]
        self.assertEqual(session.units[1][0],unit['unit_name'])
        quantity=next(w for w in current.walk() if w.__class__.__name__=='TextInput')
        quantity.text='37';settle()
        hire=next(w for w in current.controls.children if getattr(w,'text','').startswith('НАНЯТЬ'))
        hire.dispatch('on_release');settle()
        self.assertEqual(carousel.index,1)
        camp=otherworlds.party(self.db,'Север')['camp']
        row=self.db.execute('SELECT unit_count FROM garrisons WHERE city_name=? AND unit_name=?',
                            (camp,'Странник: '+unit['unit_name']+' / Север')).fetchone()
        self.assertEqual(row,(37,))


if __name__=='__main__': unittest.main()
