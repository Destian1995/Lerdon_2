import unittest
from types import SimpleNamespace

from strategy_ui_fixture import Window, dp
from test_frontend_ui import settle
from kivy.metrics import Metrics
from development_ui import open_development, STRATEGIES
from window_theme import install_window_theme


class DevelopmentTests(unittest.TestCase):
    def test_choices_and_details_fit_and_save_only_when_applied(self):
        original = Window.size, Metrics.density, Metrics.fontscale
        install_window_theme()
        saved, messages = [], []
        faction = SimpleNamespace(auto_build_ratio=(2, 1), auto_build_enabled=False,
                                  hospitals=12345, factories=12345, money_up=15000000,
                                  save_auto_build_settings=lambda: saved.append(faction.auto_build_ratio))
        popup = open_development(faction, lambda *args: messages.append(args))
        try:
            for size, density in (((640, 360), 1), ((1280, 576), 2), ((320, 568), 1)):
                Metrics.density, Metrics.fontscale = density, 1.2
                Window.size = size
                settle()
                root = popup.content
                actions, info, choices, header = root.children
                self.assertGreaterEqual(choices.height, dp(48))
                for child in root.children:
                    self.assertGreaterEqual(child.y, root.y)
                    self.assertLessEqual(child.top, root.top)
                for label in info.children:
                    if hasattr(label, 'texture_size'):
                        self.assertLessEqual(label.texture_size[1], label.height + 1)
                        self.assertGreaterEqual(label.y, actions.top)
                for card in choices.children:
                    card.dispatch('on_release')
                    self.assertEqual(faction.auto_build_ratio, (2, 1))
                # Kivy stores children in reverse order: select the last strategy.
                choices.children[0].dispatch('on_release')
            self.assertEqual(saved, [])
            actions.children[0].dispatch('on_release')
            self.assertEqual(saved, [STRATEGIES[2][0]])
            self.assertTrue(faction.auto_build_enabled)
        finally:
            popup.dismiss(animation=False)
            Window.size, Metrics.density, Metrics.fontscale = original
