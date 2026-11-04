"""Current bonus summaries use the same rules as resource and combat calculations."""
import sqlite3
import unittest

from utils.faction_bonuses import council_bonuses, current_effect_rows, combat_multiplier, supplied_cities


class CurrentBonusTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
            CREATE TABLE nobles(loyalty REAL, ideology TEXT, status TEXT);
            CREATE TABLE cities(id INTEGER, name TEXT, faction TEXT);
            CREATE TABLE roads(city1 INTEGER, city2 INTEGER);
            CREATE TABLE buildings(city_name TEXT, faction TEXT, building_type TEXT, count INTEGER);
            CREATE TABLE season(season_index INTEGER);
            INSERT INTO season VALUES(0);
            INSERT INTO cities VALUES(1,'Столица','Север'),(2,'Порт','Север'),(3,'Остров','Север');
            INSERT INTO roads VALUES(1,2);
        ''')

    def tearDown(self):
        self.db.close()

    def test_council_sums_only_effective_active_bonuses(self):
        self.db.executemany('INSERT INTO nobles VALUES(?,?,?)', [
            (80, 'Смирение', 'active'), (75, 'Борьба', 'active'),
            (95, '{"type":"greed"}', 'active'),
            (57, 'Любит Эльфы', 'active'), (90, 'Любит Север', 'active'),
            (54, 'Смирение', 'active'), (30, 'Борьба', 'active'),
            (100, 'Смирение', 'eliminated'), (100, '{broken', 'active'),
        ])
        summary = council_bonuses(self.db, 'Север')
        self.assertEqual(summary['crowns'], 10)
        self.assertEqual(summary['crystals'], 9)
        self.assertEqual(summary['trade'], 9.5)
        self.assertEqual(summary['active'], 4)
        self.assertEqual(dict(summary['relations']), {'Эльфы': 7})

    def test_buildings_respect_supply_and_keep_defense_local(self):
        self.db.executemany('INSERT INTO buildings VALUES(?,?,?,?)', [
            ('Столица', 'Север', 'Рынок', 2), ('Остров', 'Север', 'Рынок', 3),
            ('Порт', 'Север', 'Фабрика', 2), ('Столица', 'Север', 'Больница', 3),
            ('Порт', 'Север', 'Вышка', 2), ('Столица', 'Север', 'Стена', 2),
            ('Остров', 'Север', 'Стена', 1), ('Порт', 'Север', 'Кузница', 3),
            ('Чужой', 'Эльфы', 'Рынок', 20),
        ])
        self.assertEqual(supplied_cities(self.db, 'Север'), {'Столица', 'Порт'})
        rows = {name: (count, effect) for name, count, effect in current_effect_rows(self.db, 'Север', 0)}
        self.assertEqual(rows['Рынки'][0], 2)
        self.assertIn('+20%', rows['Рынки'][1])
        self.assertEqual(rows['Рынок · без снабжения'][0], 3)
        self.assertIn('2142', rows['Фабрики'][1])
        self.assertIn('+2160', rows['Больницы'][1])
        self.assertIn('+1000', rows['Вышки'][1])
        self.assertIn('+30%', rows['Стены · Столица'][1])
        self.assertIn('+15%', rows['Стены · Остров'][1])
        self.assertIn('+15%', rows['Кузницы · Порт'][1])

    def test_seasonal_combat_multipliers_match_display(self):
        self.assertAlmostEqual(combat_multiplier('Север', self.db), 1.8 * 2.75)
        self.assertAlmostEqual(combat_multiplier('Адепты', self.db), 1.55)
        self.db.execute('UPDATE season SET season_index=3')
        self.assertAlmostEqual(combat_multiplier('Север', self.db), 1.8)
        self.assertAlmostEqual(combat_multiplier('Адепты', self.db), 1.55 * 2.75)


if __name__ == '__main__':
    unittest.main()
