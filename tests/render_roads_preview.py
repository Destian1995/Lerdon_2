"""Render the current city network read-only, without importing or starting main."""
import os
os.environ['KIVY_NO_ARGS'] = '1'
os.environ['KIVY_NO_CONFIG'] = '1'
os.environ['KIVY_NO_FILELOG'] = '1'
import ast
import math
import sqlite3
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
Config.set('graphics', 'width', '1200')
Config.set('graphics', 'height', '800')
from kivy.clock import Clock
from kivy.core.image import Image as CoreImage
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle, Line, Mesh
from kivy.uix.widget import Widget


def render():
    tree = ast.parse(Path('main.py').read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MapWidget')
    names = ('draw_roads', '_get_city_label_texture', 'draw_territories', '_start_player_pulse',
             '_compute_voronoi_cells', '_clip_polygon_by_halfplane', '_triangulate_polygon')
    methods = [n for n in node.body if isinstance(n, ast.FunctionDef) and n.name in names]
    namespace = dict(ast=ast, math=math, sqlite3=sqlite3, Clock=Clock, CoreLabel=CoreLabel,
                     Color=Color, Rectangle=Rectangle, Line=Line, Mesh=Mesh)
    exec(compile(ast.Module(body=methods, type_ignores=[]), 'main.py', 'exec'), namespace)
    host_type = type('RoadPreview', (Widget,), {n.name: namespace[n.name] for n in methods})
    host = host_type(size=(1200, 800), size_hint=(None, None))
    host.conn = sqlite3.connect(Path('game_data.db').resolve().as_uri() + '?mode=ro', uri=True)
    host.map_pos, host.map_scale = (0, 0), 1
    host.base_map_width, host.base_map_height = 1200, 800
    host.current_player_kingdom = 'Север'
    host._city_label_cache = {}
    host._territory_geometry_key = host._territory_geometry = None
    host._player_pulse_event = None
    host._player_pulse_phase = 0
    host._player_territory_colors = []
    host._road_geometry_key, host._road_group = None, None
    with host.canvas:
        Color(1, 1, 1, 1)
        Rectangle(texture=CoreImage('files/map/generate/map_6.png').texture,
                  pos=(0, 0), size=(1200, 800))
    host.draw_territories()
    started = time.perf_counter()
    host.draw_roads()
    print(f'Road build: {(time.perf_counter() - started) * 1000:.1f} ms; {len(host._road_geometry)} roads')
    images = {'Север': 'people.png', 'Эльфы': 'elfs.png', 'Вампиры': 'vampires.png',
              'Элины': 'poly.png', 'Адепты': 'adepts.png', 'Нежить': 'castle_death.png',
              'Мятежники': 'keig.png'}
    for name, faction, raw_coords, undead in host.conn.execute(
            'SELECT name, faction, coordinates, COALESCE(is_undead, 0) FROM cities'):
        x, y = ast.literal_eval(raw_coords)
        image = 'castle_death.png' if undead else images.get(faction, 'default.png')
        with host.canvas:
            Color(1, 1, 1, 1)
            Rectangle(texture=CoreImage('files/buildings/' + image).texture, pos=(x, y), size=(77, 77))
            texture = host._get_city_label_texture(f'{name}({faction})')
            tx, ty = x + (40 - texture.size[0]) / 2, y - texture.size[1] - 5
            Color(0, 0, 0, 0.9)
            for ox, oy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                Rectangle(texture=texture, pos=(tx + ox, ty + oy), size=texture.size)
            Color(1, 1, 1, 1)
            Rectangle(texture=texture, pos=(tx, ty), size=texture.size)
    host.export_to_png('assets/roads-preview.png')
    if host._player_pulse_event:
        host._player_pulse_event.cancel()
    host.conn.close()
    print(Path('assets/roads-preview.png').resolve())


if __name__ == '__main__':
    render()
