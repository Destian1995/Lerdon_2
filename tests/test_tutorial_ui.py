import ast
from pathlib import Path
import time
import unittest

from strategy_ui_fixture import city_fixture, Window
from kivy.base import EventLoop
from kivy.uix.floatlayout import FloatLayout
from kivy.tests.common import UnitTestTouch

from tutorial import TutorialProgress, notify_event, set_event_handler
from tutorial_ui import TutorialPanel


class TutorialUITests(unittest.TestCase):
    def setUp(self):
        self.original_size = Window.size
        self.progress = TutorialProgress('Борьба')
        self.panel = TutorialPanel(self.progress, self.progress.next, self.progress.back,
                                   self.progress.stop, lambda: None)
        EventLoop.ensure_window()
        Window.add_widget(self.panel)

    def settle(self):
        for _ in range(5):
            time.sleep(.02)
            EventLoop.idle()

    def tearDown(self):
        set_event_handler(None)
        if self.panel.parent:
            self.panel.parent.remove_widget(self.panel)
        Window.size = self.original_size
        self.settle()

    def test_phone_and_desktop_keep_actions_inside_card(self):
        for size in ((1280, 720), (640, 360), (360, 640)):
            Window.size = size
            self.settle()
            self.assertGreaterEqual(self.panel.card.x, 0)
            self.assertLessEqual(self.panel.card.right, Window.width)
            self.assertLessEqual(self.panel.card.top, Window.height)
            for button in (self.panel.back_btn, self.panel.next_btn, self.panel.skip_btn, self.panel.fold):
                self.assertGreaterEqual(button.y, self.panel.card.y)
                self.assertLessEqual(button.top, self.panel.card.top)
                self.assertGreaterEqual(button.height, 48)
                self.assertGreaterEqual(button.x, self.panel.card.x)
                self.assertLessEqual(button.right, self.panel.card.right)

    def test_long_text_scrolls_in_short_landscape(self):
        self.progress.next()
        self.progress.next()
        self.panel.refresh()
        Window.size = (640, 360)
        self.settle()
        self.assertGreater(self.panel.message.height, self.panel.scroll.height)
        self.assertEqual(self.panel.message.text_size[1], None)

    def test_fold_and_resume_preserve_step(self):
        self.progress.next()
        self.panel.refresh()
        self.panel.toggle()
        self.assertNotIn(self.panel.body, self.panel.card.children)
        self.panel.toggle()
        self.assertIn(self.panel.body, self.panel.card.children)
        self.assertEqual(self.progress.index, 1)

    def test_gate_button_updates_after_actual_event(self):
        self.progress.next()
        self.progress.next()
        self.panel.refresh()
        self.assertTrue(self.panel.next_btn.disabled)
        self.progress.record('tax_set')
        self.panel.refresh()
        self.assertFalse(self.panel.next_btn.disabled)

    def test_touch_outside_card_reaches_game(self):
        Window.size = (1280, 720)
        self.settle()
        touch = UnitTestTouch(10, Window.height - 10)
        touch.scale_for_screen(Window.width, Window.height)
        self.assertFalse(self.panel.on_touch_down(touch))
        self.assertFalse(self.panel.on_touch_up(touch))

    def test_only_own_city_open_completes_city_exercise(self):
        class Receiver:
            def receive(self, event):
                events.append(event)
        events = []
        receiver = Receiver()
        set_event_handler(receiver.receive)
        for owner in ('Эльфы', 'Адепты'):
            popup, conn = city_fixture(owner=owner)
            try:
                popup.dispatch('on_open')
            finally:
                conn.close()
        self.assertEqual(events, ['owned_city_opened'])

    def test_screen_skip_detaches_panel_and_ignores_late_events(self):
        tree = ast.parse(Path('game_process.py').read_text(encoding='utf-8'))
        game = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GameScreen')
        names = {'_tutorial_event', '_tutorial_next', '_tutorial_back', '_dismiss_hint', 'skip_tutorial'}
        methods = [n for n in game.body if isinstance(n, ast.FunctionDef) and n.name in names]
        namespace = {}
        exec(compile(ast.Module(body=methods, type_ignores=[]), 'game_process.py', 'exec'), namespace)
        host_type = type('TutorialHost', (FloatLayout,), {n.name: namespace[n.name] for n in methods})
        host = host_type()
        Window.add_widget(host)
        try:
            host.tutorial_enabled = True
            host.tutorial_progress = self.progress
            host.current_hint = self.panel
            host.current_tutorial_step = 1
            set_event_handler(host._tutorial_event)
            host.skip_tutorial()
            notify_event('tax_set')
            self.assertIsNone(host.current_hint)
            self.assertIsNone(self.panel.parent)
            self.assertFalse(host.tutorial_enabled)
            self.assertEqual(self.progress.events, set())
        finally:
            Window.remove_widget(host)


if __name__ == '__main__':
    unittest.main()
