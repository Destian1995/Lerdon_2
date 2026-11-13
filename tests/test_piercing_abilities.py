"""Piercing volleys and ranged swords share the existing hero damage rules."""
import unittest
from unittest.mock import Mock
from test_tactical_combat import unit
from test_tactical_abilities import arena
from tactical_combat import TacticalBattle
from tactical_abilities import ABILITIES


def line_battle(name='Владислав'):
 hero=unit(name,1,attack=1000,defense=1000,initiative=100,cls=3)
 model=TacticalBattle([hero,unit('Солдаты',200,initiative=10)],
   [unit('Первый',10000),unit('Второй',10000),unit('Третий',10000),unit('За пределом',10000)])
 a,g,b,c,d,out=list(model.stacks.values())
 for stack,pos in zip((a,g,b,c,d,out),((1,2),(1,0),(4,2),(5,2),(6,2),(7,2))):stack.pos=pos
 model.terrain={p:'plain' for p in model.terrain}
 return model,a,g,b,c,d,out


class PiercingAbilityTests(unittest.TestCase):




 def test_agilar_keeps_whirlwind_and_throws_three_swords_for_fifteen_percent(self):
  m,a,g,b,c,d,out=line_battle('Агилар')
  self.assertEqual(set(m.skills()),{'whirlwind','sword_throw'})
  expected=m.skill_power(a,True)/m._resistance(b);old=b.hp;rear=c.hp
  event=m.use_ability('sword_throw',b.pos)
  self.assertEqual(len(event['strikes']),3)
  self.assertAlmostEqual(old-b.hp,expected);self.assertEqual(c.hp,rear)
  self.assertEqual(a.cooldowns['sword_throw'],m.round+ABILITIES['sword_throw'].cooldown)
  m.queue.insert(0,a.id)
  self.assertFalse(m.ability_valid('sword_throw',b.pos))

 def test_sword_throw_obeys_visibility_and_ai_can_use_it_at_range(self):
  m,a,g,b,c,d,out=line_battle('Агилар');m.terrain[3,2]='rock'
  self.assertFalse(m.ability_valid('sword_throw',b.pos))
  m.terrain[3,2]='plain'
  event=m.ai_step();self.assertEqual(event['ability'],'sword_throw')


import test_tactical_battle_ui as ui_fixture
from tactical_battle_ui import TacticalBattlePopup

class PiercingAbilityUITests(unittest.TestCase):
 setUp=ui_fixture.TacticalUITests.setUp
 tearDown=ui_fixture.TacticalUITests.tearDown


 def test_sword_throw_is_in_the_book_and_uses_steel_projectiles_and_throw_sound(self):
  model,a,g,b,c,d,out=line_battle('Агилар')
  view=TacticalBattlePopup(model,'attacker',lambda _:None);self.views.append(view)
  view.deploying=False;view.audio=Mock();view.open(animation=False);ui_fixture.settle()
  view.clock_event.cancel();view.clock_event=None
  book=view.show_skills();self.views.append(book);ui_fixture.settle()
  self.assertIn('sword_throw',book.tiles);book.select_skill('sword_throw')
  self.assertIn('15%',book.description.text);self.assertTrue(book.power.text)
  self.assertIsNotNone(book.tiles['sword_throw'].icon.texture)
  book.dismiss(animation=False);ui_fixture.settle()
  view.animate(model.use_ability('sword_throw',b.pos));view.tick(.1)
  self.assertTrue(view.projectiles)
  self.assertTrue(all(hit['ability']=='sword_throw' for hit,_ in view.projectiles))
  view.audio.play.assert_any_call('throw',owner=view)
  view.board.draw()

if __name__=='__main__':unittest.main()
