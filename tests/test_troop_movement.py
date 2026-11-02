import math
import sqlite3
import sys
import unittest
from collections import defaultdict
from types import MethodType, SimpleNamespace
from unittest.mock import patch, Mock

from strategy_ui_fixture import *
from test_allied_movement import city_methods
from map_atmosphere import MapAtmosphere
from map_roads import TransportNetwork
from troop_movement import MarchRoute, rendered_route
from utils.movement_rules import army_size_level, movement_city_route


class MarchTests(unittest.TestCase):
    def setUp(self):
        self.layer = MapAtmosphere()
        self.layer.configure((0, 0), 1)

    def tearDown(self):
        self.layer.marches.cancel_all()
        self.layer.stop()

    def test_visible_route_stitches_bridge_and_ferry_runs_in_both_directions(self):
        network = TransportNetwork(land=[(1, 2, [(0, 0), (10, 0)]),
                                           (1, 2, [(30, 0), (40, 10)]),
                                           (2, 3, [(40, 10), (50, 20)])],
                                   bridges=[(1, 2, [(10, 0), (20, 0)])],
                                   sea=[(1, 2, [(20, 0), (30, 0)])])
        centers = {1: (0, 0), 2: (40, 10), 3: (50, 20)}
        forward = rendered_route(network, [1, 2, 3], centers)
        reverse = rendered_route(network, [3, 2, 1], centers)
        self.assertEqual(forward.points, list(reversed(reverse.points)))
        self.assertEqual(forward.land, list(reversed(reverse.land)))
        self.assertIn(False, forward.land)
        self.assertEqual(forward.sample(0)[:2], centers[1])
        self.assertEqual(forward.sample(1)[:2], centers[3])

    def test_dust_three_levels_reuses_pool_and_never_spawns_on_water(self):
        route = MarchRoute([(100, 300), (250, 350), (500, 300)], [True, True])
        water = MarchRoute([(100, 200), (500, 200)], [False])
        self.layer.marches.play_batch([(lambda: route, level, 'Север', 100 * level)
                                      for level in (1, 2, 3)] + [(lambda: water, 3, 'Эльфы', 100)],
                                     lambda: None, lambda: None)
        marches = self.layer.marches.marches
        ids = [[id(p['shape']) for p in march.dust] for march in marches]
        for _ in range(25):
            self.layer.update(1 / 30)
        active = [sum(p['age'] < p['life'] for p in march.dust) for march in marches]
        self.assertLess(active[0], active[1])
        self.assertLess(active[1], active[2])
        self.assertEqual(active[3], 0)
        self.assertEqual(ids, [[id(p['shape']) for p in march.dust] for march in marches])
        self.assertEqual([army_size_level(100, n) for n in (30, 70, 71)], [1, 2, 3])

    def test_hero_flag_waves_follows_march_on_water_and_disappears_at_arrival(self):
        route=MarchRoute([(100,100),(500,100)],[False])
        self.layer.marches.play_batch([(lambda:route,1,'Север',1,True)],lambda:None,lambda:None)
        march=self.layer.marches.marches[0]
        self.layer.update(.2)
        flag=march.hero_flag
        first=list(flag.cloth.vertices)
        position=march.marker.pos
        self.layer.update(.2)
        self.assertNotEqual(first,flag.cloth.vertices)
        self.assertNotEqual(position,march.marker.pos)
        self.assertTrue(all(c.a>0 for c,_ in flag.colors))
        self.assertEqual(sum(p['age']<p['life'] for p in march.dust),0)
        for _ in range(180):
            self.layer.update(1/30)
        self.assertTrue(march.arrived)
        self.assertTrue(all(c.a==0 for c,_ in flag.colors))

    def test_end_turn_is_blocked_while_a_march_is_pending(self):
        import ast
        tree = ast.parse((ROOT / 'game_process.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GameScreen')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'process_turn')
        namespace = {}
        exec(compile(ast.Module(body=[method], type_ignores=[]), 'game_process.py', 'exec'), namespace)
        screen = SimpleNamespace(_troop_movement_busy=True, turn_counter=9)
        namespace['process_turn'](screen)
        self.assertEqual(screen.turn_counter, 9)


class MovementArrivalTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
            CREATE TABLE cities(id INTEGER, name TEXT, faction TEXT, coordinates TEXT);
            INSERT INTO cities VALUES(1,'A','Север','[100,300]'),(2,'B','Север','[300,300]'),(3,'C','Север','[500,300]');
            CREATE TABLE roads(city1 INTEGER, city2 INTEGER);
            INSERT INTO roads VALUES(1,2),(2,3);
            CREATE TABLE diplomacies(faction1 TEXT,faction2 TEXT,relationship TEXT);
            CREATE TABLE units(unit_name TEXT,faction TEXT,consumption REAL);
            INSERT INTO units VALUES('Страж','Север',1);
            CREATE TABLE garrisons(city_name TEXT,unit_name TEXT,unit_count INTEGER,unit_image TEXT,
                                   UNIQUE(city_name,unit_name));
            INSERT INTO garrisons VALUES('A','Страж',100,'');
            CREATE TABLE turn_check_move(faction TEXT,can_move INTEGER,moves_left INTEGER);
            INSERT INTO turn_check_move VALUES('Север',1,1);
        ''')
        self.layer = MapAtmosphere()
        self.layer.configure((0, 0), 1)
        self.network = TransportNetwork(land=[(1, 2, [(138.5, 330), (230, 350), (338.5, 330)]),
                                             (2, 3, [(338.5, 330), (430, 310), (538.5, 330)])])
        self.map = SimpleNamespace(_map_atmosphere=self.layer, map_scale=1, map_pos=(0, 0),
                                   _road_geometry=self.network)
        self.screen = SimpleNamespace(conn=self.db, end_turn_button=SimpleNamespace(disabled=False))
        self.screen.parent = SimpleNamespace(children=[self.map, self.screen])
        self.module_patch = patch.dict(sys.modules, game_process=SimpleNamespace(_active_game_screen=self.screen))
        self.module_patch.start()
        self.errors = []
        methods = city_methods('move_selected_group_to_city', 'transfer_troops_between_cities', 'move_troops',
                               show_popup_message=lambda *args: self.errors.append(args), refresh_map=lambda: None)
        self.owner = SimpleNamespace(conn=self.db, city_name='C', player_fraction='Север', current_popup=None,
            selected_group=[dict(city_name='A', unit_name='Страж', unit_count=50)],
            get_relationship=lambda *_: '', is_ally=lambda *_: False,
            get_city_owner=lambda name: self.db.execute('SELECT faction FROM cities WHERE name=?', (name,)).fetchone()[0],
            update_garrison=lambda: None,
            dismiss=lambda: None, close_current_popup=lambda: None)
        for name in ('move_selected_group_to_city', 'transfer_troops_between_cities', 'move_troops'):
            setattr(self.owner, name, MethodType(methods[name], self.owner))

    def tearDown(self):
        self.layer.marches.cancel_all()
        self.layer.stop()
        self.module_patch.stop()
        self.db.close()

    def count(self, city):
        row = self.db.execute('SELECT unit_count FROM garrisons WHERE city_name=?', (city,)).fetchone()
        return row[0] if row else 0

    def test_real_command_transfers_only_on_arrival_and_spends_one_move(self):
        selection=SimpleNamespace(dismiss=Mock())
        self.owner.current_popup=selection
        self.owner.dismiss=Mock()
        self.assertEqual(movement_city_route(self.db, 'A', 'C', 'Север'), [1, 2, 3])
        self.owner.move_selected_group_to_city()
        selection.dismiss.assert_called_once_with()
        self.owner.dismiss.assert_called_once_with()
        self.assertIsNone(self.owner.current_popup)
        self.assertFalse(self.errors)
        self.assertEqual((self.count('A'), self.count('C')), (100, 0))
        self.assertTrue(self.screen.end_turn_button.disabled)
        self.owner.move_selected_group_to_city()  # Repeated presses cannot enqueue another command.
        self.assertEqual(len(self.layer.marches.marches), 1)
        for _ in range(240):
            self.layer.update(1 / 30)
        self.assertFalse(self.errors)
        self.assertEqual((self.count('A'), self.count('C')), (50, 50))
        self.assertEqual(self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0], 0)
        self.assertFalse(self.screen.end_turn_button.disabled)
        self.assertFalse(self.screen._troop_movement_busy)
        self.assertEqual(self.layer.marches.marches, [])

    def test_flag_depends_on_selected_troops_and_ai_queue_remembers_hero_after_transfer(self):
        from troop_movement import queue_ai_march,play_ai_marches
        self.db.execute("ALTER TABLE units ADD COLUMN unit_class TEXT DEFAULT '1'")
        self.db.execute("INSERT INTO units VALUES('Герой','Север',1,'2')")
        self.db.execute("INSERT INTO garrisons VALUES('A','Герой',1,'')")
        self.owner.move_selected_group_to_city()
        self.assertIsNone(self.layer.marches.marches[0].hero_flag)
        self.layer.marches.cancel_all()
        self.owner.selected_group=[dict(city_name='A',unit_name='Герой',unit_count=1)]
        self.owner.move_selected_group_to_city()
        self.assertIsNotNone(self.layer.marches.marches[0].hero_flag)
        self.layer.marches.cancel_all()
        queue_ai_march(self.db,'Север','A','C',[dict(unit_name='Страж',unit_count=10)])
        queue_ai_march(self.db,'Север','A','C',[dict(unit_name='Герой',unit_count=1)])
        self.db.execute("DELETE FROM garrisons WHERE unit_name='Герой'")
        play_ai_marches(self.screen)
        self.assertEqual(len(self.layer.marches.marches),1)
        self.assertIsNotNone(self.layer.marches.marches[0].hero_flag)

    def test_rejected_command_keeps_city_and_selection_open(self):
        selection=SimpleNamespace(dismiss=Mock())
        self.owner.current_popup=selection
        self.owner.dismiss=Mock()
        self.owner.selected_group[0]['unit_count']=101
        self.owner.move_selected_group_to_city()
        self.assertTrue(self.errors)
        selection.dismiss.assert_not_called()
        self.owner.dismiss.assert_not_called()
        self.assertEqual(self.count('A'),100)

    def test_cancel_before_arrival_leaves_garrisons_and_move_counter_intact(self):
        self.owner.move_selected_group_to_city()
        self.layer.update(.1)
        self.layer.marches.cancel_all()
        self.assertEqual((self.count('A'), self.count('C')), (100, 0))
        self.assertEqual(self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0], 1)
        self.assertFalse(self.screen.end_turn_button.disabled)
        self.assertFalse(self.screen._troop_movement_busy)

    def test_attack_starts_only_after_the_march_reaches_enemy_city(self):
        self.db.execute("UPDATE cities SET faction='Вампиры' WHERE name='C'")
        self.db.execute("UPDATE garrisons SET city_name='B'")
        self.owner.selected_group[0]['city_name'] = 'B'
        self.owner.get_relationship = lambda *_: 'война'
        battles = []
        self.owner.start_battle_group = lambda *args: battles.append(args)
        self.owner.move_selected_group_to_city()
        self.assertEqual(battles, [])
        for _ in range(180):
            self.layer.update(1 / 30)
        self.assertFalse(self.errors)
        self.assertEqual(len(battles), 1)
        self.assertEqual(battles[0][:2], ('B', 'C'))

    def test_resize_reprojects_onto_the_updated_road_without_resetting_progress(self):
        self.owner.move_selected_group_to_city()
        for _ in range(15):
            self.layer.update(1 / 30)
        march = self.layer.marches.marches[0]
        age = march.age
        self.map.map_scale, self.map.map_pos = .5, (20, 40)
        self.layer.configure((20, 40), .5)
        self.map._road_geometry = TransportNetwork(land=[
            (a, b, [(x * .5 + 20, y * .5 + 40) for x, y in points])
            for a, b, points in self.network.land])
        self.layer.update(1 / 30)
        self.assertGreater(march.age, age)
        self.assertEqual(march.route.points[0], (138.5 * .5 + 20, 330 * .5 + 40))

    def test_route_uses_an_available_visible_detour(self):
        self.db.execute("INSERT INTO cities VALUES(4,'D','Север','[300,450]')")
        self.db.executemany('INSERT INTO roads VALUES(?,?)', [(1, 4), (4, 3)])
        route = movement_city_route(self.db, 'A', 'C', 'Север', {(1, 4), (3, 4)})
        self.assertEqual(route, [1, 4, 3])

    def test_arrival_rechecks_available_troops_before_consuming_a_move(self):
        self.owner.move_selected_group_to_city()
        self.db.execute("UPDATE garrisons SET unit_count=10 WHERE city_name='A'")
        for _ in range(240):
            self.layer.update(1 / 30)
        self.assertTrue(self.errors)
        self.assertEqual((self.count('A'), self.count('C')), (10, 0))
        self.assertEqual(self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0], 1)
        self.assertFalse(self.screen._troop_movement_busy)
