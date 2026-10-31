import ast
import contextlib
import io
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from undead_garrison import (ARCHER_NAME, ARCHER_IMAGE, ensure_archer_units,
                             migrate_capital_archers, ensure_capital_archers)

ROOT = Path(__file__).resolve().parents[1]


class UndeadGarrisonTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        for table in ('units_default', 'units'):
            self.db.execute(f'''CREATE TABLE {table}(id INTEGER, faction, unit_name, image_path,
                attack, defense, durability, unit_class, consumption, unit_type)''')
            self.db.execute(f'INSERT INTO {table} VALUES (1,?,?,?,?,?,?,?,?,?)',
                            ('Нежить', 'Призрак', 'ghost.png', 75, 15, 15, '1', 0.8, 'siege'))
        self.db.executescript('''
            CREATE TABLE cities(name PRIMARY KEY, faction, color_faction);
            INSERT INTO cities VALUES ('Capital','Нежить','green'), ('Other','Нейтрал','gray');
            CREATE TABLE undead_invasion(id PRIMARY KEY, capital_city);
            INSERT INTO undead_invasion VALUES (1,'Capital');
            CREATE TABLE garrisons(city_name,unit_name,unit_count,unit_image,experience DEFAULT 0,
                                   UNIQUE(city_name,unit_name));
            INSERT INTO garrisons VALUES ('Capital','Призрак',270000,'ghost.png',3);
            INSERT INTO garrisons VALUES ('Other','Призрак',1000,'ghost.png',0);
        ''')

    def tearDown(self):
        self.db.close()

    def count(self, name, city='Capital'):
        row = self.db.execute('SELECT unit_count FROM garrisons WHERE city_name=? AND unit_name=?',
                              (city, name)).fetchone()
        return row[0] if row else 0

    def test_archers_copy_ghost_stats_except_requested_stats_and_archer_type(self):
        ensure_archer_units(self.db)
        ensure_archer_units(self.db)
        for table in ('units_default', 'units'):
            self.assertEqual(self.db.execute(f'''SELECT attack,defense,durability,consumption,
                unit_class,unit_type,image_path FROM {table} WHERE unit_name=?''', (ARCHER_NAME,)).fetchall(),
                [(10, 30, 15, 0.8, '1', 'archer', ARCHER_IMAGE)])
            self.assertEqual(self.db.execute(f'SELECT attack,defense FROM {table} WHERE unit_name="Призрак"').fetchone(),
                             (75, 15))

    def test_saved_capital_converts_only_reserve_once_and_preserves_experience(self):
        for _ in range(3):
            migrate_capital_archers(self.db)
        self.assertEqual(self.count(ARCHER_NAME), 250000)
        self.assertEqual(self.count('Призрак'), 20000)
        self.assertEqual(self.count('Призрак', 'Other'), 1000)
        self.assertEqual(self.db.execute('SELECT experience FROM garrisons WHERE unit_name=?',
                                        (ARCHER_NAME,)).fetchone()[0], 3)
        self.db.execute('DELETE FROM garrisons WHERE unit_name=?', (ARCHER_NAME,))
        migrate_capital_archers(self.db)
        self.assertEqual(self.count('Призрак'), 20000)
        ensure_capital_archers(self.db.cursor(), 'Capital')
        self.assertEqual(self.count(ARCHER_NAME), 250000)
        self.assertEqual(self.count('Призрак'), 20000)

    def test_new_invasion_guard_never_consumes_its_marching_ghosts(self):
        ensure_archer_units(self.db)
        ensure_capital_archers(self.db.cursor(), 'Capital')
        migrate_capital_archers(self.db)
        ensure_capital_archers(self.db.cursor(), 'Capital')
        self.assertEqual(self.count('Призрак'), 270000)
        self.assertEqual(self.count(ARCHER_NAME), 250000)

    def test_captured_capital_garrison_is_not_converted(self):
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Capital'")
        migrate_capital_archers(self.db)
        self.assertEqual(self.count(ARCHER_NAME), 0)
        self.assertEqual(self.count('Призрак'), 270000)

    def test_actual_ai_leaves_archers_when_attacking_or_capturing_empty_city(self):
        tree = ast.parse((ROOT / 'ii.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AIController')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == '_undead_direct_attack')
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'ii.py', 'exec'), namespace)
        migrate_capital_archers(self.db)
        for defended in (False, True):
            with self.subTest(defended=defended):
                self.db.execute('''INSERT INTO garrisons(city_name,unit_name,unit_count,unit_image)
                    VALUES ('Capital','Призрак',20000,'ghost.png') ON CONFLICT(city_name,unit_name)
                    DO UPDATE SET unit_count=20000''')
                combat = Mock(return_value={'winner': 'attacker', 'defending_losses': 0})
                host = SimpleNamespace(cursor=self.db.cursor(), db_connection=self.db, faction='Нежить',
                    get_unit_class=lambda _: 1,
                    get_defending_army=lambda _: [dict(unit_name='Enemy', unit_count=1)] if defended else [])
                with patch.dict(sys.modules, {'fight': SimpleNamespace(fight=combat)}), contextlib.redirect_stdout(io.StringIO()):
                    namespace['_undead_direct_attack'](host, 'Capital', 'Other', 'Нейтрал')
                self.assertEqual(self.count(ARCHER_NAME), 250000)
                self.assertEqual(self.count(ARCHER_NAME, 'Other'), 0)
                if defended:
                    self.assertTrue(combat.called)
                    self.assertEqual([u['unit_name'] for u in combat.call_args.kwargs['attacking_army']], ['Призрак'])


