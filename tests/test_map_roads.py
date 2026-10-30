"""Visual routing and rendering checks, without opening the game database."""
import os
os.environ['KIVY_NO_ARGS'] = '1'
os.environ['KIVY_NO_CONFIG'] = '1'
os.environ['KIVY_NO_FILELOG'] = '1'
# A hidden SDL window may report zero DPI; keep test widget metrics valid.
os.environ['KIVY_METRICS_DENSITY'] = '1'
os.environ['KIVY_METRICS_FONTSCALE'] = '1'
import ast
import sqlite3
import unittest
from pathlib import Path
from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle
from kivy.uix.widget import Widget
from map_roads import build_road_paths, segment_hits_rect


class RoadRoutingTests(unittest.TestCase):
    def setUp(self):
        self.cities = {1: (100, 300), 2: (550, 300), 3: (320, 300)}
        self.bounds = (30, 30, 1170, 770)

    def test_preserves_graph_deduplicates_and_is_deterministic(self):
        edges = [(2, 1), (1, 2), (3, 2), (1, 1), (1, 99)]
        paths = build_road_paths(self.cities, edges, {}, self.bounds)
        self.assertEqual([(a, b) for a, b, path in paths], [(1, 2), (2, 3)])
        self.assertEqual(paths, build_road_paths(self.cities, list(reversed(edges)), {}, self.bounds))

    def test_road_detours_around_intermediate_city_and_label(self):
        label = (290, 250, 440, 295)
        paths = build_road_paths(self.cities, [(1, 2)], {3: label}, self.bounds)
        self.assertEqual(len(paths), 1)
        points = paths[0][2]
        for a, b in zip(points, points[1:]):
            self.assertFalse(segment_hits_rect(a, b, (315, 296, 402, 382)))
            self.assertFalse(segment_hits_rect(a, b, label))
        self.assertTrue(all(30 <= x <= 1170 and 30 <= y <= 770 for x, y in points))

    def test_obstructed_map_keeps_existing_connection(self):
        paths = build_road_paths(self.cities, [(1, 2)], {3: (290, 0, 310, 800)}, self.bounds)
        self.assertEqual(len(paths), 1)

    def test_open_road_has_gentle_curve_and_reaches_beneath_city_sprites(self):
        paths = build_road_paths({1: (100, 300), 2: (550, 300)}, [(1, 2)], {}, self.bounds)
        points = paths[0][2]
        self.assertEqual(points[0], (138.5, 330))
        self.assertAlmostEqual(points[-1][0], 588.5)
        self.assertGreater(max(y for x, y in points) - min(y for x, y in points), 5)


class RoadLayerTests(unittest.TestCase):
    def test_redrawing_reuses_routes_and_preserves_other_canvas_layers(self):
        tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MapWidget')
        methods = [n for n in node.body if isinstance(n, ast.FunctionDef)
                   and n.name in ('draw_roads', '_get_city_label_texture')]
        namespace = dict(ast=ast, sqlite3=sqlite3, CoreLabel=CoreLabel)
        exec(compile(ast.Module(body=methods, type_ignores=[]), 'main.py', 'exec'), namespace)
        host_type = type('RoadHost', (Widget,), {n.name: namespace[n.name] for n in methods})
        host = host_type()
        host.conn = sqlite3.connect(':memory:')
        try:
            host.conn.executescript('''
                CREATE TABLE cities(id INTEGER, name TEXT, faction TEXT, coordinates TEXT);
                CREATE TABLE roads(id INTEGER, city1 INTEGER, city2 INTEGER);
                INSERT INTO cities VALUES(1, 'A', 'Север', '[100, 300]');
                INSERT INTO cities VALUES(2, 'B', 'Эльфы', '[550, 300]');
                INSERT INTO roads VALUES(1, 1, 2);
            ''')
            host.map_pos, host.map_scale = (0, 0), 1
            host.base_map_width, host.base_map_height = 1200, 800
            host._city_label_cache = {}
            host._road_geometry_key, host._road_group = None, None
            with host.canvas.after:
                sentinel = Rectangle(pos=(0, 0), size=(1, 1))
            host.draw_roads()
            old_geometry, old_group = host._road_geometry, host._road_group
            count = len(host.canvas.children)
            host.draw_roads()
            self.assertIs(old_geometry, host._road_geometry)
            self.assertNotIn(old_group, host.canvas.children)
            self.assertIn(host._road_group, host.canvas.children)
            self.assertEqual(len(host.canvas.children), count)
            self.assertIn(sentinel, host.canvas.after.children)
        finally:
            host.conn.close()


if __name__ == '__main__':
    unittest.main()
