"""Run with: py -3.12 -m unittest discover -s tests -v (hidden SDL window)."""
import os
os.environ['KIVY_NO_ARGS'] = '1'
os.environ['KIVY_NO_CONFIG'] = '1'
os.environ['KIVY_NO_FILELOG'] = '1'
# A hidden SDL window may report zero DPI; keep test widget metrics valid.
os.environ['KIVY_METRICS_DENSITY'] = '1'
os.environ['KIVY_METRICS_FONTSCALE'] = '1'

import unittest
import ast
import sqlite3
from pathlib import Path
from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
Config.set('graphics', 'width', '1200')
Config.set('graphics', 'height', '800')

from kivy.core.window import Window
from kivy.clock import Clock
from kivy.graphics import ClearColor, ClearBuffers, Color, Fbo, Rectangle
from kivy.uix.widget import Widget
from map_atmosphere import MapAtmosphere, plague_routes, stream_point


class InfectionRulesTests(unittest.TestCase):
    def test_only_recorded_losses_within_real_plague_radius_get_routes(self):
        effects = [('near', 30, 120, 0), ('edge', 4, 200, 0),
                   ('outside', 10, 201, 0), ('no-loss', 0, 50, 0)]
        routes = plague_routes(effects, [('undead', 0, 0)])
        self.assertEqual([row[1] for row in routes], ['near', 'edge'])

    def test_nearest_actual_source_and_no_self_infection(self):
        routes = plague_routes([('target', 9, 100, 0)],
                               [('far', -50, 0), ('near', 95, 0)])
        self.assertEqual(routes[0][0], 'near')
        self.assertEqual(plague_routes([('target', 9, 0, 0)], []), [])
        self.assertEqual(plague_routes([('target', 9, 100, 0)],
                                       [('near', 95, 0), ('target', 100, 0)]), [])

    def test_stream_reaches_both_city_centers(self):
        self.assertEqual(stream_point((10, 20), (100, 80), 0), (10, 20))
        x, y = stream_point((10, 20), (100, 80), 1)
        self.assertAlmostEqual(x, 100)
        self.assertAlmostEqual(y, 80)


class AtmosphereGraphicsTests(unittest.TestCase):
    def setUp(self):
        self.layer = MapAtmosphere()
        self.layer.configure((80, 60), 0.8)

    def tearDown(self):
        self.layer.stop()

    def test_weather_reuses_instructions_through_all_seasons(self):
        for season in ('Зима', 'Весна', 'Лето', 'Осень'):
            self.layer.set_season(season)
            before = tuple(self.layer._weather_group.children)
            for frame in range(150):
                self.layer.update(1 / 30)
            self.assertEqual(before, tuple(self.layer._weather_group.children))

    def test_storms_are_bounded_and_disappear_when_city_is_removed(self):
        self.layer.set_storms([(400, 400, False), (600, 500, True)])
        for frame in range(1800):
            self.layer.update(1 / 30)
            self.assertLessEqual(sum(len(s['bolts']) for s in self.layer._storms), 2)
        self.layer.set_storms([])
        self.assertEqual(self.layer._storms, [])
        self.assertEqual(len(self.layer._storm_group.children), 0)

    def test_plague_report_does_not_replay_on_resize_or_unchanged_refresh(self):
        effects = [('source', 0, 200, 200), ('target', 12, 300, 200)]
        sources = [('source', 200, 200)]
        self.layer.set_plague(effects, sources)
        self.assertEqual(len(self.layer._outbreaks), 1)
        outbreak = self.layer._outbreaks[0]
        self.layer.set_plague(effects, sources)
        self.assertIs(self.layer._outbreaks[0], outbreak)
        self.layer.configure((60, 40), 0.7)
        self.layer.set_plague(effects, sources)
        self.assertEqual(self.layer._outbreaks, [])
        self.layer.set_plague([effects[0], ('target', 15, 300, 200)], sources)
        self.assertEqual(len(self.layer._outbreaks), 1)
        self.layer.set_plague([], [], active=False)
        self.assertEqual(self.layer._streams, [])
        self.assertEqual(self.layer._fog, [])

    def test_plague_particles_reuse_graphics_and_finish_outbreak(self):
        self.layer.set_plague([('source', 0, 200, 200), ('target', 12, 300, 200)],
                              [('source', 200, 200)])
        before = tuple(self.layer._plague_group.children)
        for frame in range(1200):
            self.layer.update(1 / 30)
        self.assertEqual(before, tuple(self.layer._plague_group.children))
        self.assertEqual(self.layer._outbreaks[0]['color'].a, 0)
        self.assertEqual(self.layer._outbreaks[0]['text_color'].a, 0)

    def test_single_timer_and_touch_passthrough(self):
        self.layer.start()
        event = self.layer._event
        self.layer.start()
        self.assertIs(event, self.layer._event)
        self.layer.stop()
        self.assertIsNone(self.layer._event)
        self.assertFalse(self.layer.on_touch_down(object()))
        self.assertFalse(self.layer.on_touch_move(object()))
        self.assertFalse(self.layer.on_touch_up(object()))

    def test_stencil_prevents_weather_outside_map(self):
        # Intentionally draw far beyond the map; the real GPU stencil must clip it.
        self.layer._weather_group.add(Color(1, 0, 0, 1))
        self.layer._weather_group.add(Rectangle(pos=(0, 0), size=(1200, 800)))
        fbo = Fbo(size=(1200, 800), with_stencilbuffer=True)
        with fbo:
            ClearColor(0, 0, 0, 1)
            ClearBuffers()
        fbo.add(self.layer.canvas)
        try:
            fbo.draw()
            pixels = fbo.pixels
            def pixel(x, y):
                offset = (y * 1200 + x) * 4
                return tuple(pixels[offset:offset + 3])
            self.assertEqual(pixel(20, 20), (0, 0, 0))
            self.assertEqual(pixel(500, 400), (255, 0, 0))
            self.assertEqual(pixel(1150, 750), (0, 0, 0))
        finally:
            fbo.remove(self.layer.canvas)


