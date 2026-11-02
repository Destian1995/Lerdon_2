import ast
import sqlite3
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from strategy_ui_fixture import *
from strategy_ui_fixture import __dict__ as fixture_globals
from kivy.base import EventLoop
from kivy.uix.spinner import Spinner
from kivy.animation import Animation
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from frontend_ui import MenuButton, FactionChoice
from strategy_ui import StrategyButton
from window_theme import install_window_theme, theme_tree


def settle():
    for _ in range(15):
        time.sleep(0.015)
        EventLoop.idle()


def frontend_classes():
    tree = ast.parse((ROOT / 'main.py').read_text(encoding='utf-8'))
    names = {'LoadingScreen', 'MenuWidget', 'KingdomSelectionWidget', 'TutorialFactionScreen', 'AuthorScreen',
             'ModernButton', 'RoundedButton', 'GameButton', 'FactionButton', 'DossierScreen', 'Lor'}
    nodes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name in names]
    namespace = dict(fixture_globals, MDFloatLayout=FloatLayout, Spinner=Spinner,
                     TabbedPanel=TabbedPanel, TabbedPanelItem=TabbedPanelItem,
                     MenuButton=MenuButton, FactionChoice=FactionChoice, StrategyButton=StrategyButton)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'main.py', 'exec'), namespace)
    return namespace


