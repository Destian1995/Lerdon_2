import sqlite3
import unittest

from unit_updates import migrate_morgana, canonical_unit_name, ensure_morgana_guardian, MORGANA_IMAGE
from undead_invasion import _create_undead_units


class MorganaTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        columns = '''id INTEGER, faction TEXT, unit_name TEXT UNIQUE, cost_money REAL, cost_time INTEGER,
            image_path TEXT, attack REAL, defense REAL, durability REAL, unit_class TEXT, consumption REAL,
            initiative INTEGER, unit_type TEXT, morale INTEGER, aura_attack REAL, aura_defense REAL, crit_chance REAL'''
        for table in ('units_default', 'units'):
            self.db.execute(f'CREATE TABLE {table} ({columns})')
            self.db.execute(f'INSERT INTO {table} VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                ('Нежить', 'Наместник', 0, 0, 'files/army/death/death.png', 8, 800, 50,
                 '2', 0, 80, 'siege', 100, 0, 0, 10))
        self.db.execute('''CREATE TABLE garrisons(city_name,unit_name,unit_count,unit_image,experience DEFAULT 0,
                                                UNIQUE(city_name,unit_name))''')
        self.db.execute('INSERT INTO garrisons VALUES ("Некрополь","Наместник",1,"old.png",3)')
        self.db.execute('CREATE TABLE armies(unit_type,quantity,total_attack,total_defense,unit_image)')
        self.db.execute('INSERT INTO armies VALUES ("Наместник",1,8,800,"old.png")')

    def tearDown(self):
        self.db.close()

    def test_rename_preserves_every_other_stat_and_adds_exactly_200_attack(self):
        original = self.db.execute('SELECT * FROM units_default').fetchone()
        migrate_morgana(self.db)
        for table in ('units_default', 'units'):
            actual = self.db.execute(f'SELECT * FROM {table}').fetchone()
            expected = list(original)
            expected[2], expected[5], expected[6] = 'Моргана', MORGANA_IMAGE, 208
            self.assertEqual(actual, tuple(expected))
        self.assertEqual(self.db.execute('SELECT unit_name,unit_image,experience FROM garrisons').fetchone(),
                         ('Моргана', MORGANA_IMAGE, 3))
        self.assertEqual(self.db.execute('SELECT unit_type,total_attack,total_defense FROM armies').fetchone(),
                         ('Моргана', 208, 800))

    def test_repeat_startup_does_not_add_attack_again(self):
        for _ in range(4):
            migrate_morgana(self.db)
        self.assertEqual(self.db.execute('SELECT attack FROM units_default').fetchone()[0], 208)
        self.assertEqual(self.db.execute('SELECT total_attack FROM armies').fetchone()[0], 208)

    def test_existing_guardian_rows_merge_without_duplicate_hero(self):
        self.db.execute('INSERT INTO garrisons VALUES ("Некрополь","Моргана",1,"new.png",1)')
        migrate_morgana(self.db)
        self.assertEqual(self.db.execute('SELECT unit_name,unit_count,experience FROM garrisons').fetchall(),
                         [('Моргана', 1, 3)])

    def test_capital_respawns_only_morgana_with_new_portrait(self):
        migrate_morgana(self.db)
        self.db.execute('UPDATE garrisons SET unit_count=0')
        self.assertTrue(ensure_morgana_guardian(self.db.cursor(), 'Некрополь'))
        self.assertFalse(ensure_morgana_guardian(self.db.cursor(), 'Некрополь'))
        self.assertEqual(self.db.execute('SELECT unit_name,unit_count,unit_image FROM garrisons').fetchall(),
                         [('Моргана', 1, MORGANA_IMAGE)])

    def test_default_restore_and_empty_database_fallback_both_include_morgana(self):
        _create_undead_units(self.db.cursor())
        self.assertEqual(self.db.execute('SELECT attack FROM units WHERE unit_name="Моргана"').fetchone()[0], 208)
        self.db.execute('DELETE FROM units')
        self.db.execute('DELETE FROM units_default')
        _create_undead_units(self.db.cursor())
        self.assertEqual(self.db.execute('SELECT attack,defense,durability,image_path FROM units WHERE unit_name="Моргана"').fetchone(),
                         (208, 800, 50, MORGANA_IMAGE))

    def test_name_change_does_not_trigger_bulk_replacement_of_player_units(self):
        self.assertEqual(canonical_unit_name('Наместник'), canonical_unit_name('Моргана'))
        self.assertEqual(canonical_unit_name('Низар'), 'Низар')


if __name__ == '__main__':
    unittest.main()
