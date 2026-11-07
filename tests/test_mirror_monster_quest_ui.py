import random
import json
import unittest
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from kivy.metrics import Metrics,dp
from kivy.uix.popup import Popup
from kivy.uix.image import Image
from otherworld_ui import OtherworldMap
from otherworld_quest_ui import QuestJournal
import otherworlds as worlds
import otherworld_quests as quests
import mirror_monster_quest as hunt


class MonsterCaseUITests(unittest.TestCase):
    def test_optional_case_buttons_clues_and_monster_fit_phone_and_landscape(self):
        size=Window.size;metrics=(Metrics.density,Metrics.fontscale)
        db=fixture()
        try:
            Metrics.density=Metrics.fontscale=1;Window.size=(640,360);settle()
            db.executescript('CREATE TABLE season(id,current_season,season_index); INSERT INTO season VALUES(1,"Лето",2);')
            worlds.enter(db,'Север','Home')
            owner=OtherworldMap(db,'Север');owner.open(animation=False);settle()
            journal=QuestJournal(owner);journal.open(animation=False);settle()
            journal.cards.select(1);settle()
            journal.cards.pages[1].buttons.children[0].dispatch('on_release');settle()
            case=hunt.state(db,'Север');self.assertIsNotNone(case)
            self.assertIsNone(quests.state(db,'Север'))
            self.assertTrue(journal.cards.pages[1].buttons.children[0].disabled)
            db.execute('UPDATE portal_parties SET city_id=?',(case['city_id'],))
            for stage in (0,1):
                journal.refresh();settle()
                self.assertEqual(hunt.state(db,'Север')['stage'],stage)
                button=journal.cards.pages[1].buttons.children[0]
                self.assertFalse(button.disabled);button.dispatch('on_release');settle()
            journal.refresh();settle();card=journal.cards.pages[1]
            self.assertEqual(hunt.state(db,'Север')['stage'],2)
            self.assertFalse(any(isinstance(w,Image) for w in card.content.children))
            story=json.loads(hunt.state(db,'Север')['scenario'])
            name=story['nobles'][story['culprit']]['name']
            wrong=story['nobles'][(story['culprit']+1)%3]['name']
            self.assertFalse(any(story['monster'] in label.text for label in card.sections))
            next(b for b in card.buttons.children if b.text=='Обвинить: '+wrong).dispatch('on_release');settle()
            card=journal.cards.pages[1]
            self.assertFalse(hunt.revealed(hunt.state(db,'Север')))
            self.assertFalse(any(isinstance(w,Image) for w in card.content.children))
            self.assertTrue(next(b for b in card.buttons.children if b.text=='Обвинить: '+wrong).disabled)
            Window.size=(392,844);settle();journal.fit();settle()
            journal.export_to_png('.release/mirror-noble-investigation-phone.png')
            next(b for b in card.buttons.children if b.text=='Обвинить: '+name).dispatch('on_release');settle()
            card=journal.cards.pages[1]
            self.assertTrue(hunt.identified(hunt.state(db,'Север')))
            self.assertFalse(hunt.revealed(hunt.state(db,'Север')))
            image=next(w for w in card.content.children if isinstance(w,Image))
            self.assertIsNotNone(image.texture)
            self.assertTrue(any('Hero' in b.text for b in card.buttons.children))
            for screen,density in (((640,360),1),((1280,576),2),((392,844),1)):
                Window.size=screen;Metrics.density=density;settle();journal.fit();settle()
                journal.cards.select(1);settle()
                self.assertGreater(card.scroll.height,dp(35))
                self.assertGreaterEqual(card.x,journal.root.x-1)
                self.assertLessEqual(card.right,journal.root.right+1)
                self.assertGreaterEqual(card.y,journal.root.y-1)
                for button in card.buttons.children:self.assertGreaterEqual(button.height,dp(44)-1)
            journal.export_to_png('.release/mirror-monster-quest-phone.png')
            offer=next(b for b in journal.cards.pages[1].buttons.children if b.text.startswith('Договориться'))
            offer.dispatch('on_release');settle()
            self.assertIsNone(hunt.pact(db,'Север'))
            card=journal.cards.pages[1]
            self.assertTrue(any('30 ходов' in s.text and 'поражение' not in s.text for s in card.sections))
            next(b for b in card.buttons.children if b.text=='Отказаться от сделки').dispatch('on_release');settle()
            self.assertIsNone(hunt.pact(db,'Север'))
            next(b for b in journal.cards.pages[1].buttons.children if b.text.startswith('Договориться')).dispatch('on_release');settle()
            journal.export_to_png('.release/mirror-soul-pact-confirm-phone.png')
            next(b for b in journal.cards.pages[1].buttons.children if b.text.startswith('Продать душу')).dispatch('on_release');settle()
            self.assertEqual(hunt.pact(db,'Север')['deadline'],30)
            self.assertIn('Сделка за душу',journal.cards.pages[1].title)
            prize=hunt.state(db,'Север')['reward_unit']
            self.assertEqual(db.execute('SELECT attack,defense FROM units WHERE unit_name=?',(prize,)).fetchone(),(253_500_000,100_750_000))
            journal.change_form('monster');settle()
            self.assertEqual(db.execute('SELECT attack,defense FROM units WHERE unit_name=?',(prize,)).fetchone(),(84_500_000,302_250_000))
            from companion_form_ui import CompanionForms,form_button
            self.assertIsNotNone(form_button(db,'Север',prize))
            self.assertIsNone(form_button(db,'Север','troop1'))
            forms=CompanionForms(db,'Север');forms.open(animation=False);settle()
            forms.switch('noble');settle()
            self.assertTrue(forms.art.source.endswith('.jpg'))
            self.assertIsNotNone(forms.art.texture)
            self.assertIn('АТК +50%',forms.stats.text)
            self.assertEqual(hunt.pact(db,'Север')['deadline'],30)
            forms.export_to_png('.release/companion-noble-form-phone.png')
        finally:
            for widget in list(Window.children):
                if isinstance(widget,Popup):widget.dismiss(animation=False)
            settle();db.close();Metrics.density,Metrics.fontscale=metrics;Window.size=size;settle()


if __name__=='__main__':unittest.main()
