"""Distance eligibility, excessive detours and generator/render agreement."""
import ast
import contextlib
import io
from pathlib import Path
import random
import sqlite3
from types import SimpleNamespace
import unittest

from map_roads import build_transport_network
from utils.movement_rules import cities_in_range, filter_city_links, route_length


def extract_function(filename, name, namespace):
    tree = ast.parse(Path(filename).read_text(encoding='utf-8'))
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[function], type_ignores=[]), filename, 'exec'), namespace)
    return namespace[name]


class CityMovementRulesTests(unittest.TestCase):
    def test_manhattan_boundary_is_inclusive_and_not_euclidean(self):
        self.assertTrue(cities_in_range((0, 0), (140, 140)))
        self.assertFalse(cities_in_range((0, 0), (141, 140)))
        self.assertFalse(cities_in_range((0, 0), (200, 200)))
        self.assertFalse(cities_in_range((0, 0), (0, 0)))

    def test_link_eligibility_does_not_depend_on_screen_scale_or_origin(self):
        cities = {1: (100, 100), 2: (240, 240), 3: (300, 300)}
        for scale in (.6, 1, 1.8):
            projected = {key: (x * scale + 500, y * scale + 90) for key, (x, y) in cities.items()}
            self.assertEqual(filter_city_links(projected, [(1, 2), (1, 3)], scale), [(1, 2)])

    def test_stale_distant_connection_is_not_rendered(self):
        network = build_transport_network({1: (100, 100), 2: (381, 100)}, [(1, 2)], {}, (30, 30, 1170, 770))
        self.assertEqual(network.connections, 0)
        self.assertEqual(network.land + network.sea + network.bridges, [])

    def test_label_obstacle_cannot_force_a_long_loop(self):
        network = build_transport_network({1: (300, 300), 2: (520, 300)}, [(1, 2)],
                                          {3: (400, 170, 435, 490)}, (30, 30, 1170, 770))
        self.assertEqual(network.connections, 1)
        self.assertLessEqual(route_length(network.land[0][2]), 280)

    def test_impossible_short_route_is_omitted_instead_of_forced(self):
        cities = {1: (300, 300), 2: (540, 300)}
        cities.update({i + 3: (430, y) for i, y in enumerate((80, 160, 240, 320, 400, 480))})
        network = build_transport_network(cities, [(1, 2)], {}, (30, 30, 1170, 770))
        self.assertEqual(network.connections, 0)

    def test_generator_does_not_connect_distant_isolated_city(self):
        function = extract_function('generate_map.py', 'build_city_graph',
                                    {'MAX_NEIGHBOURS': 4})
        cities = [{'position': p, 'type': 'neutral'} for p in ((100, 100), (381, 100), (100, 300))]
        graph = function(cities)
        self.assertEqual(graph[1], [])
        self.assertIn(2, graph[0])
        self.assertTrue(all(cities_in_range(cities[a]['position'], cities[b]['position'])
                            for a, neighbors in graph.items() for b in neighbors))

    def test_database_writer_rejects_out_of_range_edges(self):
        function = extract_function('generate_map.py', 'save_to_database',
                                    dict(sqlite3=sqlite3, random=random.Random(1), UNDEAD_CITIES=0))
        db = sqlite3.connect(':memory:')
        try:
            db.executescript('''
                CREATE TABLE cities(id, name, coordinates, faction, icon_coordinates,
                                    label_coordinates, color_faction, is_undead, kf_crystal);
                CREATE TABLE roads(id, city1, city2);
            ''')
            cities = [{'position': p, 'name': str(i), 'faction': None, 'color_faction': '#aaa'}
                      for i, p in enumerate(((100, 100), (381, 100), (100, 300)))]
            with contextlib.redirect_stdout(io.StringIO()):
                function(db, cities, {0: [0, 1, 2], 1: [0], 2: [0]})
            self.assertEqual(db.execute('SELECT city1,city2 FROM roads').fetchall(), [(1, 3)])
        finally:
            db.close()

    def test_ai_range_check_accepts_exactly_280(self):
        function = extract_function('ai_strategy.py', '_find_closest_own_city_in_range',
                                    dict(sqlite3=sqlite3, MAX_MOVE_DISTANCE=280))
        db = sqlite3.connect(':memory:')
        try:
            db.executescript('''
                CREATE TABLE cities(name, coordinates, faction);
                INSERT INTO cities VALUES('target', '[380, 100]', 'enemy');
                INSERT INTO cities VALUES('ours', '[100, 100]', 'player');
            ''')
            ai = SimpleNamespace(cursor=db.cursor(), faction='player')
            self.assertEqual(function(ai, 'target'), 'ours')
            db.execute("UPDATE cities SET coordinates='[381, 100]' WHERE name='target'")
            self.assertIsNone(function(ai, 'target'))
        finally:
            db.close()


if __name__ == '__main__':
    unittest.main()
