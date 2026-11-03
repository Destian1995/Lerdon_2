import unittest

from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from otherworld_ui import OtherworldMap,ForeignCityPopup
from otherworld_quest_ui import QuestJournal
import otherworlds as w
import otherworld_quests as q
from window_theme import install_window_theme
from kivy.uix.popup import Popup


class MirrorCampaignUITests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)
        self.size=Window.size
        Window.size=(1280,576);settle();install_window_theme()
        w.enter(self.db,'Север','Home')
        self.map=OtherworldMap(self.db,'Север');self.map.open(animation=False);settle()

    def tearDown(self):
        for popup in list(Window.children):
            if isinstance(popup,Popup):popup.dismiss(animation=False)
        settle();Window.size=self.size;settle()

    def test_journal_records_clues_and_fits_small_landscape_screen(self):
        journal=QuestJournal(self.map);journal.open(animation=False);settle()
        journal.perform(lambda:q.begin(self.db,'Север'))
        self.assertEqual(len(journal.cards.children),2)
        witness=q.details(q.state(self.db,'Север'))['detective']['cities'][0]
        self.db.execute("UPDATE portal_parties SET city_id=? WHERE faction='Север'",(witness,))
        self.db.execute('UPDATE turn_check_move SET moves_left=10');self.db.commit()
        journal.step('witness');settle()
        self.assertEqual(q.state(self.db,'Север')['detective'],1)
        self.assertIn(q.details(q.state(self.db,'Север'))['detective']['tokens'][q.state(self.db,'Север')['culprit']],journal.feedback.text)
        Window.size=(640,360);settle();journal.fit();settle()
        self.assertGreater(journal.cards.parent.height,80)
        self.assertGreaterEqual(journal.root.children[0].y,journal.y)
        self.assertLessEqual(journal.right,Window.width+1)

    def test_shop_shows_hero_class_and_active_relic_deadline(self):
        city=ForeignCityPopup(self.map,w.cities(self.db,'Север')[0]);city.open(animation=False);settle()
        city.show_market('artifacts');settle()
        self.assertIn('3 класс',city.feedback.text)
        item=w.artifact_offers(self.db,'Север')[0]
        city.artifact(item);settle()
        self.assertTrue(city.offer_buttons[0].disabled)
        self.assertIn('Действует',city.offer_buttons[0].text)

    def test_closing_map_during_beam_saves_arrival_and_stops_effects(self):
        neighbor=self.db.execute('SELECT city2 FROM portal_roads WHERE city1=1 LIMIT 1').fetchone()[0]
        w.begin_beam(self.db,'Север',neighbor)
        self.map.play_beam(1,neighbor)
        self.map.map.effects.update(.1)
        self.assertTrue(self.map.map.beam.core.points)
        self.assertEqual(w.party(self.db,'Север')['city_id'],1)
        self.map.dismiss(animation=False)
        self.assertEqual(w.party(self.db,'Север')['city_id'],neighbor)
        self.assertIsNone(w.beam(self.db,'Север'))
        self.assertIsNone(self.map.map.effects._event)

    def test_equipment_panel_keeps_atlas_art_and_shows_expiry_details(self):
        from types import SimpleNamespace
        from dialog700_fixture import function
        from kivy.uix.button import Button
        from kivy.uix.label import Label
        w.buy_artifact(self.db,'Север',1)
        aid=self.db.execute('SELECT artifact_id FROM portal_artifacts').fetchone()[0]
        cursor=self.db.execute('SELECT * FROM artifacts WHERE id=?',(aid,))
        artifact=dict(zip((d[0] for d in cursor.description),cursor.fetchone()))
        player=SimpleNamespace(conn=self.db,faction='Север',resources={'Кроны':50000})
        function('heroes.py','open_artifacts_popup',
            load_artifacts_from_db=lambda f:[artifact],
            load_hero_equipment_from_db=lambda f:{'0':{'id':aid}},
            load_hero_image_from_db=lambda f:'files/army/people/vlad.jpg',
            load_hero_stats_from_db=lambda f:dict(attack=100,defense=300,durability=10),
            format_artifact_description=lambda art:'Временный артефакт',
            style_rounded_spinner=lambda *args,**kwargs:None,
            style_rounded_button=lambda *args,**kwargs:None)(player,None)
        settle()
        popup=next(p for p in Window.children if isinstance(p,Popup) and p is not self.map)
        slots=[b for b in popup.content.walk() if isinstance(b,Button) and b.background_normal==artifact['image_url']]
        self.assertEqual(len(slots),1)
        self.assertEqual(slots[0].background_color[3],1)
        slots[0].dispatch('on_release');settle()
        detail=Window.children[0]
        self.assertTrue(any('Осталось:' in label.text for label in detail.walk() if isinstance(label,Label)))


if __name__=='__main__':unittest.main()
