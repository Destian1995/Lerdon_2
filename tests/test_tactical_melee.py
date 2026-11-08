"""Close attacks and counterattacks use drawn melee clips, never ranged effects."""
import unittest
from unittest.mock import Mock

import test_tactical_battle_ui as ui_fixture
from test_tactical_combat import unit
from tactical_combat import TacticalBattle
from tactical_battle_ui import TacticalBattlePopup,SpriteLibrary
from game_audio import attack_sound


class TacticalMeleeTests(unittest.TestCase):
    setUp=ui_fixture.TacticalUITests.setUp
    tearDown=ui_fixture.TacticalUITests.tearDown

    def battle(self,distance=1,kind='archer',image='files/army/people/predator.jpg'):
        soldier=unit('Attacker',100,kind,initiative=100)
        soldier['unit_image']=image
        enemy=unit('Defender',100,kind,initiative=40)
        enemy['unit_image']=image
        model=TacticalBattle([soldier],[enemy],terrain={(x,y):'plain' for x in range(10) for y in range(6)})
        a=model.stacks['attacker:0'];b=model.stacks['defender:0']
        a.pos=(1,2);b.pos=(1+distance,2)
        view=TacticalBattlePopup(model,'attacker',lambda _:None)
        self.views.append(view);view.deploying=False;view.audio=Mock()
        return model,a,b,view

    def test_adjacent_and_diagonal_shots_use_melee_including_retaliation(self):
        for diagonal in (False,True):
            model,a,b,view=self.battle()
            if diagonal:b.pos=(2,3)
            view.animate(model.attack(b.id));view.tick(.01)
            self.assertEqual(view.animations[a.id][0],'melee')
            self.assertEqual(view.visual(a)[0],'melee')
            view.audio.play.assert_called_with('hit',owner=view)
            for _ in range(8):view.tick(.1)
            self.assertEqual(view.animations[b.id][0],'melee')

    def test_distant_attack_keeps_ranged_clip_and_rifle_sound(self):
        model,a,b,view=self.battle(distance=5)
        view.animate(model.attack(b.id));view.tick(.01)
        self.assertEqual(view.animations[a.id][0],'attack')
        view.audio.play.assert_called_with('rifle',owner=view)

    def test_close_attack_turns_towards_an_enemy_that_moved_behind_the_unit(self):
        model,a,b,view=self.battle()
        a.pos=(5,2);b.pos=(4,2)
        view.animate(model.attack(b.id));view.tick(.01)
        self.assertEqual(view.animations[a.id][0],'melee')
        self.assertTrue(view.facings[a.id])
        for _ in range(8):view.tick(.1)
        self.assertFalse(view.facings[b.id])

    def test_staff_attack_is_not_a_spell_sound_at_close_range(self):
        model,a,b,view=self.battle(kind='mage',image='files/army/poly/fanatik.jpg')
        view.animate(model.attack(b.id));view.tick(.01)
        self.assertEqual(view.animations[a.id][0],'melee')
        view.audio.play.assert_called_with('hit',owner=view)
        self.assertEqual(attack_sound({'unit_image':'files/army/elfs/archer.jpg'},'archer',False),'sword')
        self.assertEqual(attack_sound(a.unit,'mage',True),'magic')

    def test_missing_optional_melee_clip_falls_back_to_existing_attack(self):
        library=SpriteLibrary();self.addCleanup(library.clear)
        soldier={'unit_image':'files/army/adepts/paladin.jpg'}
        melee=library.frame(soldier,'melee',.2)[0]
        attack=library.frame(soldier,'attack',.2)[0]
        self.assertEqual(melee.tex_coords,attack.tex_coords)
        self.assertFalse(library.extra_atlases)

    def test_supplemental_frames_load_lazily_animate_and_release_with_the_battle(self):
        library=SpriteLibrary()
        soldier={'unit_image':'files/army/people/predator.jpg'}
        library.frame(soldier,'idle',0)
        self.assertFalse(library.extra_atlases)
        first=library.frame(soldier,'melee',0)[0]
        contact=library.frame(soldier,'melee',.25)[0]
        self.assertNotEqual(first.tex_coords,contact.tex_coords)
        self.assertEqual(first.size,(512,512))
        self.assertEqual(len(library.extra_atlases),1)
        self.assertGreater(library.scale(soldier,'melee'),0)
        library.clear()
        self.assertFalse(library.extra_atlases)


if __name__=='__main__':unittest.main()
