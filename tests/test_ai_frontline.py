import ast
from pathlib import Path
import sqlite3
from types import MethodType, SimpleNamespace
import unittest

from utils.ai_frontline import choose_frontier, rally_frontier, prepare_border_war


class FrontierTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript('''
            CREATE TABLE cities(id,name,faction,coordinates);
            INSERT INTO cities VALUES(1,'A','Адепты','[0,0]'),(2,'B','Адепты','[100,0]'),
                (3,'C','Адепты','[200,0]'),(4,'V','Вампиры','[300,0]'),
                (5,'N','Север','[-100,0]'),(6,'Island','Адепты','[0,500]');
            CREATE TABLE roads(city1,city2);
            INSERT INTO roads VALUES(1,2),(2,3),(3,4),(1,5);
            CREATE TABLE diplomacies(faction1,faction2,relationship);
            CREATE TABLE units(unit_name,unit_class,faction);
            INSERT INTO units VALUES('soldier','1','Адепты'),('hero','2','Адепты'),('guardian','4','Адепты');
            CREATE TABLE garrisons(city_name,unit_name,unit_count,unit_image,UNIQUE(city_name,unit_name));
            INSERT INTO garrisons VALUES('A','soldier',100,''),('B','hero',1,''),
                ('A','guardian',1,''),('Island','soldier',10,'');
        ''')
        self.relations = {'Вампиры': '0', 'Север': '0', 'Нейтрал': '-100'}
        self.strengths = {'Вампиры': 100, 'Север': 200, 'Адепты': 1000}
        self.ai = SimpleNamespace(db_connection=self.db, cursor=self.db.cursor(), faction='Адепты', turn=10,
                                  load_relations=lambda: self.relations,
                                  calculate_army_strength=lambda: self.strengths)
        tree = ast.parse(Path('ii.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AIController')
        names = {'relocate_units', 'get_city_owner', 'has_road_between_cities', 'has_own_territory_path'}
        methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
        namespace = dict(sqlite3=sqlite3)
        exec(compile(ast.Module(body=methods, type_ignores=[]), 'ii.py', 'exec'), namespace)
        for name in names:
            setattr(self.ai, name, MethodType(namespace[name], self.ai))

    def plan(self):
        return choose_frontier(self.db, 'Адепты', self.relations, self.strengths)

    def test_worst_relations_then_weakest_army_select_the_shared_border(self):
        self.assertEqual((self.plan().faction, self.plan().city), ('Вампиры', 'C'))
        self.relations['Север'] = -1
        self.assertEqual((self.plan().faction, self.plan().city), ('Север', 'A'))

    def test_reverse_alliance_and_extinct_factions_are_excluded(self):
        self.db.execute("INSERT INTO diplomacies VALUES('Вампиры','Адепты','союз')")
        self.relations['Уничтоженная'] = -999
        self.assertEqual(self.plan().faction, 'Север')

    def test_rally_keeps_heroes_with_troops_and_does_not_teleport_island_units(self):
        self.assertEqual(rally_frontier(self.ai).city, 'C')
        rows = set(self.db.execute('SELECT city_name,unit_name,unit_count FROM garrisons'))
        self.assertEqual(rows, {('C', 'soldier', 100), ('C', 'hero', 1),
                                ('Island', 'soldier', 10), ('A', 'guardian', 1)})
        rally_frontier(self.ai)
        self.assertEqual(rows, set(self.db.execute('SELECT city_name,unit_name,unit_count FROM garrisons')))

    def test_war_requires_a_preparation_turn_and_live_soldiers_on_the_border(self):
        self.assertFalse(prepare_border_war(self.ai, 'Вампиры'))
        self.assertFalse(prepare_border_war(self.ai, 'Вампиры'))
        self.ai.turn += 1
        self.assertTrue(prepare_border_war(self.ai, 'Вампиры'))
        self.db.execute("DELETE FROM garrisons WHERE unit_name='soldier'")
        self.assertFalse(prepare_border_war(self.ai, 'Вампиры'))

    def test_no_shared_road_prevents_declaration(self):
        self.db.execute('DELETE FROM roads WHERE city2=4')
        self.assertFalse(prepare_border_war(self.ai, 'Вампиры'))
        self.ai.turn += 1
        self.assertFalse(prepare_border_war(self.ai, 'Вампиры'))


if __name__ == '__main__':
    unittest.main()
