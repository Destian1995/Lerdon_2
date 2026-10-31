import time
import unittest
import ast

from strategy_ui_fixture import Window, Image, FloatLayout
from kivy.base import EventLoop
from portrait_ui import style_portrait_image, portrait_accent
from strategy_ui_fixture import ROOT
from strategy_ui_fixture import __dict__ as fixture_globals
from strategy_ui import FACTIONS


class PortraitFrameTests(unittest.TestCase):
    def setUp(self):
        self.host = FloatLayout()
        Window.add_widget(self.host)

    def tearDown(self):
        Window.remove_widget(self.host)

    def image(self, source, framed=True):
        widget = Image(source=source, size_hint=(None, None), size=(320, 200), pos=(20, 30), fit_mode='contain')
        if framed:
            style_portrait_image(widget, enabled=True)
        self.host.add_widget(widget)
        for _ in range(5):
            time.sleep(.02)
            EventLoop.idle()
        return widget

    def test_units_heroes_and_factions_have_frames_but_status_and_map_do_not(self):
        for source in ('files/army/death/morgana.png', 'files/pict/hero/default_image.png',
                       'files/buildings/people.png', 'files/sov/vampire.jpg'):
            widget = self.image(source)
            self.assertTrue(widget._portrait_frame.visible, source)
        for source in ('files/status/army.png', 'files/map/generate/map_1.png', 'files/menu/choise/vampire.jpg'):
            self.assertIsNone(portrait_accent(source))

    def test_frame_follows_visible_portrait_and_resize_without_layout_changes(self):
        widget = self.image('files/army/death/morgana.png')
        frame = widget._portrait_frame
        before = (widget.pos, widget.size, widget.size_hint)
        frame.update()
        self.assertEqual(before, (widget.pos, widget.size, widget.size_hint))
        x, y, width, height = frame.bounds
        self.assertAlmostEqual(x + width / 2, widget.center_x)
        self.assertAlmostEqual(y + height / 2, widget.center_y)
        ix, iy, iw, ih = frame.image_bounds
        self.assertLess(x, ix)
        self.assertLess(y, iy)
        self.assertGreater(x + width, ix + iw)
        self.assertGreater(y + height, iy + ih)
        widget.size = (420, 280)
        frame.update()
        self.assertNotEqual(frame.bounds, (x, y, width, height))

    def test_dynamic_source_changes_update_one_frame_and_faction_accent(self):
        widget = self.image('files/status/army.png')
        widget.source = 'files/army/death/morgana.png'
        decoration = widget._portrait_frame
        for _ in range(5):
            EventLoop.idle()
        self.assertEqual(tuple(decoration.accent.rgba[:3]), tuple(FACTIONS['Нежить'][:3]))
        widget.source = 'files/army/people/vlad.jpg'
        self.assertIs(widget._portrait_frame, decoration)
        self.assertEqual(widget.canvas.after.children.count(decoration.group), 1)
        widget.source = 'files/status/army.png'
        self.assertFalse(decoration.visible)

    def test_map_and_game_menu_icons_stay_unframed_even_when_themed(self):
        from window_theme import theme_tree
        for source in ('files/buildings/people.png', 'files/buildings/vampires.png',
                       'files/sov/adept.jpg', 'files/army/people/vlad.jpg'):
            widget = self.image(source, framed=False)
            theme_tree(self.host)
            self.assertFalse(hasattr(widget, '_portrait_frame'), source)

    def test_turn_overlay_explicitly_frames_the_active_faction_portrait(self):
        tree = ast.parse((ROOT / 'game_process.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'TurnOverlay')
        namespace = dict(fixture_globals, KivyImage=Image)
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'game_process.py', 'exec'), namespace)
        overlay = namespace['TurnOverlay']()
        self.host.add_widget(overlay)
        overlay._faction_img.source = 'files/sov/vampire.jpg'
        for _ in range(5):
            EventLoop.idle()
        self.assertTrue(overlay._faction_img._portrait_frame.visible)

    def test_explicit_disabling_removes_an_existing_frame(self):
        widget = self.image('files/army/death/morgana.png')
        style_portrait_image(widget, enabled=False)
        self.assertFalse(widget._portrait_frame.visible)

    def test_actual_game_menu_icons_have_no_image_or_button_frames(self):
        from strategy_ui_fixture import hud_fixture, cleanup_hud
        hud = hud_fixture()
        try:
            for button in hud.tab_buttons.values():
                self.assertFalse(hasattr(button, '_portrait_frame'))
                self.assertFalse(hasattr(button, '_strategy_frame'))
        finally:
            cleanup_hud(hud)

    def test_shop_and_battle_portraits_are_unframed(self):
        from battle_ui import CombatSide
        from dialog700_fixture import equipment
        from kivy.uix.popup import Popup
        from window_theme import install_window_theme
        install_window_theme()
        side = CombatSide('Нежить', 'Защита', 'files/army/death/morgana.png')
        self.host.add_widget(side)
        self.assertFalse(hasattr(side.image, '_portrait_frame'))
        equipment()
        popup = next(w for w in Window.children if isinstance(w, Popup))
        try:
            self.assertFalse(hasattr(popup.hero_portrait, '_portrait_frame'))
        finally:
            popup.dismiss(animation=False)

    def test_recruitment_menu_keeps_unit_portrait_frame(self):
        from recruitment_ui import RecruitmentSession
        from types import SimpleNamespace
        unit = dict(image='files/army/death/morgana.png', cost=(20, 1),
                    stats={'Класс юнита': '2 класс', 'Урон': 208, 'Защита': 800, 'Живучесть': 50})
        army = SimpleNamespace(class_faction=SimpleNamespace(get_resource_now=lambda _: 10000))
        session = RecruitmentSession('Нежить', army, {'Моргана': unit}, lambda *args: None)
        self.host.add_widget(session)
        try:
            session.open()
            self.assertTrue(session.cards[0].portrait._portrait_frame.visible)
        finally:
            session.release()


if __name__ == '__main__':
    unittest.main()
