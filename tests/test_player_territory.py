"""Player territory visibility and pulse regression checks in a hidden window."""
import os
os.environ['KIVY_NO_ARGS'] = '1'
os.environ['KIVY_NO_CONFIG'] = '1'
os.environ['KIVY_NO_FILELOG'] = '1'
# A hidden SDL window may report zero DPI; keep test widget metrics valid.
os.environ['KIVY_METRICS_DENSITY'] = '1'
os.environ['KIVY_METRICS_FONTSCALE'] = '1'

import ast
import math
import sqlite3
import unittest
from pathlib import Path
from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color, Rectangle, Line, Mesh, Fbo, ClearColor, ClearBuffers
from kivy.uix.widget import Widget


def territory_host():
    tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MapWidget')
    names = ('draw_territories', '_start_player_pulse', '_compute_voronoi_cells',
             '_clip_polygon_by_halfplane', '_triangulate_polygon')
    methods = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name in names]
    namespace = dict(ast=ast, math=math, sqlite3=sqlite3, Clock=Clock,
                     Color=Color, Line=Line, Mesh=Mesh)
    exec(compile(ast.Module(body=methods, type_ignores=[]), 'main.py', 'exec'), namespace)
    host_type = type('TerritoryHost', (Widget,), {n.name: namespace[n.name] for n in methods})
    host = host_type(size=(1200, 800), size_hint=(None, None))
    host.conn = sqlite3.connect(':memory:')
    host.conn.executescript('''
        CREATE TABLE cities(id INTEGER, name TEXT, faction TEXT, coordinates TEXT);
        INSERT INTO cities VALUES(1, 'neutral', 'Нейтрал', '[230, 330]');
        INSERT INTO cities VALUES(2, 'player', 'Север', '[560, 330]');
        INSERT INTO cities VALUES(3, 'enemy', 'Эльфы', '[890, 330]');
    ''')
    host.current_player_kingdom = 'Север'
    host.map_pos, host.map_scale = (0, 0), 1
    host.base_map_width, host.base_map_height = 1200, 800
    host._territory_geometry_key = host._territory_geometry = None
    host._player_pulse_event = None
    host._player_pulse_phase = 0
    host._player_territory_colors = []
    with host.canvas:
        Color(1, 1, 1, 1)
        Rectangle(texture=CoreImage('files/map/generate/map_2.png').texture,
                  pos=(0, 0), size=(1200, 800))
    host.draw_territories()
    return host


class PlayerTerritoryTests(unittest.TestCase):
    def setUp(self):
        self.host = territory_host()

    def tearDown(self):
        self.host._player_pulse_event.cancel()
        self.host.conn.close()

    def test_fill_has_visible_range_and_border_never_disappears(self):
        colors = self.host._player_territory_colors
        self.assertAlmostEqual(colors[0][0].a, 0.30)
        callback = self.host._player_pulse_event.get_callback()
        callback(1.4)
        self.assertAlmostEqual(colors[0][0].a, 0.105)
        for color, low, high in colors:
            if high == 0.95:
                self.assertGreaterEqual(color.a, 0.74)
        callback(1.4)
        self.assertAlmostEqual(colors[0][0].a, 0.30)

    def test_animation_preserves_geometry_and_phase_on_rebuild(self):
        callback = self.host._player_pulse_event.get_callback()
        geometry = tuple(self.host.canvas.children)
        for frame in range(120):
            callback(1 / 30)
        self.assertEqual(geometry, tuple(self.host.canvas.children))
        phase = self.host._player_pulse_phase
        self.host.draw_territories()
        self.assertAlmostEqual(self.host._player_pulse_phase, phase)

    def test_gpu_pixels_change_inside_player_territory_only(self):
        fbo = Fbo(size=(1200, 800))
        with fbo:
            ClearColor(0, 0, 0, 1)
            ClearBuffers()
        fbo.add(self.host.canvas)
        try:
            fbo.draw()
            bright = bytes(fbo.pixels)
            self.host._player_pulse_event.get_callback()(1.4)
            fbo.ask_update()
            fbo.draw()
            dim = bytes(fbo.pixels)
            def difference(x, y):
                offset = (y * 1200 + x) * 4
                return sum(abs(bright[offset + c] - dim[offset + c]) for c in range(3))
            self.assertGreater(difference(600, 400), 20)
            self.assertEqual(difference(150, 400), 0)
            self.assertEqual(difference(1000, 400), 0)
        finally:
            fbo.remove(self.host.canvas)


if __name__ == '__main__':
    unittest.main()
