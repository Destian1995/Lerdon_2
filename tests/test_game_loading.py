"""Startup lifecycle without importing main or changing the player's database."""
import ast
import os
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
from kivy.clock import Clock
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.widget import Widget
from game_loading import GameLoadingPanel


class GameLoadingTests(unittest.TestCase):
    def pump(self, until, timeout=3):
        deadline = time.monotonic() + timeout
        while not until() and time.monotonic() < deadline:
            time.sleep(0.02)
            Clock.tick()
        self.assertTrue(until())

    def tearDown(self):
        if hasattr(self, 'panel'):
            self.panel.dismiss()

    def test_panel_precedes_work_and_steps_finish_in_order(self):
        calls = []
        self.panel = GameLoadingPanel([
            ('Карта', lambda: calls.append(('map', self.panel.parent is not None))),
            ('Интерфейс', lambda: calls.append(('ui', self.panel.progress.value))),
        ], on_complete=lambda: calls.append(('done', self.panel.parent is None)))
        self.panel.start()
        self.panel.start()
        self.assertEqual(calls, [])
        self.assertIsNotNone(self.panel.parent)
        self.pump(lambda: len(calls) == 3)
        self.assertEqual(calls, [('map', True), ('ui', 1), ('done', True)])

    def test_error_stops_work_and_keeps_explanation_visible(self):
        calls = []
        def broken():
            raise RuntimeError('Synthetic startup failure')
        self.panel = GameLoadingPanel([('Карта', broken), ('Later', lambda: calls.append('later'))],
                                      on_error=lambda error: calls.append(str(error)))
        self.panel.start()
        self.pump(lambda: bool(calls))
        self.assertEqual(calls, ['Synthetic startup failure'])
        self.assertIsNotNone(self.panel.parent)
        self.assertEqual(self.panel.completed, 0)
        self.assertIn('Не удалось', self.panel.status.text)

    def test_dismiss_cancels_pending_work(self):
        calls = []
        self.panel = GameLoadingPanel([('Карта', lambda: calls.append(1))])
        self.panel.start()
        self.panel.dismiss()
        time.sleep(0.15)
        Clock.tick()
        self.assertEqual(calls, [])

    def test_new_game_keeps_panel_during_root_replacement(self):
        path = Path(__file__).resolve().parents[1] / 'main.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'KingdomSelectionWidget')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'cleanup_and_start_game')
        calls = []
        root = FloatLayout()
        app = SimpleNamespace(root=root, selected_kingdom='Север')
        owner = SimpleNamespace(conn=SimpleNamespace(commit=lambda: calls.append('commit')),
                                selected_allies=[], tutorial_enabled=False,
                                ideology_spinner=SimpleNamespace(text='Борьба'),
                                disable_all_buttons=lambda disabled: calls.append(('locked', disabled)))
        def make_map(**kwargs):
            self.assertIsNotNone(owner._game_loading.parent)
            calls.append('map')
            return Widget()
        namespace = dict(App=SimpleNamespace(get_running_app=lambda: app), Clock=Clock,
                         clear_tables=lambda conn: calls.append('clear'),
                         restore_from_backup=lambda conn: calls.append('restore'),
                         MapWidget=make_map, load_cities_from_db=lambda *args: [],
                         GameScreen=lambda *args, **kwargs: Widget())
        exec(compile(ast.Module(body=[method], type_ignores=[]), str(path), 'exec'), namespace)
        namespace['cleanup_and_start_game'](owner)
        self.panel = owner._game_loading
        namespace['cleanup_and_start_game'](owner)
        self.assertEqual(calls, [('locked', True)])
        self.pump(lambda: owner._game_loading is None)
        self.assertEqual(len(root.children), 2)
        self.assertEqual(owner.selected_ideology, 'Борьба')
        self.assertEqual(calls, [('locked', True), 'clear', 'commit', 'restore', 'map'])