class MapIntegrationTests(unittest.TestCase):
    """Exercise the real integration methods against an isolated SQLite database."""

    def setUp(self):
        # Import only these methods: importing main would open the game's database.
        tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
        map_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'MapWidget')
        methods = [node for node in map_class.body if isinstance(node, ast.FunctionDef)
                   and node.name in ('_read_map_snapshot', '_sync_map_atmosphere')]
        namespace = {'ast': ast, 'sqlite3': sqlite3, 'Window': Window, 'Clock': Clock}
        exec(compile(ast.Module(body=methods, type_ignores=[]), 'main.py', 'exec'), namespace)
        host_type = type('MapHost', (Widget,), {node.name: namespace[node.name] for node in methods})
        self.host = host_type()
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
            CREATE TABLE cities(id INTEGER, name TEXT, faction TEXT, coordinates TEXT,
                                is_undead INTEGER, icon_coordinates TEXT);
            CREATE TABLE roads(id INTEGER, city1 INTEGER, city2 INTEGER);
            CREATE TABLE undead_invasion(id INTEGER, invasion_started INTEGER, capital_city TEXT);
            CREATE TABLE season(id INTEGER, current_season TEXT);
            CREATE TABLE plague_effects(city_name TEXT, losses INTEGER, coord_x REAL, coord_y REAL);
            INSERT INTO cities VALUES(1, 'source', 'Нежить', '[200, 200]', 1, '[]');
            INSERT INTO cities VALUES(2, 'target', 'Север', '[300, 200]', 0, '[]');
            INSERT INTO undead_invasion VALUES(1, 1, 'source');
            INSERT INTO season VALUES(1, 'Лето');
            INSERT INTO plague_effects VALUES('source', 0, 200, 200);
            INSERT INTO plague_effects VALUES('target', 15, 300, 200);
        ''')
        self.host.conn = self.db
        self.host._map_atmosphere = None
        self.host.map_pos, self.host.map_scale = (0, 0), 1
        self.host.base_map_width, self.host.base_map_height = 1200, 800
        self.host.current_player_kingdom = 'Север'
        self.host.random_map_source = 'test.png'
        self.host._undead_shield_data = [(238.5, 238.5, True)]

    def tearDown(self):
        if self.host._map_atmosphere:
            self.host._map_atmosphere.stop()
        self.db.close()

    def test_season_invalidates_snapshot_but_icon_position_write_does_not(self):
        before = self.host._read_map_snapshot()
        self.db.execute("UPDATE cities SET icon_coordinates = '[10, 20]'")
        self.assertEqual(before, self.host._read_map_snapshot())
        self.db.execute("UPDATE season SET current_season = 'Зима'")
        self.assertNotEqual(before, self.host._read_map_snapshot())

    def test_layer_survives_map_rebuild_and_stops_plague_after_invasion(self):
        self.host._sync_map_atmosphere()
        layer = self.host._map_atmosphere
        self.assertEqual(len(layer._streams), 7)
        self.assertEqual(len(layer._storms), 1)
        self.host.clear_widgets()
        self.assertIsNone(layer._event)
        self.host._sync_map_atmosphere()
        self.assertIs(layer, self.host._map_atmosphere)
        self.assertIs(layer.parent, self.host)
        self.db.execute('UPDATE undead_invasion SET invasion_started = 2')
        self.host._sync_map_atmosphere()
        self.assertEqual(layer._streams, [])
        self.assertEqual(layer._fog, [])

    def test_captured_source_no_longer_sends_infection(self):
        self.host._sync_map_atmosphere()
        self.db.execute("UPDATE cities SET faction = 'Север' WHERE name = 'source'")
        self.host._sync_map_atmosphere()
        self.assertEqual(self.host._map_atmosphere._streams, [])

    def test_stale_loss_report_does_not_infect_a_now_neutral_city(self):
        self.host._sync_map_atmosphere()
        self.db.execute("UPDATE cities SET faction = 'Нейтрал' WHERE name = 'target'")
        self.host._sync_map_atmosphere()
        self.assertEqual(self.host._map_atmosphere._streams, [])


if __name__ == '__main__':
    unittest.main()
