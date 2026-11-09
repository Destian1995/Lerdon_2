import json
from pathlib import Path
import unittest
from unittest.mock import Mock
import test_tactical_battle_ui as fixture
from tactical_combat import TacticalBattle
from tactical_battle_ui import TacticalBattlePopup
from test_tactical_combat import unit


class NobleSpriteUITests(unittest.TestCase):
    setUp=fixture.TacticalUITests.setUp
    tearDown=fixture.TacticalUITests.tearDown

    def test_new_lady_in_reported_battle_is_an_animated_cutout_for_both_sides(self):
        fixture.Window.size=(1000,650)
        noble=unit('Спутник: Леди Изольда',count=1,attack=1000)
        noble['unit_image']='files/otherworld/companions/adepts/noble-lady-2.png'
        enemy=unit('Леди Лиора',count=1)
        enemy['unit_image']='files/otherworld/companions/elves/noble-lady.jpg'
        model=TacticalBattle([noble],[enemy],seed=7)
        view=TacticalBattlePopup(model,'attacker',lambda result:None,'Виндгар')
        self.views.append(view);view.audio=Mock();view.open(animation=False);fixture.settle()
        view.clock_event.cancel();view.clock_event=None;view.deploying=False
        for stack in model.stacks.values():
            self.assertIsNotNone(view.board.library.key(stack.unit))
        actor=model.stacks['attacker:0']
        for action in ('idle','walk','attack','hit','death','melee'):
            view.animations[actor.id]=(action,0,10);view.age=.25;view.board.draw()
            self.assertFalse(view.board.library.fallbacks)
        view.animations.clear();view.board.draw()
        view.export_to_png('.release/tactical-noble-animated-cutout.png')


if __name__=='__main__':unittest.main()
