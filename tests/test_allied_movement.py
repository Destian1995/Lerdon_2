"""The troop picker and actual movement must agree for every source garrison."""
import ast
from collections import defaultdict
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest

from utils.movement_rules import reachable_source_cities, can_move_between_cities


def city_methods(*names, **extra):
    tree = ast.parse(Path('ui.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'FortressInfoPopup')
    nodes = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    namespace = dict(sqlite3=sqlite3, defaultdict=defaultdict, **extra)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'ui.py', 'exec'), namespace)
    return namespace


class AlliedMovementTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
            CREATE TABLE cities(id INTEGER,name TEXT,faction TEXT);
            INSERT INTO cities VALUES (1,'Наш ближний','Север'),(2,'Союзник','Эльфы'),
              (3,'Наш дальний','Север'),(4,'Союзный дальний','Эльфы'),
              (5,'Враг','Вампиры'),(6,'Через врага','Север'),(7,'Остров','Север');
            CREATE TABLE roads(city1 INTEGER,city2 INTEGER);
            INSERT INTO roads VALUES(1,2),(1,3),(2,4),(2,5),(5,6);
            CREATE TABLE diplomacies(faction1 TEXT,faction2 TEXT,relationship TEXT);
            INSERT INTO diplomacies VALUES('Эльфы','Север','союз');
            CREATE TABLE units(unit_name TEXT,faction TEXT,unit_class TEXT,image_path TEXT,attack,defense,durability);
            INSERT INTO units VALUES('Мечник','Север','1','',10,5,4),('Герой','Север','2','',10,5,4),
              ('Защитник','Север','1','',5,10,4),('Чужой','Эльфы','1','',5,10,4);
            CREATE TABLE garrisons(city_name TEXT,unit_name TEXT,unit_count INTEGER,unit_image TEXT);
            INSERT INTO garrisons VALUES('Наш ближний','Мечник',10,''),('Наш ближний','Герой',1,''),
              ('Наш ближний','Защитник',10,''),('Наш дальний','Мечник',20,''),
              ('Союзный дальний','Мечник',5,''),('Союзный дальний','Чужой',10,''),
              ('Через врага','Мечник',10,''),('Остров','Мечник',10,'');
        ''')

    def tearDown(self):
        self.db.close()

    def test_allied_target_accepts_only_direct_friendly_sources(self):
        self.assertEqual(reachable_source_cities(self.db, 'Союзник', 'Север'),
                         {'Наш ближний', 'Союзный дальний'})
        self.assertFalse(can_move_between_cities(self.db, 'Наш дальний', 'Союзник', 'Север'))
        self.assertFalse(can_move_between_cities(self.db, 'Через врага', 'Союзник', 'Север'))
        self.assertFalse(can_move_between_cities(self.db, 'Союзник', 'Союзник', 'Север'))

    def test_ordinary_movement_keeps_own_territory_routes(self):
        self.db.execute('INSERT INTO roads VALUES(3,7)')
        self.assertEqual(reachable_source_cities(self.db, 'Наш ближний', 'Север'),
                         {'Наш дальний', 'Остров', 'Союзник'})
        self.assertFalse(can_move_between_cities(self.db, 'Союзный дальний', 'Наш ближний', 'Север'))

    def test_picker_filters_routes_for_both_modes_and_all_troop_types(self):
        errors, selections = [], []
        ns = city_methods('load_troops_by_type', _show_dark_error_popup=lambda *args: errors.append(args))
        owner = SimpleNamespace(conn=self.db, city_name='Союзник', player_fraction='Север',
                                is_ally=lambda first, second: second == 'Эльфы',
                                show_troops_selection=lambda rows: selections.append(rows))
        for mode in ('transfer', 'control'):
            for troop_type in ('Любых', 'Атакующих', 'Защитных'):
                with self.subTest(mode=mode, troop_type=troop_type):
                    ns['load_troops_by_type'](owner, troop_type, None, _transfer_mode=mode)
                    self.assertFalse(errors)
                    rows = selections[-1]
                    self.assertTrue(rows)
                    self.assertTrue(all(row[0] in ('Наш ближний', 'Союзный дальний') for row in rows))
                    self.assertFalse(any(row[1] == 'Чужой' for row in rows))
                    if mode == 'transfer':
                        self.assertFalse(any(row[1] == 'Герой' for row in rows))

    def test_group_revalidates_every_source_before_moving_any_units(self):
        self.db.executescript('''CREATE TABLE turn_check_move(faction,can_move,moves_left);
            INSERT INTO turn_check_move VALUES('Север',1,1);''')
        errors, transfers = [], []
        ns = city_methods('move_selected_group_to_city', show_popup_message=lambda *args: errors.append(args))
        owner = SimpleNamespace(conn=self.db, city_name='Союзник', player_fraction='Север',
                                get_relationship=lambda *_: 'союз', update_garrison=lambda: None,
                                selected_group=[dict(city_name='Наш ближний', unit_name='Мечник', unit_count=5),
                                                dict(city_name='Наш дальний', unit_name='Мечник', unit_count=5)],
                                transfer_troops_between_cities=lambda **kw: transfers.append(kw))
        ns['move_selected_group_to_city'](owner)
        self.assertTrue(errors)
        self.assertEqual(transfers, [])
        self.assertEqual(self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0], 1)
        self.assertEqual(self.db.execute("SELECT unit_count FROM garrisons WHERE city_name='Наш ближний' AND unit_name='Мечник'").fetchone()[0], 10)

    def test_direct_execution_uses_the_same_routes_as_the_picker(self):
        errors, moved = [], []
        ns = city_methods('transfer_troops_between_cities', show_popup_message=lambda *args: errors.append(args))
        owner = SimpleNamespace(conn=self.db, player_fraction='Север', _ally_transfer_mode='control',
                                get_city_owner=lambda name: self.db.execute('SELECT faction FROM cities WHERE name=?', (name,)).fetchone()[0],
                                is_ally=lambda first, second: second == 'Эльфы',
                                move_troops=lambda *args: moved.append(args))
        for source, target, allowed in (('Наш дальний', 'Союзник', False),
                                         ('Наш ближний', 'Союзник', True),
                                         ('Союзный дальний', 'Союзник', True),
                                         ('Наш дальний', 'Наш ближний', True)):
            with self.subTest(source=source, target=target):
                moved.clear()
                result = ns['transfer_troops_between_cities'](owner, source, target, 'Мечник', 5)
                self.assertEqual(result, allowed)
                self.assertEqual(bool(moved), allowed)


if __name__ == '__main__':
    unittest.main()
