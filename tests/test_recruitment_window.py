"""Exercise the recruitment UI without importing the game or touching its database."""
import ast
import os
import sqlite3
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ['KIVY_NO_ARGS'] = '1'
os.environ['KIVY_NO_CONFIG'] = '1'
os.environ['KIVY_NO_FILELOG'] = '1'
os.environ['KIVY_METRICS_DENSITY'] = '1'
os.environ['KIVY_METRICS_FONTSCALE'] = '1'
from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
Config.set('graphics', 'width', '1200')
Config.set('graphics', 'height', '800')
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.carousel import Carousel
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import AsyncImage, Image
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy.utils import get_color_from_hex


class RecruitmentWindowTests(unittest.TestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / 'army.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                     and node.name in ('start_army_mode', 'load_unit_data')]
        self.hires = []
        namespace = dict(globals())
        namespace.update(
            ArmyCash=lambda faction, economy, conn: SimpleNamespace(class_faction=economy),
            format_number=str,
            broadcast_units=lambda *args: self.hires.append(args),
        )
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), 'exec'), namespace)
        self.conn = sqlite3.connect(':memory:')
        self.conn.execute('''CREATE TABLE units (
            unit_name, consumption, cost_money, cost_time, image_path,
            attack, defense, durability, unit_class, faction)''')
        self.conn.executemany('INSERT INTO units VALUES (?, 1, 10, 1, ?, 5, 4, 3, ?, ?)',
                              [(f'Unit {i}', '', f'{cls} класс', 'Север')
                               for i, cls in enumerate((1, 1, 2, 3, 4, 4))])
        self.area = FloatLayout()
        economy = SimpleNamespace(get_resource_now=lambda resource: 1000)
        namespace['start_army_mode']('Север', self.area, economy, self.conn)
        self.root = self.area.children[0]
        self.carousel = self.root.carousel

    def tearDown(self):
        self.area.clear_widgets()
        self.conn.close()

    def built_count(self):
        return sum(bool(slide.children) for slide in self.carousel.slides)

    def test_open_builds_only_first_card_and_uses_async_portrait(self):
        self.assertEqual(len(self.carousel.slides), 6)
        self.assertEqual(self.built_count(), 1)
        self.assertTrue(any(isinstance(w, AsyncImage)
                            for w in self.carousel.slides[0].walk()))

    def test_neighbors_warm_up_and_navigation_builds_current_card(self):
        for _ in range(3):
            time.sleep(0.11)
            Clock.tick()
        self.assertEqual(self.built_count(), 3)
        self.carousel.index = 3
        self.assertTrue(self.carousel.slides[3].children)

    def test_close_cancels_pending_card_build_and_blink(self):
        self.area.clear_widgets()
        time.sleep(0.12)
        Clock.tick()
        self.assertEqual(self.built_count(), 1)
        self.assertTrue(self.root.released)
        self.assertIsNone(self.root.warmup_event)
        self.assertIsNone(self.root.popup.parent)

    def test_recruit_quantity_belongs_to_its_own_card(self):
        self.carousel.index = 1
        first, second = self.carousel.slides[:2]
        first_input = next(w for w in first.walk() if isinstance(w, TextInput))
        second_input = next(w for w in second.walk() if isinstance(w, TextInput))
        first_input.text = '7'
        second_input.text = '3'
        for slide, name, quantity in ((first, 'Unit 0', '7'), (second, 'Unit 1', '3')):
            button = next(w for w in slide.walk()
                          if isinstance(w, Button) and w.text == 'НАНЯТЬ')
            button.dispatch('on_release')
            self.assertEqual(self.hires[-1][0], name)
            self.assertEqual(self.hires[-1][2].text, quantity)

    def test_insufficient_resources_disable_hiring(self):
        self.root.army_hire.class_faction.get_resource_now = lambda resource: 0
        card = self.carousel.slides[0]
        quantity = next(w for w in card.walk() if isinstance(w, TextInput))
        quantity.text = '2'
        hire = next(w for w in card.walk() if isinstance(w, Button) and w.text == 'НАНЯТЬ')
        self.assertTrue(hire.disabled)

    def test_close_dismisses_once_and_releases_the_owner(self):
        calls = []
        self.root.popup.bind(on_dismiss=lambda *args: calls.append('dismiss'))
        self.root.close_button.dispatch('on_release')
        self.assertEqual(calls, ['dismiss'])
        self.assertIsNone(self.root.parent)
        self.assertTrue(self.root.released)


if __name__ == '__main__':
    unittest.main()
