"""Ranged support heroes and Mirror weapons keep faction matchup stats intact."""
import unittest

from game_audio import attack_sound
from tactical_combat import TacticalBattle,weapon_role,RANGE
from unit_combat_presentation import movement_sound
from otherworld_content import unit_catalog,FACTION_UNIT_TYPES
from test_tactical_combat import unit


class UnitCombatPresentationTests(unittest.TestCase):
    def test_defensive_heroes_and_vampire_casters_are_ranged_except_frost(self):
        cases={'Ольга':'people/olga.jpg','Сестра Милосердия':'adepts/sestra.jpg',
               'Кристол':'poly/clare.jpg','Анабэль':'vampires/anabel.jpg',
               'Изабэлл':'vampires/isabel.jpg','Люци':'elfs/disease.jpg','Моргана':'death/morgana.png'}
        for name,image in cases.items():
            with self.subTest(name=name):
                self.assertEqual(weapon_role({'unit_name':name},'infantry'),'mage')
                self.assertEqual(weapon_role({'unit_image':'files/army/'+image},'beast'),'mage')
        self.assertEqual(weapon_role({'unit_name':'Дитрих Фрост'},'mage'),'infantry')
        self.assertEqual(weapon_role({'unit_image':'files/army/vampires/frost.jpg'},'mage'),'infantry')

    def test_ranged_support_can_attack_at_a_distance_without_changing_faction_kind(self):
        hero=unit('Изабэлл',1,'beast',cls=3,initiative=100)
        enemy=unit('Враг',1000,'infantry')
        field={(x,y):'plain' for x in range(10) for y in range(6)}
        battle=TacticalBattle([hero],[enemy],terrain=field)
        a=battle.stacks['attacker:0'];b=battle.stacks['defender:0']
        a.pos=(1,2);b.pos=(6,2)
        self.assertEqual((a.kind,a.role),('beast','mage'))
        self.assertTrue(battle.can_attack(a,b))
        a.role='infantry'
        self.assertFalse(battle.can_attack(a,b))

    def test_mirror_weapon_roles_and_sounds_cover_faction_female_and_legacy_aliases(self):
        expected=('infantry','archer','cavalry','mage','infantry')
        for faction,kind in FACTION_UNIT_TYPES.items():
            for row,role in zip(unit_catalog(faction),expected):
                self.assertEqual(row['unit_type'],kind)
                self.assertEqual(weapon_role(row,kind),role)
                sound=attack_sound(row,role,role in RANGE)
                self.assertIn(sound,('sword','bow','magic','frost','monster','hit'))
        for path,sound in (('north/units/rider','hooves'),('elines/units/golem','stone_step'),
                           ('elves/women/archer','step')):
            self.assertEqual(movement_sound({'unit_image':'atlas://files/otherworld/themes/'+path}),sound)
        for row,role in zip(unit_catalog(),expected):self.assertEqual(weapon_role(row,'beast'),role)


if __name__=='__main__':unittest.main()
