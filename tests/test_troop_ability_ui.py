import unittest
from unittest.mock import Mock
import test_tactical_battle_ui as fixture
from test_troop_abilities import field
from tactical_battle_ui import TacticalBattlePopup
from tactical_abilities import TROOPS
from kivy.metrics import Metrics,dp

class TroopAbilityUITests(unittest.TestCase):
 setUp=fixture.TacticalUITests.setUp
 tearDown=fixture.TacticalUITests.tearDown

 def test_all_six_ordinary_troops_have_accessible_books_and_real_icons(self):
  fixture.Window.size=(640,360);fixture.settle()
  for key,(_,names) in TROOPS.items():
   model,a,g,b,c=field(names[0],'beast' if key=='vampire_raise' else 'archer' if key in ('auto_burst','twin_arrow') else 'mage')
   view=TacticalBattlePopup(model,'attacker',lambda _:None);self.views.append(view)
   view.open(animation=False);fixture.settle();view.clock_event.cancel();view.clock_event=None;view.deploying=False;view.refresh()
   self.assertFalse(view.skill_button.disabled)
   book=view.show_skills();self.views.append(book);fixture.settle()
   self.assertIn(key,book.tiles);self.assertIsNotNone(book.tiles[key].icon.texture)
   book.select_skill(key);self.assertIn('5',book.target_info.text)
   book.choose(key);fixture.settle()
   self.assertEqual(view.selected_skill,key)
   view.dismiss(animation=False)

 def test_vortex_and_shield_have_visible_effects_and_resurrection_clears_death_pose(self):
  model,a,g,b,c=field('Маг крови','mage')
  view=TacticalBattlePopup(model,'attacker',lambda _:None);self.views.append(view);view.audio=Mock()
  view.open(animation=False);fixture.settle();view.clock_event.cancel();view.clock_event=None;view.deploying=False
  view.animate(model.use_ability('blood_vortex',b.pos));view.tick(.1)
  self.assertEqual(len(model.vortices),1);view.board.draw()
  view.export_to_png('.release/tactical-blood-vortex.png')
  view.dismiss(animation=False)
  model,a,g,b,c=field('Вестник смерти','beast');b.pos=(2,2);g.count=0;g.hp=0
  view=TacticalBattlePopup(model,'attacker',lambda _:None);self.views.append(view);view.audio=Mock();view.deploying=False
  view.animations[g.id]=('death',0,1)
  view.animate(model.use_ability('vampire_raise',b.pos))
  self.assertNotIn(g.id,view.animations);self.assertTrue(g.alive)
  self.assertTrue(any(key=='heal' for _,_,key in view.ability_fx))

if __name__=='__main__':unittest.main()
