import sqlite3
import ast
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import closing

from strategy_ui_fixture import *
from kivy.base import EventLoop
from kivy.metrics import Metrics
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from window_theme import install_window_theme
from test_frontend_ui import frontend_classes
from frontend_ui import build_rating
from ai_models.advisor_view import AdvisorView
from event_ticker import EventQueue
from slider_ui import StrategySlider
from strategy_ui_fixture import __dict__ as fixture_globals
from kivy.uix.checkbox import CheckBox
from kivy.uix.slider import Slider


def settle(frames=25):
    for _ in range(frames):
        time.sleep(0.012)
        EventLoop.idle()


class UIRegressionTests(unittest.TestCase):
    def setUp(self):
        self.size = Window.size
        self.metrics = Metrics.density, Metrics.fontscale
        self.old_open = Popup.open
        install_window_theme()
        self.host = FloatLayout()
        Window.add_widget(self.host)
        self.db = sqlite3.connect(':memory:')
        with closing(sqlite3.connect(f'file:{(ROOT / "game_data.db").as_posix()}?mode=ro', uri=True)) as source:
            source.backup(self.db)
        for index, faction in enumerate(('Север', 'Эльфы', 'Адепты', 'Вампиры', 'Элины')):
            self.db.execute('INSERT INTO cities(name,faction,coordinates) VALUES (?,?,?)',
                            (f'Test {index}', faction, str([index * 100, 100])))
        self.db.commit()

    def tearDown(self):
        for widget in list(Window.children):
            if isinstance(widget, Popup):
                widget.dismiss(animation=False)
        self.host.clear_widgets()
        if self.host.parent:
            Window.remove_widget(self.host)
        settle(5)
        self.db.close()
        Popup.open = self.old_open
        Metrics.density, Metrics.fontscale = self.metrics
        Window.size = self.size
        settle(5)

    def test_real_chat_selection_and_close_repeatedly_removes_only_chat(self):
        Window.size = (640, 360)
        settle(5)
        for index in range(3):
            advisor = AdvisorView('Север', self.db)
            self.host.add_widget(advisor)
            settle()
            self.assertGreaterEqual(len(advisor.diplomacy_chat._faction_buttons), 4)
            for button in advisor.diplomacy_chat._faction_buttons.values():
                button.dispatch('on_press')
                self.assertGreater(sum(button.color[:3]), 2)
            settle(5)
            popup = advisor.popup
            advisor.close_window(None)
            advisor.close_window(None)
            settle()
            self.assertIsNone(popup.parent)
            self.assertIsNone(advisor.parent)
            self.assertFalse(self.host.children)
            self.assertTrue(advisor.diplomacy_chat._disposed)
            self.assertTrue(advisor.diplomacy_chat.keyboard_helper._disposed)

    def test_campaign_panels_have_top_aligned_titles_and_fixed_footer_at_android_density(self):
        Metrics.density, Metrics.fontscale = 2, 1.2
        Window.size = (1280, 576)
        settle(5)
        classes = frontend_classes()
        with patch('kivy.app.App.get_running_app', return_value=SimpleNamespace(selected_kingdom=None)):
            setup = classes['KingdomSelectionWidget'](self.db)
            self.host.add_widget(setup)
            settle()
            first_title = list(reversed(setup.faction_panel_container.children))[0]
            self.assertLess(setup.faction_panel_container.top - first_title.top, dp(16))
            self.assertLess(first_title.height, dp(40))
            self.assertGreaterEqual(setup.back_btn.y, 0)
            self.assertGreaterEqual(setup.start_game_button.y, 0)
            self.assertLessEqual(setup.start_game_button.top, setup.top)
            columns = setup.campaign_columns
            self.assertGreaterEqual(columns.body.y, setup.start_game_button.top)
            for button in setup.kingdom_button_widgets.values():
                self.assertGreaterEqual(button.height, dp(48))
            self.assertLess(setup._front_page.flow.width, Window.width)
            heights = (setup.faction_panel_container.height, setup.settings_panel_container.height, first_title.height)
            settle(30)
            self.assertEqual(heights, (setup.faction_panel_container.height, setup.settings_panel_container.height, first_title.height))

    def test_rating_content_stays_inside_its_scroll_and_filter_preserves_data(self):
        Window.size = (640, 360)
        owner = FloatLayout()
        owner.conn = self.db
        owner.go_back = owner.clear_dossier = lambda *args: None
        build_rating(owner)
        self.host.add_widget(owner)
        settle()
        page = owner._front_page
        footer = page.column.children[0]
        scroll = page.column.children[1]
        self.assertGreaterEqual(scroll.y, footer.top)
        self.assertLessEqual(scroll.top, page.column.top)
        self.assertGreaterEqual(footer.y, 0)
        for card in owner.rating_records.children:
            ordered = list(reversed(card.children))
            for upper, lower in zip(ordered, ordered[1:]):
                self.assertGreaterEqual(upper.y + 1, lower.top)

    def test_slider_keeps_range_and_updates_vector_thumb(self):
        slider = StrategySlider(min=-10, max=30, value=0, size=(300, 48), size_hint=(None, None))
        self.host.add_widget(slider)
        settle(5)
        before = slider._strategy_slider_art.knob.pos
        instructions = tuple(map(id, slider._strategy_slider_art.group.children))
        slider.value = 30
        self.assertGreater(slider._strategy_slider_art.knob.pos[0], before[0])
        self.assertEqual(slider.value, 30)
        self.assertEqual(tuple(map(id, slider._strategy_slider_art.group.children)), instructions)

    def test_event_queue_is_clipped_and_disposed_without_delayed_retries(self):
        Window.size = (640, 360)
        screen = FloatLayout()
        screen.resource_box = SimpleNamespace(width=dp(136))
        self.host.add_widget(screen)
        queue = EventQueue(screen)
        queue.push('Длинное описание события ' * 30, 'passive')
        queue.push('Следующее событие', 'active')
        settle(5)
        first = queue.active
        self.assertGreaterEqual(len(queue.pending), 1)
        self.assertGreaterEqual(first.y, dp(70))
        self.assertLess(first.width, Window.width)
        first.finish()
        self.assertNotEqual(queue.active, first)
        self.host.remove_widget(screen)
        self.assertIsNone(queue.active)
        self.assertFalse(first.events)

    def test_real_market_keeps_ratio_in_price_card_and_uses_styled_slider(self):
        tree = ast.parse((ROOT / 'economic.py').read_text(encoding='utf-8'))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'open_trade_popup')
        namespace = dict(fixture_globals, platform='android', CheckBox=CheckBox)
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'economic.py', 'exec'), namespace)
        game = SimpleNamespace(get_resources=lambda: None, generate_raw_material_price=lambda: None,
                               current_raw_material_price=200, _get_trade_bonus=lambda: 1,
                               resources={'Кроны': 10000, 'Кристаллы': 1000},
                               get_available_raw_material_lots=lambda: 10, raw_material_price_history=[180, 200])
        namespace[node.name](game)
        settle()
        popup = next(w for w in Window.children if isinstance(w, Popup))
        labels = [w for w in popup.content.walk() if isinstance(w, Label)]
        price = next(w for w in labels if 'Цена 1 лота' in w.text)
        ratio = next(w for w in labels if 'Соотношение:' in w.text)
        self.assertIs(price.parent, ratio.parent)
        slider = next(w for w in popup.content.walk() if isinstance(w, Slider))
        self.assertTrue(hasattr(slider, '_strategy_slider_art'))
        slider.value = 5
        info = next(w for w in labels if 'Купить 500' in w.text)
        self.assertIn(format_number(1000), info.text)