class UndeadCapitalCombatTests(unittest.TestCase):
    def test_mixed_capital_battle_with_spirit_bonus_completes_and_keeps_report_message(self):
        from test_battle_ui import combat_namespace
        namespace = combat_namespace()
        db = sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript('''
            CREATE TABLE user_faction(faction_name); INSERT INTO user_faction VALUES ('Север');
            CREATE TABLE turn(turn_count); INSERT INTO turn VALUES (49);
            CREATE TABLE faction_victories(faction,defeated,turn);
            INSERT INTO faction_victories VALUES ('Север','Вампиры',48),('Север','Эльфы',47);
            CREATE TABLE cities(name PRIMARY KEY,faction,is_undead);
            INSERT INTO cities VALUES ('Capital','Нежить',1);
            CREATE TABLE undead_invasion(id,capital_city); INSERT INTO undead_invasion VALUES (1,'Capital');
            CREATE TABLE garrisons(city_name,unit_name,unit_count,experience);
            CREATE TABLE buildings(city_name,building_type,count);
        ''')
        namespace['update_results_table'] = lambda **kw: None
        namespace['update_garrisons_after_battle'] = lambda **kw: None
        namespace['cleanup_equipment_after_battle'] = lambda *a: None
        namespace['generate_battle_report'] = lambda *a, **kw: []
        namespace['show_battle_animation'] = lambda *a, **kw: kw['callback']()
        report = Mock()
        namespace['show_battle_report'] = report
        def unit(name, count, unit_class=1):
            return dict(unit_name=name, unit_count=count, units_stats={
                'Урон': 100, 'Защита': 100, 'Живучесть': 15, 'Класс юнита': unit_class})
        defenders = [unit(ARCHER_NAME, 100), unit('Зомби', 30), unit('Моргана', 1, 2)]
        with patch('kivy.clock.Clock.schedule_once', side_effect=lambda cb, *a: cb(0)), contextlib.redirect_stdout(io.StringIO()):
            result = namespace['fight']('Source', 'Capital', defenders, [unit('Воин', 1000)], 'Север', 'Нежить', db)
        self.assertGreater(result['rounds'], 0)
        self.assertTrue(report.called)
        self.assertTrue(any('Боевой дух!' in message for message in report.call_args.kwargs['bonus_messages']))
