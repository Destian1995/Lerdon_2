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
 def test_burst_hits_primary_and_exactly_two_cells_behind_with_three_shots(self):
  m,a,g,b,c,d,out=line_battle();power=m.skill_power(a,True)
  expected={s.id:power/m._resistance(s) for s in (b,c,d)}
  old={s.id:s.hp for s in (b,c,d,out)}
  self.assertEqual(m.ability_cells('burst',b.pos),[(4,2),(5,2),(6,2)])
  event=m.use_ability('burst',b.pos)
  for s in (b,c,d):self.assertAlmostEqual(old[s.id]-s.hp,expected[s.id])
  self.assertEqual(out.hp,old[out.id]);self.assertEqual(len(event['strikes']),9)
  self.assertEqual([hit['shot'] for hit in event['strikes']],[0,0,0,1,1,1,2,2,2])
  self.assertEqual(sum(hit['volley_lead'] for hit in event['strikes']),3)

 def test_diagonal_and_sloping_rays_and_edges_follow_the_aim_direction(self):
  m,a,g,b,*_=line_battle()
  for origin,target,expected in (((1,1),(3,3),[(3,3),(4,4),(5,5)]),
     ((1,1),(3,2),[(3,2),(4,3),(5,3)]),((4,4),(2,3),[(2,3),(1,2),(0,2)]),
     ((1,2),(9,2),[(9,2)]),((5,4),(5,1),[(5,1),(5,0)])):
   a.pos=origin;b.pos=target
   self.assertEqual(m.ability_cells('burst',target),expected)

 def test_piercing_does_not_hit_allies_or_bypass_bodyguards(self):
  m,a,g,b,c,d,out=line_battle();g.pos=(5,2);c.pos=(8,4)
  old=g.hp;event=m.use_ability('burst',b.pos)
  self.assertEqual(g.hp,old);self.assertNotIn(g.id,[h['target'] for h in event['strikes']])
  m,a,g,b,h=arena('Владислав');a.pos=(1,2);b.pos=(4,2);h.pos=(5,2)
  b.count=1;b.hp=1
  old=h.hp;m.use_ability('burst',b.pos)
  self.assertFalse(b.alive);self.assertEqual(h.hp,old)

 def test_rocks_and_forest_stop_collateral_but_primary_range_stays_seven(self):
  m,a,g,b,c,d,out=line_battle();m.terrain[5,2]='rock'
  self.assertEqual(m.ability_cells('burst',b.pos),[(4,2)])
  m.terrain[5,2]='forest'
  self.assertEqual(m.ability_cells('burst',b.pos),[(4,2),(5,2)])
  old=d.hp;m.use_ability('burst',b.pos);self.assertEqual(d.hp,old)
  m,a,g,b,*_=line_battle();a.pos=(0,2);b.pos=(8,2)
  self.assertFalse(m.ability_valid('burst',b.pos))

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

 def test_piercing_animates_three_shots_instead_of_nine_separate_attacks(self):
  model,a,g,b,c,d,out=line_battle()
  view=TacticalBattlePopup(model,'attacker',lambda _:None);self.views.append(view)
  view.deploying=False;view.audio=Mock();view.animate(model.use_ability('burst',b.pos))
  self.assertEqual(len(view.pending_strikes),9)
  self.assertEqual(len({when for when,_ in view.pending_strikes}),3)
  self.assertLess(view.busy,1.2)
  for _ in range(7):view.tick(.1)
  self.assertEqual(sum(call.args[0]=='rifle' for call in view.audio.play.call_args_list),3)

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
