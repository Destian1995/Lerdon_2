import json
import time
import unittest
from types import SimpleNamespace
from pathlib import Path

from strategy_ui_fixture import city_fixture, hud_fixture, cleanup_hud, Window, Clock
from kivy.base import EventLoop
from PIL import Image
from kivy.uix.boxlayout import BoxLayout
from strategy_ui import bind_row_tap

ROOT = Path(__file__).resolve().parents[1]


class StrategyUITests(unittest.TestCase):
    def setUp(self):
        self.original_size = Window.size
        self.popups = []
        self.huds = []

    def settle(self):
        for _ in range(5):
            time.sleep(0.02)
            EventLoop.idle()

    def viewport(self, size):
        Window.size = size
        self.settle()

    def popup(self, **kwargs):
        popup, db = city_fixture(**kwargs)
        self.popups.append((popup, db))
        popup.open(animation=False)
        self.settle()
        return popup

    def tearDown(self):
        for popup, db in self.popups:
            popup.dismiss(animation=False)
            db.close()
        for host in self.huds:
            cleanup_hud(host)
            if host.parent:
                host.parent.remove_widget(host)
        Window.size = self.original_size
        self.settle()

    def test_landscape_city_uses_two_columns_and_touch_sized_actions(self):
        self.viewport((1280, 576))
        popup = self.popup(populated=True)
        self.assertTrue(popup.city_columns._wide)
        self.assertEqual(len(popup.city_columns.body.children), 2)
        self.assertEqual(set(popup.city_action_buttons), {'move', 'army', 'build'})
        self.assertEqual(len(popup.attacking_units_box.children), 1)
        self.assertIn('25 / 25', popup.city_building_count.text)
        for button in popup.city_action_buttons.values():
            self.assertGreaterEqual(button.height, 48)
            self.assertGreaterEqual(button.y, popup.y)
            self.assertLessEqual(button.top, popup.top)

    def test_compact_city_tabs_preserve_actions_and_content(self):
        self.viewport((640, 360))
        popup = self.popup()
        self.assertFalse(popup.city_columns._wide)
        popup.city_columns.select(1)
        self.settle()
        self.assertIs(popup.city_columns.body.children[0], popup.city_columns.panels[1])
        self.assertEqual(len(popup.buildings_box.children), 3)
        self.assertGreaterEqual(popup.buildings_list.height, 48)
        calls = []
        popup.load_troops_by_type = lambda *args: calls.append(('move', args))
        popup._open_build_menu = lambda: calls.append(('build',))
        popup.city_action_buttons['move'].dispatch('on_release')
        popup.city_action_buttons['build'].dispatch('on_release')
        self.assertEqual(calls, [('move', ('Любые', None)), ('build',)])
        self.assertLessEqual(popup.width, Window.width)
        self.assertLessEqual(popup.height, Window.height)

    def test_foreign_and_undead_city_do_not_offer_owned_city_actions(self):
        self.viewport((800, 480))
        foreign = self.popup(owner='Эльфы')
        self.assertEqual(set(foreign.city_action_buttons), {'move'})
        foreign.dismiss(animation=False)
        undead = self.popup(owner='Нежить', undead=True)
        self.assertEqual(set(undead.city_action_buttons), {'move'})
        self.assertTrue(undead._is_undead_city)
        self.assertTrue(json.loads((ROOT / 'files/city/death/lore.json').read_text(encoding='utf-8'))['Некрополь'])

    def test_open_city_adapts_on_rotation_without_losing_selection(self):
        self.viewport((640, 360))
        popup = self.popup()
        popup.city_columns.select(1)
        self.viewport((1000, 600))
        self.assertTrue(popup.city_columns._wide)
        self.viewport((480, 800))
        self.assertFalse(popup.city_columns._wide)
        self.assertEqual(popup.city_columns.selected, 1)
        self.assertIs(popup.city_columns.body.children[0], popup.city_columns.panels[1])

    def test_hud_resources_reuse_rows_and_end_turn_does_not_overlap(self):
        self.viewport((640, 360))
        host = hud_fixture()
        self.huds.append(host)
        Window.add_widget(host)
        self.settle()
        before = {name: id(label) for name, label in host.resource_box._label_values.items()}
        host.resource_box.update_resources()
        self.assertEqual(before, {name: id(label) for name, label in host.resource_box._label_values.items()})
        panels = host._hud_panels
        self.assertLessEqual(panels['end_turn'].top, panels['resources'].y)
        self.assertGreaterEqual(panels['end_turn'].y, 0)
        self.assertEqual(len(host.resource_box._label_values), 6)
        self.assertTrue(all(hasattr(panel, '_strategy_frame') for panel in panels.values()))
        cleanup_hud(host)
        self.assertIsNone(host.resource_box._refresh_event)

    def test_status_icons_are_transparent_compact_and_aliases_match(self):
        manifest = json.loads((ROOT / 'assets/status-redraw-manifest.json').read_text(encoding='utf-8'))
        self.assertEqual(len(manifest['assets']), 22)
        for asset in manifest['assets']:
            image = Image.open(ROOT / asset['path'])
            self.assertEqual(image.size, (128, 128))
            self.assertEqual(image.mode, 'RGBA')
            self.assertEqual(image.getchannel('A').getextrema(), (0, 255))
        for target, source in manifest['aliases'].items():
            self.assertEqual((ROOT / target).read_bytes(), (ROOT / source).read_bytes())

    def test_dragging_a_garrison_row_does_not_open_details(self):
        row = BoxLayout(pos=(0, 0), size=(300, 80))
        calls = []
        bind_row_tap(row, lambda *args: calls.append('details'))
        touch = SimpleNamespace(pos=(20, 20), ud={}, is_mouse_scrolling=False)
        row.dispatch('on_touch_down', touch)
        touch.pos = (20, 60)
        row.dispatch('on_touch_up', touch)
        self.assertEqual(calls, [])
        touch.pos = (20, 20)
        row.dispatch('on_touch_down', touch)
        touch.pos = (21, 21)
        row.dispatch('on_touch_up', touch)
        self.assertEqual(calls, ['details'])
