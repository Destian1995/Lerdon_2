"""Exercise workshop geometry and the actual combat threshold with isolated data."""
import ast
import random
import unittest
from unittest.mock import patch

from strategy_ui_fixture import *
from test_responsive_windows import settle
from window_theme import install_window_theme
from utils.faction_bonuses import combat_bonus_status, garrison_bonus_status
from troop_movement import queue_ai_march, play_ai_marches
import test_troop_movement as march_tests


class BonusStatusTests(unittest.TestCase):
    def test_unit_card_marks_oplot_green_even_with_only_hero_durability(self):
        popup, conn = city_fixture(populated=True)
        self.addCleanup(conn.close)
        self.addCleanup(popup.dismiss)
        conn.execute("INSERT INTO units VALUES ('hero','','2',0,0,9120,100,'infantry')")
        conn.execute("INSERT INTO garrisons VALUES ('Виндгар','hero',1,'',0)")
        popup.update_garrison()
        texts = [w.text for w in popup.content.walk(restrict=True) if isinstance(w, Label)]
        self.assertTrue(any('[color=#66CC66]Оплот\nПрименяется' in text for text in texts))
        conn.execute("DELETE FROM garrisons WHERE unit_name='hero'")
        popup.update_garrison()
        texts = [w.text for w in popup.content.walk(restrict=True) if isinstance(w, Label)]
        self.assertTrue(any('Оплот\nНе применяется' in text for text in texts))

    def test_oplot_uses_base_durability_and_hero_durability_before_experience(self):
        # Defense alone would pass x20, but battle power includes durability.
        self.assertFalse(combat_bonus_status('Адепты', 10, 10, 180, (0, 190, 0))[1])
        self.assertTrue(combat_bonus_status('Адепты', 10, 10, 180, (0, 0, 3800))[1])
        self.assertTrue(combat_bonus_status('Адепты', 10, 0, 0, (0, 19, 0))[1])
        self.assertFalse(combat_bonus_status('Север', 10, 0, 0, (189, 0, 0))[1])
        self.assertTrue(combat_bonus_status('Север', 10, 0, 0, (190, 0, 0))[1])

    def test_summary_only_counts_live_troops_and_local_heroes(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.executescript('''CREATE TABLE units(unit_name,unit_class,attack,defense,durability,faction);
            CREATE TABLE garrisons(city_name,unit_name,unit_count);
            INSERT INTO units VALUES('troop','1',10,10,0,'Север'),('hero','2',190,0,0,'Север');
            INSERT INTO garrisons VALUES('A','troop',100),('A','hero',1),('B','troop',100),('B','hero',0);''')
        self.assertEqual(garrison_bonus_status(conn, 'Север'), (1, 2))


class AIMarchTests(unittest.TestCase):
    setUp = march_tests.MovementArrivalTests.setUp
    tearDown = march_tests.MovementArrivalTests.tearDown

    def test_capture_notification_starts_on_arrival_and_does_not_repeat(self):
        fx = self.layer.city_effects
        fx.sync([('B', 300, 300, 'Нейтрал')], {}, 0)
        queue_ai_march(self.db, 'Север', 'A', 'B', [dict(unit_count=20)])
        from troop_movement import deferred_ai_captures
        fx.sync([('B', 300, 300, 'Север')], {}, 0, deferred=deferred_ai_captures(self.db))
        self.assertFalse(fx.captures)
        play_ai_marches(self.screen)
        march = self.layer.marches.marches[0]
        self.layer.marches.update(march.duration - .01)
        self.assertFalse(fx.captures)
        self.layer.marches.update(.02)
        self.assertEqual(len(fx.captures), 1)
        fx.sync([('B', 300, 300, 'Север')], {}, 0)
        self.assertEqual(len(fx.captures), 1)

    def test_refresh_map_updates_cities_synchronously(self):
        tree = ast.parse((ROOT / 'game_process.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'refresh_map')
        updates = []
        self.map.update_cities = lambda dt: updates.append(dt)
        self.screen.update_army_rating = lambda: None
        namespace = dict(_active_game_screen=self.screen)
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'game_process.py', 'exec'), namespace)
        namespace['refresh_map']()
        self.assertEqual(updates, [0])

    def test_ai_routes_are_merged_and_replayed_without_changing_garrisons(self):
        before = self.db.execute('SELECT * FROM garrisons').fetchall()
        queue_ai_march(self.db, 'Север', 'A', 'C', [dict(unit_count=20)])
        queue_ai_march(self.db, 'Север', 'A', 'C', [dict(unit_count=30)])
        self.assertFalse(self.layer.marches.marches)
        play_ai_marches(self.screen)
        self.assertEqual(len(self.layer.marches.marches), 1)
        self.assertEqual(self.layer.marches.marches[0].route.points[-1], (538.5, 330))
        self.assertFalse(self.screen._ai_march_queue)
        self.assertEqual(self.db.execute('SELECT * FROM garrisons').fetchall(), before)


class WorkshopGeometryTests(unittest.TestCase):
    def test_all_parameters_visible_without_scrolling(self):
        from kivy.metrics import Metrics
        original_open, size = Popup.open, Window.size
        metrics = Metrics.density, Metrics.fontscale
        popups = []
        install_window_theme()
        themed_open = Popup.open
        def capture(popup, *args, **kwargs):
            popups.append(popup)
            return themed_open(popup, *args, **kwargs)
        tree = ast.parse((ROOT / 'create_artifacts.py').read_text(encoding='utf-8'))
        nodes = [n for n in tree.body if isinstance(n, (ast.Assign, ast.FunctionDef))]
        namespace = dict(globals(), show_message=lambda *args: None)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), 'create_artifacts.py', 'exec'), namespace)
        try:
            with patch.object(Popup, 'open', capture):
                for width, height, density in ((1280, 576, 1), (1280, 576, 1.5), (390, 844, 1)):
                    with self.subTest(size=(width, height), density=density):
                        Metrics.density = density
                        Window.size = width, height
                        settle()
                        namespace['workshop'](SimpleNamespace(faction='Адепты', money=500000), None)
                        settle()
                        popup = popups[-1]
                        button = next(w for w in popup.content.walk() if isinstance(w, Button) and w.text == 'Далее >>')
                        button.dispatch('on_release')
                        settle()
                        flow = popup._window_flow
                        self.assertAlmostEqual(flow.body.height, flow.height, delta=1)
                        controls = [w for w in flow.body.walk(restrict=True) if isinstance(w, (Label, Slider))]
                        self.assertEqual(sum(isinstance(w, Slider) for w in controls), 2)
                        _, bottom = flow.to_window(*flow.pos)
                        for widget in controls:
                            _, y = widget.to_window(*widget.pos)
                            self.assertGreaterEqual(y + 1, bottom, getattr(widget, 'text', 'slider'))
                            self.assertLessEqual(y + widget.height, bottom + flow.height + 1,
                                                 getattr(widget, 'text', 'slider'))
                        popup.dismiss(animation=False)
                        settle()
        finally:
            for popup in popups:
                popup.dismiss(animation=False)
            Popup.open = original_open
            Metrics.density, Metrics.fontscale = metrics
            Window.size = size
            settle()


if __name__ == '__main__':
    unittest.main()
