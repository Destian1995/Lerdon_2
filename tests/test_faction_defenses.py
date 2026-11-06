"""Faction defenses preserve saved construction and fit narrow town screens."""
import unittest
from strategy_ui_fixture import Window
from test_town_interior import TownTests
from test_dialog_layout import settle
from city_construction import building_name,DEFENSE_BONUS,buy_building,building_counts
from town_art import defense_lot,THEMES


class FactionDefenseTests(unittest.TestCase):
    setUp=TownTests.setUp
    tearDown=TownTests.tearDown

    def test_saved_wall_is_presented_as_owner_defense_without_a_second_purchase(self):
        expected={'Север':'Арсенал','Элины':'Пещера дракона','Вампиры':'Стена',
                  'Эльфы':'Древо силы','Адепты':'Аббатство'}
        town=self.owner._open_build_menu();settle()
        for faction,name in expected.items():
            with self.subTest(faction=faction):
                self.db.execute('DELETE FROM buildings')
                self.db.execute('UPDATE cities SET faction=?',(faction,))
                self.db.execute('INSERT INTO buildings VALUES(?,?,?,1)',(self.owner.city_name,faction,'Стена'))
                town.choose('Стена');settle()
                row=town.selectors['Стена']
                self.assertEqual(row.title.text,name)
                self.assertIn(name,row.compact_label.text)
                self.assertEqual(town.selector.text,name)
                self.assertTrue(row.is_built)
                self.assertIn('Стена',town.scene.sprites)
                with self.assertRaises(ValueError):buy_building(self.db,self.owner.city_name,faction,'Стена')
                self.assertEqual(building_counts(self.db,self.owner.city_name,faction)['Стена'],1)
        self.assertEqual(DEFENSE_BONUS,.15)

    def test_tall_defenses_fit_panorama_and_unlisted_factions_keep_walls(self):
        for faction in ('Север','Элины','Эльфы','Адепты'):
            for aspect in (.5,1,2):
                x,y,width=defense_lot(faction,16/9,aspect)
                self.assertLessEqual(y+width*16/9*aspect,.98001)
                self.assertLessEqual(x+width/2,1)
        for faction in ('Нежить','Мятежники','Нейтрал'):
            self.assertEqual(building_name(faction,'Стена'),'Стена')


if __name__=='__main__':unittest.main()
