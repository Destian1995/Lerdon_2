"""A centered result and one automatic campaign callback after final animations."""
from unittest.mock import Mock
import unittest
import test_tactical_battle_ui as fixture
from test_tactical_combat import unit
from tactical_combat import TacticalBattle
from tactical_battle_ui import TacticalBattlePopup
from kivy.metrics import Metrics


class TacticalAutoResultTests(unittest.TestCase):
 setUp=fixture.TacticalUITests.setUp
 tearDown=fixture.TacticalUITests.tearDown

 def view(self,player='attacker'):
  model=TacticalBattle([unit('Победитель',100,attack=10000,initiative=100)],
                       [unit('Последний враг',1,attack=1,defense=1,initiative=10)],
                       terrain={(x,y):'plain' for x in range(10) for y in range(6)})
  a,b=list(model.stacks.values());a.pos=(2,2);b.pos=(3,2)
  callback=Mock();view=TacticalBattlePopup(model,player,callback)
  view.audio=Mock();self.views.append(view)
  view.open(animation=False);fixture.settle()
  view.clock_event.cancel();view.clock_event=None
  view.deploying=False;view.refresh()
  return view,callback,a,b

 def test_last_enemy_immediately_shows_centered_victory_and_automatically_finishes_once(self):
  fixture.Window.size=(640,360);fixture.settle()
  view,callback,a,b=self.view()
  view.perform(lambda:view.battle.attack(b.id));fixture.settle()
  self.assertEqual(view.battle.winner,'attacker')
  self.assertIsNotNone(view.result_banner)
  self.assertEqual(view.result_title.text,'ПОБЕДА')
  self.assertAlmostEqual(view.result_banner.center_x,view.layers.center_x,delta=2)
  self.assertAlmostEqual(view.result_banner.center_y,view.layers.center_y,delta=2)
  self.assertNotEqual(view.action.text,'Завершить бой');self.assertTrue(view.action.disabled)
  callback.assert_not_called()
  view.export_to_png('.release/tactical-centered-victory.png')
  for _ in range(35):view.tick(.1)
  callback.assert_called_once_with(view.battle)
  self.assertIsNone(view.parent);self.assertIsNone(view.clock_event)
  self.assertTrue(view.notified);self.assertFalse(view.board.library.atlases)
  view.confirm();view.finish_result();view.tick(.1)
  callback.assert_called_once_with(view.battle)
  self.assertEqual(sum(call.args[0]=='victory' for call in view.audio.play.call_args_list),1)

 def test_final_grenade_and_death_animation_are_not_cut_short(self):
  model=TacticalBattle([unit('Владислав',1,attack=10000,cls=3,initiative=100),unit('Солдаты',100)],
                       [unit('Враг',1,defense=1)],terrain={(x,y):'plain' for x in range(10) for y in range(6)})
  a,g,b=list(model.stacks.values());a.pos=(1,2);g.pos=(0,0);b.pos=(4,2)
  callback=Mock();view=TacticalBattlePopup(model,'attacker',callback);view.deploying=False;view.audio=Mock()
  self.views.append(view);view.open(animation=False);fixture.settle();view.clock_event.cancel();view.clock_event=None
  view.perform(lambda:model.use_ability('grenade',b.pos))
  self.assertIsNotNone(view.result_banner)
  for _ in range(14):view.tick(.1)
  callback.assert_not_called();self.assertIsNotNone(view.parent)
  for _ in range(12):view.tick(.1)
  callback.assert_called_once_with(model)

 def test_defeat_uses_player_side_and_a_readable_result_at_high_speed(self):
  view,callback,a,b=self.view(player='defender');view.speed=4
  view.animate(view.battle.attack(b.id));view.refresh()
  self.assertEqual(view.result_title.text,'ПОРАЖЕНИЕ')
  for _ in range(8):view.tick(.1)
  callback.assert_not_called()
  for _ in range(12):view.tick(.1)
  callback.assert_called_once_with(view.battle)

 def test_open_help_does_not_keep_a_finished_battle_or_overlay_alive(self):
  view,callback,a,b=self.view();view.show_info();fixture.settle()
  child=view.child_popups[-1];self.assertIsNotNone(child.parent)
  view.battle.attack(b.id);view.refresh();fixture.settle()
  self.assertIsNone(child.parent);self.assertFalse(view.help_open)
  for _ in range(25):view.tick(.1)
  callback.assert_called_once_with(view.battle)

if __name__=='__main__':unittest.main()