class FrontendTests(unittest.TestCase):
    def setUp(self):
        self.original_size = Window.size
        Window.size = (640, 360)
        settle()
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE diplomacies_default(faction1 TEXT)')
        self.db.executemany('INSERT INTO diplomacies_default VALUES (?)', [(name,) for name in ('Север', 'Эльфы', 'Адепты', 'Вампиры', 'Элины')])
        self.classes = frontend_classes()
        self.widgets = []

    def show(self, name):
        widget = self.classes[name](self.db)
        self.widgets.append(widget)
        Window.add_widget(widget)
        settle()
        return widget

    def tearDown(self):
        for widget in self.widgets:
            if widget.parent:
                widget.parent.remove_widget(widget)
        self.db.close()
        Window.size = self.original_size
        settle()

    def test_main_menu_all_routes_use_shared_buttons_and_version(self):
        menu = self.show('MenuWidget')
        self.assertEqual(len(menu.buttons), 6)
        self.assertTrue(all(isinstance(b, StrategyButton) and b.height >= 48 for b in menu.buttons))
        self.assertTrue(any(isinstance(w, Label) and w.text == 'v7.0.7' for w in menu.walk()))
        self.assertIsNone(menu._particle_event)
        self.assertEqual(menu.button_container.cols, 2)
        Window.size = (360, 640)
        settle()
        self.assertEqual(menu.button_container.cols, 1)

    def test_campaign_setup_retains_actual_selection_and_options(self):
        app = SimpleNamespace(selected_kingdom=None)
        with patch('kivy.app.App.get_running_app', return_value=app):
            setup = self.show('KingdomSelectionWidget')
            self.assertEqual(app.selected_kingdom, 'Вампиры')
            setup.kingdom_button_widgets['Эльфы'].dispatch('on_release')
            self.assertEqual(app.selected_kingdom, 'Эльфы')
            self.assertTrue(setup.kingdom_button_widgets['Эльфы'].selected)
            setup.ideology_spinner.text = 'Борьба'
            setup.allies_spinner.text = '2'
            self.assertEqual(setup.selected_ideology, 'Борьба')
            self.assertEqual(setup.selected_allies, 2)
            self.assertFalse(setup.start_game_button.disabled)
            setup.disable_all_buttons(True)
            self.assertTrue(setup.ideology_spinner.disabled)
            self.assertTrue(setup.start_game_button.disabled)

    def test_loading_text_and_meter_remain_stable_through_progress_and_resize(self):
        # Use the actual loading widget without running startup against any database.
        from frontend_ui import Meter
        cls = self.classes['LoadingScreen']
        with patch.object(cls, 'start_loading'):
            loading = self.show('LoadingScreen')
            loading.tip_label.text = loading.TIPS[0]
            for size in ((1280, 576), (640, 360), (360, 640), (640, 360)):
                Window.size = size
                settle()
                page = loading._front_page
                self.assertGreaterEqual(page.column.height, page.flow.height)
                self.assertAlmostEqual(page.flow.width, loading.width - dp(24), delta=1)
                self.assertAlmostEqual(page.header.top, page.column.top - page.column.padding[1], delta=1)
                self.assertTrue(all(label.halign == 'center' for label in page.header.children))
                self.assertGreaterEqual(loading.label.y, loading.percent_label.top)
                self.assertGreaterEqual(loading.percent_label.y, loading.pb_container.top)
                geometry = (tuple(page.flow.size), page.column.height, loading.tip_label.height)
                self.assertLess(loading.tip_label.height, dp(120))
                self.assertIsNone(loading.tip_label.text_size[1])
                self.assertIsInstance(loading.pb_container, Meter)
                instructions = tuple(loading.pb_container.canvas.children)
                for percent in (20, 60, 75, 99):
                    loading.current_progress = percent
                    loading.percent_label.text = f'{percent}%'
                    loading._draw_progress()
                    settle()
                    self.assertEqual(geometry, (tuple(page.flow.size), page.column.height, loading.tip_label.height))
                    self.assertEqual(instructions, tuple(loading.pb_container.canvas.children))
                    self.assertAlmostEqual(loading.pb_container.fill.size[0],
                                           loading.pb_container.width * percent / 100, delta=0.01)
            menu = self.show('MenuWidget')
            self.assertEqual(tuple(page.flow.size), tuple(menu._front_page.flow.size))

    def test_campaign_factions_and_selectors_are_visible_together_after_resize(self):
        with patch('kivy.app.App.get_running_app', return_value=SimpleNamespace(selected_kingdom=None)):
            setup = self.show('KingdomSelectionWidget')
            for size in ((800, 600), (640, 360), (360, 640), (320, 568), (1280, 720)):
                Window.size = size
                settle()
                controls = [*setup.kingdom_button_widgets.values(), setup.ideology_spinner,
                            setup.allies_spinner, setup.start_game_button, setup.back_btn]
                for widget in controls:
                    with self.subTest(size=size, text=widget.text):
                        left, bottom = widget.to_window(*widget.pos)
                        right, top = widget.to_window(widget.right, widget.top)
                        self.assertGreaterEqual(bottom, setup.y - 1)
                        self.assertLessEqual(top, setup.top + 1)
                        self.assertGreaterEqual(left, setup.x - 1)
                        self.assertLessEqual(right, setup.right + 1)
                        self.assertGreaterEqual(widget.height, dp(48))
                self.assertGreaterEqual(setup.campaign_columns.factions.y,
                                        setup.campaign_columns.controls.top)

    def test_tutorial_and_author_share_components(self):
        tutorial = self.show('TutorialFactionScreen')
        self.assertTrue(tutorial.start_btn.disabled)
        tutorial._faction_btns['Север'].dispatch('on_release')
        self.assertEqual(tutorial.selected_faction, 'Север')
        self.assertFalse(tutorial.start_btn.disabled)
        author = self.show('AuthorScreen')
        self.assertTrue(any(isinstance(w, StrategyButton) and w.text == 'В меню' for w in author.walk()))

    def test_tutorial_keeps_all_factions_and_start_visible_after_resize(self):
        from kivy.metrics import Metrics
        original_metrics = Metrics.density, Metrics.fontscale
        tutorial = self.show('TutorialFactionScreen')
        try:
            for size, density in (((800, 600), 1), ((640, 360), 1), ((360, 640), 1),
                                  ((320, 568), 1), ((1280, 576), 2)):
                Metrics.density, Metrics.fontscale = density, 1.2
                Window.size = size
                settle()
                for button in [*tutorial._faction_btns.values(), tutorial.start_btn, tutorial.tutorial_back_button]:
                    with self.subTest(size=size, faction=button.text):
                        left, bottom = button.to_window(*button.pos)
                        right, top = button.to_window(button.right, button.top)
                        self.assertGreaterEqual(bottom, -1)
                        self.assertLessEqual(top, Window.height + 1)
                        self.assertGreaterEqual(left, -1)
                        self.assertLessEqual(right, Window.width + 1)
                for name, button in tutorial._faction_btns.items():
                    button.dispatch('on_release')
                    self.assertEqual(tutorial.selected_faction, name)
                    self.assertEqual(tutorial.tutorial_selection_label.text, name)
                    self.assertEqual(tutorial.tutorial_ideology_label.text, tutorial.FACTION_HINT[name])
                    self.assertFalse(tutorial.start_btn.disabled)
        finally:
            Metrics.density, Metrics.fontscale = original_metrics

    def test_button_motion_finishes_and_does_not_change_geometry(self):
        button = StrategyButton(size=(180, 52), size_hint=(None, None))
        Window.add_widget(button)
        geometry = (tuple(button.pos), tuple(button.size))
        button.state = 'down'
        settle()
        self.assertGreater(button._motion.level, 0.95)
        button.state = 'normal'
        settle()
        self.assertLess(button._motion.level, 0.05)
        self.assertEqual(geometry, (tuple(button.pos), tuple(button.size)))
        Window.remove_widget(button)
        self.assertEqual(button._motion.level, 0)

    def test_development_overlay_does_not_cover_real_card_labels(self):
        from kivy.uix.floatlayout import FloatLayout
        card = FloatLayout()
        label = Label(text='Рост населения')
        overlay = Button(text='', background_color=(0, 0, 0, 0))
        card.add_widget(label)
        card.add_widget(overlay)
        theme_tree(card)
        self.assertTrue(overlay._strategy_hit_region)
        self.assertFalse(hasattr(overlay, '_window_button_skin'))
        self.assertEqual(overlay.background_color[3], 0)

    def test_advisor_dismiss_removes_owner_once_without_reopening(self):
        tree = ast.parse((ROOT / 'ai_models/advisor_view.py').read_text(encoding='utf-8'))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AdvisorView')
        methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in ('_dispose', '_remove_owner', 'on_parent')]
        ns = dict(fixture_globals)
        exec(compile(ast.Module(body=methods, type_ignores=[]), 'advisor_view.py', 'exec'), ns)
        owner_type = type('AdvisorFixture', (FloatLayout,), {n.name: ns[n.name] for n in methods})
        owner = owner_type()
        owner._closed = False
        calls = []
        owner.diplomacy_chat = SimpleNamespace(dispose=lambda: calls.append('dispose'))
        host = FloatLayout()
        host.add_widget(owner)
        owner._dispose()
        owner._dispose()
        settle()
        self.assertEqual(calls, ['dispose'])
        self.assertIsNone(owner.parent)
        self.assertEqual(host.children, [])
