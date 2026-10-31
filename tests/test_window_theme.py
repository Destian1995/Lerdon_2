import os
import ast
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.update(KIVY_NO_ARGS='1', KIVY_NO_CONFIG='1', KIVY_NO_FILELOG='1',
                  KIVY_METRICS_DENSITY='1', KIVY_METRICS_FONTSCALE='1')
from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
from kivy.base import EventLoop
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.slider import Slider
from window_theme import install_window_theme, has_close_button, is_close_button
from strategy_ui_fixture import city_fixture
from strategy_ui_fixture import __dict__ as fixture_globals


class WindowThemeTests(unittest.TestCase):
    def setUp(self):
        self.original = Popup.open
        install_window_theme()
        self.popups = []

    def tearDown(self):
        for popup in self.popups:
            popup.dismiss(animation=False)
        Popup.open = self.original

    def open(self, content, **kwargs):
        popup = Popup(content=content, **kwargs)
        self.popups.append(popup)
        popup.open(animation=False)
        return popup

    def test_city_has_exactly_one_close_under_real_global_open_hook(self):
        popup, db = city_fixture()
        self.popups.append(popup)
        try:
            popup.open(animation=False)
            self.assertEqual(sum(is_close_button(w) for w in popup.content.walk()), 1)
            self.assertFalse(getattr(popup, '_close_x_injected', False))
            self.assertFalse(getattr(popup.content, '_window_theme_wrapper', False))
        finally:
            db.close()

    def test_existing_close_callback_and_game_action_are_preserved(self):
        body = BoxLayout()
        buy, close = Button(text='Купить'), Button(text='Закрыть')
        calls = []
        buy.bind(on_release=lambda *args: calls.append('buy'))
        close.bind(on_release=lambda *args: calls.append('close'))
        body.add_widget(buy)
        body.add_widget(close)
        popup = self.open(body, title='Рынок')
        buy.dispatch('on_release')
        close.dispatch('on_release')
        self.assertEqual(calls, ['buy', 'close'])
        self.assertEqual(sum(is_close_button(w) for w in popup.content.walk()), 1)
        self.assertTrue(hasattr(buy, '_window_button_skin'))

    def test_auto_close_is_themed_and_reopen_does_not_duplicate_it(self):
        body = BoxLayout()
        body.add_widget(Button(text='Действие'))
        popup = self.open(body, title='Действие', auto_dismiss=False)
        self.assertTrue(has_close_button(popup.content))
        popup.dismiss(animation=False)
        popup.open(animation=False)
        self.assertEqual(sum(is_close_button(w) for w in popup.content.walk()), 1)

    def test_content_replacement_and_added_buttons_receive_theme(self):
        popup = self.open(BoxLayout(), title='Артефакты')
        replacement = BoxLayout()
        action = Button(text='Создать')
        replacement.add_widget(action)
        popup.content = replacement
        self.assertTrue(hasattr(action, '_window_button_skin'))
        later = Button(text='Купить')
        replacement.add_widget(later)
        for _ in range(3):
            time.sleep(0.02)
            EventLoop.idle()
        self.assertTrue(hasattr(later, '_window_button_skin'))

    def test_inputs_and_selected_toggle_retain_state_and_values(self):
        body = BoxLayout()
        value = TextInput(text='250')
        selected = ToggleButton(text='Налоги', state='down')
        body.add_widget(value)
        body.add_widget(selected)
        self.open(body, title='Экономика')
        self.assertEqual(value.text, '250')
        self.assertEqual(selected.state, 'down')
        self.assertGreater(value.foreground_color[0], 0.8)

    def test_timed_noninteractive_window_does_not_get_a_cancel_action(self):
        popup = self.open(Label(text='Сражение…'), title='Бой', auto_dismiss=False)
        self.assertFalse(has_close_button(popup.content))

    def test_readability_adjustment_does_not_rewrite_message_text(self):
        label = Label(text='Код #333333 [color=#333333]Подпись[/color]', markup=True)
        self.open(label, title='Сообщение')
        self.assertIn('Код #333333', label.text)
        self.assertIn('[color=#B9C5D1]Подпись[/color]', label.text)

    def test_real_tax_dialog_keeps_apply_action_and_effect_callback(self):
        path = Path(__file__).resolve().parents[1] / 'economic.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'open_tax_popup')
        namespace = dict(fixture_globals, platform='android')
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
        calls = []
        faction = SimpleNamespace(current_tax_rate='15%', tax_set=False, tax_effect=lambda rate: 0,
                                  set_taxes=lambda rate: calls.append(('tax', rate)),
                                  apply_tax_effect=lambda rate: calls.append(('effect', rate)))
        namespace['open_tax_popup'](faction)
        from kivy.core.window import Window
        popup = next(widget for widget in Window.children if isinstance(widget, Popup) and widget.title == 'Управление налогами')
        self.popups.append(popup)
        slider = next(widget for widget in popup.content.walk() if isinstance(widget, Slider))
        slider.value = 35
        button = next(widget for widget in popup.content.walk() if isinstance(widget, Button) and widget.text == 'Применить')
        self.assertTrue(hasattr(button, '_window_button_skin'))
        button.dispatch('on_release')
        self.assertEqual(calls, [('tax', 35), ('effect', 35)])
