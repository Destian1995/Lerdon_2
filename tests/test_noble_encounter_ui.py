import json
import random
import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from kivy.metrics import Metrics,dp
from kivy.uix.popup import Popup
from otherworld_quest_ui import QuestJournal
from noble_encounter_ui import NobleEncounter
from window_theme import install_window_theme
import otherworlds as worlds
import mirror_monster_quest as hunt


class NobleEncounterTests(unittest.TestCase):
    def setUp(self):
        self.size=Window.size;self.metrics=Metrics.density,Metrics.fontscale
        Metrics.density=Metrics.fontscale=1;Window.size=(1000,700);install_window_theme();settle()
        self.db=fixture();self.db.executescript('CREATE TABLE season(id,season_index); INSERT INTO season VALUES(1,0);')
        worlds.enter(self.db,'Север','Home');hunt.begin(self.db,'Север',random.Random(3))
        case=hunt.state(self.db,'Север');self.db.execute('UPDATE portal_parties SET city_id=?',(case['city_id'],))
        hunt.investigate(self.db,'Север');hunt.investigate(self.db,'Север')
        self.owner=SimpleNamespace(conn=self.db,faction='Север',accent=(.7,.6,.4,1),map=SimpleNamespace(draw=Mock()),refresh=Mock())
        self.journal=QuestJournal(self.owner);self.journal.open(animation=False);settle()

    def tearDown(self):
        for p in list(Window.children):
            if isinstance(p,Popup):p.dismiss(animation=False)
        settle();self.db.close();Metrics.density,Metrics.fontscale=self.metrics;Window.size=self.size;settle()

    def expose(self):
        case=hunt.state(self.db,'Север');story=json.loads(case['scenario'])
        board=self.journal.open_board(noble=True);settle()
        wrong=story['nobles'][(story['culprit']+1)%3]['name']
        board.select_suspect(wrong);board.accuse();settle()
        self.assertIsNotNone(board.parent)
        self.assertFalse(hasattr(self.journal,'noble_encounter'))
        board.select_suspect(hunt.noble_name(case));board.accuse();settle()
        self.assertIsNone(board.parent)
        dialog=self.journal.noble_encounter
        self.assertIsInstance(dialog,NobleEncounter);self.assertIsNotNone(dialog.parent)
        self.assertIsNone(hunt.pact(self.db,'Север'));self.assertFalse(hunt.revealed(hunt.state(self.db,'Север')))
        self.assertEqual(dialog.art.source,hunt.noble_image(case))
        self.assertEqual(len(dialog.dock.groups[0].children),2)
        return dialog

    def test_accepts_once_with_terms_visible_and_preserves_companion_identity(self):
        dialog=self.expose()
        self.assertIn('20 ходов',dialog.terms.text);self.assertIn('50%',dialog.terms.text)
        self.assertNotIn(hunt.monster(hunt.state(self.db,'Север'))['unit_name'],dialog.name.text)
        expected=dialog.art.source
        dialog.accept_button.dispatch('on_release');settle();dialog.accept_button.dispatch('on_release')
        case=hunt.state(self.db,'Север')
        self.assertEqual(case['stage'],3);self.assertEqual(case['hero'],'Hero')
        self.assertEqual(hunt.pact(self.db,'Север')['deadline'],20)
        self.assertIsNone(dialog.parent)
        self.assertEqual(self.db.execute('SELECT image_path FROM units WHERE unit_name=?',(case['reward_unit'],)).fetchone()[0],expected)

    def test_refusal_reveals_monster_and_allows_leaving_then_resuming_combat(self):
        dialog=self.expose();dialog.refuse_button.dispatch('on_release');settle()
        self.assertTrue(hunt.revealed(hunt.state(self.db,'Север')));self.assertIsNone(hunt.pact(self.db,'Север'))
        self.assertEqual(dialog.accept_button.text,'В бой');self.assertEqual(dialog.refuse_button.text,'Уйти')
        self.assertEqual(dialog.art.source,hunt.monster(hunt.state(self.db,'Север'))['unit_image'])
        dialog.refuse_button.dispatch('on_release');settle();self.assertIsNone(dialog.parent)
        resumed=self.journal.open_board(noble=True);settle()
        self.assertIsInstance(resumed,NobleEncounter)
        self.journal.hunt_battle=Mock();resumed.accept_button.dispatch('on_release');settle()
        self.journal.hunt_battle.assert_called_once_with('Hero');self.assertIsNone(resumed.parent)

    def test_selected_hero_receives_the_companion_when_party_has_two_heroes(self):
        self.db.execute('''INSERT INTO units SELECT 7,faction,'Second hero',cost_money,cost_time,image_path,
            attack,defense,durability,unit_class,consumption,unit_type FROM units WHERE unit_name='Hero' ''')
        camp=worlds.party(self.db,'Север')['camp']
        self.db.execute('INSERT INTO garrisons VALUES(?,?,?,?,?)',(camp,'Second hero',1,'files/status/army.png',0))
        dialog=self.expose()
        self.assertFalse(dialog.hero.disabled)
        self.assertEqual(set(dialog.hero.values),{'Hero','Second hero'})
        dialog.hero.text='Second hero';dialog.accept_button.dispatch('on_release');settle()
        self.assertEqual(hunt.state(self.db,'Север')['hero'],'Second hero')

    def test_small_screens_pin_both_choices_and_keep_uncropped_portrait(self):
        dialog=self.expose()
        for size,density,font in (((640,360),1,1),((1280,576),2,1.2),((320,568),1,1.3)):
            Window.size=size;Metrics.density=density;Metrics.fontscale=font;settle();dialog.fit();settle()
            self.assertEqual(dialog.art.fit_mode,'contain');self.assertIsNotNone(dialog.art.texture)
            self.assertGreater(dialog.scroll.height,dp(50))
            for b in (dialog.accept_button,dialog.refuse_button):
                self.assertGreaterEqual(b.height,dp(48)-1)
                self.assertGreaterEqual(b.y,dialog.y);self.assertLessEqual(b.top,dialog.top)
                self.assertGreaterEqual(b.x,dialog.x);self.assertLessEqual(b.right,dialog.right+1)
            if size==(640,360):dialog.export_to_png('.release/noble-offer-phone.png')
        dialog.export_to_png('.release/noble-offer-portrait.png')
        dialog.dismiss(animation=False);settle()
        resumed=self.journal.open_board(noble=True);settle()
        self.assertIsInstance(resumed,NobleEncounter);self.assertIsNone(hunt.pact(self.db,'Север'))


if __name__=='__main__':unittest.main()
