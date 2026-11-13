"""Real clue placement, accusation gates and readable corkboard layouts."""
import json
import random
from types import SimpleNamespace
from unittest.mock import Mock
import unittest
from strategy_ui_fixture import Window
from kivy.metrics import Metrics,dp,sp
from kivy.uix.popup import Popup
from kivy.tests.common import UnitTestTouch
from test_dialog_layout import settle
from test_otherworlds import fixture
from otherworld_quest_ui import QuestJournal
import otherworld_quests as quests
import otherworlds as worlds
import mirror_monster_quest as hunt
from otherworld_quest_pool import search_hint
from window_theme import install_window_theme

class InvestigationBoardTests(unittest.TestCase):
 def setUp(self):
  self.size=Window.size;self.metrics=(Metrics.density,Metrics.fontscale)
  Metrics.density=Metrics.fontscale=1;Window.size=(1160,760);settle();install_window_theme()
  self.db=fixture();worlds.enter(self.db,'Север','Home')
  self.owner=SimpleNamespace(conn=self.db,faction='Север',accent=(.7,.6,.4,1),map=SimpleNamespace(draw=Mock()),refresh=Mock())

 def tearDown(self):
  for popup in list(Window.children):
   if isinstance(popup,Popup):popup.dismiss(animation=False)
  settle();self.db.close();Metrics.density,Metrics.fontscale=self.metrics;Window.size=self.size;settle()

 def journal(self):
  journal=QuestJournal(self.owner);journal.open(animation=False);settle();return journal

 def collect(self):
  quests.begin(self.db,'Север',random.Random(42))
  run=quests.state(self.db,'Север');d=quests.details(run)['detective']
  self.db.execute('UPDATE portal_parties SET city_id=?',(d['cities'][0],));quests.action(self.db,'Север','witness')
  self.db.execute('UPDATE portal_parties SET city_id=?',(d['cities'][1],));quests.action(self.db,'Север','ledger',d['search_sites'][d['search_answer']])
  self.db.execute('UPDATE portal_parties SET city_id=?',(d['cities'][2],));return run,d

 def test_board_is_responsive_and_does_not_reveal_uncollected_evidence(self):
  quests.begin(self.db,'Север',random.Random(42));run=quests.state(self.db,'Север')
  board=self.journal().open_board();settle()
  texts=' '.join(c.note.text for c in board.board.notes+board.board.suspects)
  for token in quests.details(run)['detective']['tokens']:self.assertNotIn(token,texts)
  self.assertTrue(board.accuse_button.disabled)
  for size,density,scale in (((1160,760),1,1),((640,360),1,1),((1280,576),2,1.2),((320,568),1,1.4)):
   Window.size=size;Metrics.density=density;Metrics.fontscale=scale;settle();board.fit();settle()
   self.assertGreater(board.scroll.height,dp(45));self.assertGreaterEqual(board.accuse_button.height,dp(44))
   for card in board.board.case_cards+board.board.notes+board.board.suspects:
    self.assertGreaterEqual(card.x,board.board.x)
    self.assertLessEqual(card.right,board.board.right+1)
    self.assertGreaterEqual(card.y,board.board.y)
    self.assertLessEqual(card.top,board.board.top+1)
    self.assertGreaterEqual(card.note.font_size,sp(14)-1)
    self.assertLessEqual(card.note.texture_size[1],card.note.height)
   if size==(640,360):board.export_to_png('.release/investigation-board-phone.png')

 def test_clicking_cards_places_real_evidence_then_confirms_accusation(self):
  run,d=self.collect();journal=self.journal();board=journal.open_board();settle()
  money=self.db.execute("SELECT amount FROM resources WHERE faction='Север' AND resource_type='Кроны'").fetchone()[0]
  self.assertEqual(len(board.board.notes),3);self.assertEqual(len(board.board.suspects),3)
  self.assertTrue(board.accuse_button.disabled)
  for key in quests.EVIDENCE_ORDER:
   card=next(c for c in board.board.notes if c.key==key)
   board.scroll.scroll_to(card,animate=False);settle()
   touch=UnitTestTouch(*card.to_window(*card.center))
   touch.touch_down();touch.touch_up();settle()
  self.assertEqual(quests.evidence(self.db,'Север')[1],list(quests.EVIDENCE_ORDER))
  correct=d['suspects'][run['culprit']]
  next(c for c in board.board.suspects if c.key==correct).dispatch('on_release');settle()
  self.assertFalse(board.accuse_button.disabled)
  board.export_to_png('.release/investigation-board-desktop.png')
  self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE faction='Север' AND resource_type='Кроны'").fetchone()[0],money)
  touch=UnitTestTouch(*board.accuse_button.to_window(*board.accuse_button.center))
  touch.touch_down();touch.touch_up();settle()
  self.assertEqual(quests.state(self.db,'Север')['detective'],3)
  self.assertTrue(board.finished);self.assertTrue(board.accuse_button.disabled)

 def test_investigation_actions_and_persistent_search_hint_live_only_on_board(self):
  quests.begin(self.db,'Север',random.Random(42));run=quests.state(self.db,'Север');d=quests.details(run)['detective']
  self.db.execute('UPDATE portal_parties SET city_id=?',(d['cities'][0],))
  journal=self.journal();board=journal.open_board();settle()
  self.assertEqual(len(journal.cards.pages[0].buttons.children),1)
  self.assertNotIn(d['premise'],' '.join(c.text for c in journal.cards.pages[0].sections))
  board.accuse_button.dispatch('on_release');settle()
  self.assertEqual(quests.state(self.db,'Север')['detective'],1)
  site=d['search_sites'][d['search_answer']]
  self.assertIn(search_hint(d),' '.join(c.note.text for c in board.board.notes))
  self.assertFalse(journal.feedback.text)
  board.dismiss(animation=False);settle()
  self.db.execute('UPDATE portal_parties SET city_id=?',(d['cities'][1],))
  journal.refresh();board=journal.open_board();settle()
  action=next(c for c in board.board.case_cards if c.heading.text=='Искать: '+site)
  action.dispatch('on_release');settle()
  self.assertEqual(quests.state(self.db,'Север')['detective'],2)
  self.assertFalse(journal.feedback.text)
  for token in d['tokens']:
   self.assertIn(token,' '.join(c.note.text for c in board.board.notes))
   self.assertNotIn(token,' '.join(c.text for c in journal.cards.pages[0].sections))
  Window.size=(640,360);settle();board.fit();settle()
  board.scroll.scroll_y=1;settle();board.export_to_png('.release/board-only-materials-phone.png')
  board.dismiss(animation=False);settle();journal.export_to_png('.release/journal-board-only-phone.png')

 def test_reset_and_wrong_location_keep_original_game_rules(self):
  run,d=self.collect();board=self.journal().open_board();settle()
  key=quests.EVIDENCE_ORDER[0];board.place(key);settle();board.reset();settle()
  self.assertEqual(quests.evidence(self.db,'Север')[1],[])
  self.db.execute('UPDATE portal_parties SET city_id=1');board.refresh();settle()
  board.select_suspect(d['suspects'][0]);self.assertTrue(board.accuse_button.disabled)
  self.assertTrue(all(c.callback is None for c in board.board.notes))

 def test_next_city_and_earned_search_site_remain_visible_after_reopening(self):
  quests.begin(self.db,'Север',random.Random(42));run=quests.state(self.db,'Север');d=quests.details(run)['detective']
  from otherworld_themes import theme
  names=theme('Север')['cities']
  self.db.execute('UPDATE portal_parties SET city_id=?',(d['cities'][0],))
  journal=self.journal();board=journal.open_board();settle()
  self.assertIn(names[d['cities'][0]-1],board.status.text)
  site=d['search_sites'][d['search_answer']]
  self.assertNotIn(' · '+site,board.status.text)
  board.accuse_button.dispatch('on_release');settle()
  self.assertIn(names[d['cities'][1]-1],board.status.text)
  self.assertIn(search_hint(d),board.status.text)
  board.dismiss(animation=False)
  # Legacy progress survives even if the evidence table was absent/empty.
  self.db.execute('DELETE FROM portal_evidence')
  board=journal.open_board();settle()
  self.assertIn(search_hint(d),board.status.text)
  self.assertIn(search_hint(d),next(c.note.text for c in board.board.notes if c.key==quests.EVIDENCE_ORDER[0]))
  self.assertEqual(quests.evidence(self.db,'Север')[0],[quests.EVIDENCE_ORDER[0]])
  Window.size=(640,360);settle();board.fit();settle()
  self.assertLessEqual(board.status.texture_size[1],board.status.height)
  self.assertGreater(board.scroll.height,dp(45))
  board.export_to_png('.release/investigation-search-hint-phone.png')

 def test_legacy_completed_search_restores_all_earned_evidence(self):
  run,d=self.collect()
  self.db.execute('DELETE FROM portal_evidence')
  board=self.journal().open_board();settle()
  self.assertEqual(quests.evidence(self.db,'Север')[0],list(quests.EVIDENCE_ORDER))
  for key in quests.EVIDENCE_ORDER:board.place(key)
  self.assertEqual(quests.evidence(self.db,'Север')[1],list(quests.EVIDENCE_ORDER))

 def test_noble_investigation_always_names_the_search_city(self):
  self.db.executescript('CREATE TABLE season(id,season_index); INSERT INTO season VALUES(1,0);')
  hunt.begin(self.db,'Север',random.Random(3));case=hunt.state(self.db,'Север')
  from otherworld_themes import theme
  city=theme('Север')['cities'][case['city_id']-1]
  board=self.journal().open_board(noble=True);settle()
  self.assertIn(city,board.status.text)
  self.assertIn('Опросите',board.status.text)
  self.db.execute('UPDATE portal_parties SET city_id=?',(case['city_id'],))
  hunt.investigate(self.db,'Север');board.refresh();settle()
  self.assertIn(city,board.status.text)
  self.assertIn('Проверьте следы',board.status.text)

 def test_legacy_three_ladies_have_distinct_loaded_faces_on_the_board(self):
  self.db.executescript('CREATE TABLE season(id,season_index); INSERT INTO season VALUES(1,0);')
  hunt.begin(self.db,'Север',random.Random(3));case=hunt.state(self.db,'Север')
  story=json.loads(case['scenario']);names=hunt.NOBLES['Север'][1::2]
  for n,name in zip(story['nobles'],names):
   n['name']=name;n.pop('gender',None);n.pop('appearance',None)
  self.db.execute('UPDATE portal_monster_cases SET scenario=? WHERE id=?',(json.dumps(story),case['id']))
  board=self.journal().open_board(noble=True);settle()
  portraits=[c.portrait for c in board.board.suspects]
  self.assertEqual(len({p.source for p in portraits}),3)
  self.assertTrue(all(p.texture is not None for p in portraits))
  board.scroll.scroll_y=0;settle()
  board.export_to_png('.release/noble-distinct-ladies-board.png')
  Window.size=(640,360);settle();board.fit();settle()
  board.scroll.scroll_to(board.board.suspects[0],animate=False);settle()
  board.export_to_png('.release/noble-distinct-ladies-phone.png')

 def test_noble_board_compares_both_clues_without_revealing_the_monster(self):
  self.db.executescript('CREATE TABLE season(id,season_index); INSERT INTO season VALUES(1,0);')
  hunt.begin(self.db,'Север',random.Random(3));case=hunt.state(self.db,'Север')
  self.db.execute('UPDATE portal_parties SET city_id=?',(case['city_id'],))
  hunt.investigate(self.db,'Север');hunt.investigate(self.db,'Север')
  story=json.loads(hunt.state(self.db,'Север')['scenario'])
  board=self.journal().open_board(noble=True);settle()
  correct=story['nobles'][story['culprit']]['name'];wrong=story['nobles'][(story['culprit']+1)%3]['name']
  self.assertEqual(len({c.portrait.source for c in board.board.suspects}),3)
  self.assertEqual([c.portrait.source for c in board.board.suspects],[hunt.noble_portrait(hunt.state(self.db,'Север'),n['name']) for n in story['nobles']])
  self.assertNotIn(story['monster'],' '.join(c.note.text for c in board.board.notes+board.board.suspects))
  board.select_suspect(wrong);board.accuse();settle()
  self.assertIn(wrong,json.loads(hunt.state(self.db,'Север')['scenario'])['cleared'])
  board.select_suspect(correct);board.accuse();settle()
  self.assertTrue(hunt.identified(hunt.state(self.db,'Север')))
  self.assertFalse(hunt.revealed(hunt.state(self.db,'Север')))
  self.assertIsNone(board.parent)
  board.journal.noble_encounter.export_to_png('.release/noble-encounter.png')

if __name__=='__main__':unittest.main()
