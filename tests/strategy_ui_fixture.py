"""Real UI classes extracted without importing modules that open the player's DB."""
import ast
import os
import sqlite3
from pathlib import Path
from types import SimpleNamespace

os.environ.update(KIVY_NO_ARGS='1', KIVY_NO_CONFIG='1', KIVY_NO_FILELOG='1',
                  KIVY_METRICS_DENSITY='1', KIVY_METRICS_FONTSCALE='1')
from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line, Ellipse
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image, AsyncImage
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.screenmanager import Screen
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.widget import Widget
from utils.helpers import format_number, parse_formatted_number

ROOT = Path(__file__).resolve().parents[1]


def city_class():
    tree = ast.parse((ROOT / 'ui.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'FortressInfoPopup')
    namespace = dict(globals(), platform='android')
    exec(compile(ast.Module(body=[cls], type_ignores=[]), 'ui.py', 'exec'), namespace)
    return namespace['FortressInfoPopup']


def city_fixture(owner='Адепты', populated=False, undead=False):
    conn = sqlite3.connect(':memory:')
    conn.executescript('''
        CREATE TABLE cities(name TEXT, faction TEXT, coordinates TEXT, is_undead INTEGER);
        CREATE TABLE buildings(city_name TEXT, faction TEXT, building_type TEXT, count INTEGER);
        CREATE TABLE garrisons(city_name TEXT, unit_name TEXT, unit_count INTEGER, unit_image TEXT, experience INTEGER);
        CREATE TABLE units(unit_name TEXT, image_path TEXT, unit_class TEXT, attack REAL, defense REAL,
                           durability REAL, morale REAL, unit_type TEXT);
    ''')
    name = 'Некрополь' if undead else 'Виндгар'
    conn.execute('INSERT INTO cities VALUES (?, ?, ?, ?)', (name, owner, '[200, 300]', int(undead)))
    if not undead:
        conn.executemany('INSERT INTO buildings VALUES (?, ?, ?, ?)',
                         [(name, owner, kind, count) for kind, count in [('Больница', 12), ('Фабрика', 11), ('Стена', 2)]])
    if populated:
        conn.execute('INSERT INTO units VALUES (?, ?, ?, 145, 120, 240, 100, ?)',
                     ('Стражи рассвета', 'files/pict/hire/sword.png', '1', 'infantry'))
        conn.execute('INSERT INTO garrisons VALUES (?, ?, 4500, ?, 3)',
                     (name, 'Стражи рассвета', 'files/pict/hire/sword.png'))
    popup = city_class()(owner, (200, 300), 'Адепты', conn)
    return popup, conn


def hud_fixture():
    tree = ast.parse((ROOT / 'game_process.py').read_text(encoding='utf-8'))
    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)
               and n.name in ('ImageButton', 'ResourceBox', 'CircularProgressButton', 'TabImageButton')]
    game = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GameScreen')
    methods = [n for n in game.body if isinstance(n, ast.FunctionDef)
               and n.name in ('init_ui', 'activate_tab', 'deactivate_all_tabs', 'update_resource_box_position')]
    namespace = dict(globals(), platform='android', transform_filename=lambda path: 'files/sov/adept.jpg',
                     show_floating_bonus=lambda *args: None)
    exec(compile(ast.Module(body=classes + methods, type_ignores=[]), 'game_process.py', 'exec'), namespace)
    cls = type('HUDPreview', (Screen,), {method.name: namespace[method.name] for method in methods})
    host = cls()
    host.selected_faction = 'Адепты'
    host.is_android, host.turn_counter, host.tutorial_enabled = True, 10, False
    for name in ('show_advisor', 'switch_to_economy', 'switch_to_army', 'switch_to_politics',
                 'confirm_exit', 'on_season_pressed', 'process_turn', 'save_interface_element'):
        setattr(host, name, lambda *args: None)
    host.faction = SimpleNamespace(get_resources=lambda: {
        'Кроны': '861.0 тыс.', 'Рабочие': '15.4 тыс.', 'Кристаллы': '652.0 тыс.',
        'Население': '50.8 тыс.', 'Потребление': '54', 'Лимит Армии': '11.0 тыс.'})
    host.init_ui()
    host.season_icon.source = 'files/status/icons/sun.png'
    host.season_label.text = 'Лето'
    return host


def cleanup_hud(host):
    host.resource_box.cleanup()
    Window.unbind(on_resize=host._hud_fit)
    Window.unbind(on_resize=host.update_resource_box_position)
