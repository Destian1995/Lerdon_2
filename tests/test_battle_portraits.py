import unittest
from battle_presentation import pick_battle_image


class BattlePortraitTests(unittest.TestCase):
    def test_main_map_priority_is_shared_and_accepts_both_army_formats(self):
        army=[dict(unit_class=1,unit_image='troop.png'),
              dict(unit_class='4',unit_image='legend.png'),
              dict(units_stats={'Класс юнита':' 2 Герой '},unit_image='hero.png'),
              dict(unit_class='3 Чемпион',image_path='champion.png')]
        self.assertEqual(pick_battle_image(army,'Север'),'champion.png')
        self.assertEqual(pick_battle_image(army[:-1],'Север'),'hero.png')
        self.assertEqual(pick_battle_image(army[:2],'Север'),'legend.png')
        self.assertEqual(pick_battle_image(army[:1],'Север'),'troop.png')
        self.assertIsNone(pick_battle_image([],'Север'))
        self.assertEqual(pick_battle_image(army,'Нежить'),'files/army/death/banshi.png')

    def test_undead_use_present_named_hero_or_banshee_regardless_of_stack_order(self):
        soldiers=[dict(unit_name='Призрак',unit_count=100,unit_image='files/army/death/solder.png')]
        self.assertEqual(pick_battle_image(soldiers,'Нежить'),'files/army/death/banshi.png')
        for name,path in (('Низар','king_'),('Моргана','morgana')):
            with self.subTest(hero=name):
                hero=dict(unit_name=name,unit_count=1,unit_class='2',unit_image='old-wrong.png')
                self.assertEqual(pick_battle_image(soldiers+[hero],'Нежить'),f'files/army/death/{path}.png')
                self.assertEqual(pick_battle_image([hero]+soldiers,'Нежить'),f'files/army/death/{path}.png')
                hero['unit_count']=0
                self.assertEqual(pick_battle_image(soldiers+[hero],'Нежить'),'files/army/death/banshi.png')
