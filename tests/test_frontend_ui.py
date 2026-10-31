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
    names = {'MenuWidget', 'KingdomSelectionWidget', 'TutorialFactionScreen', 'AuthorScreen',
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
        self.assertTrue(any(isinstance(w, Label) and w.text == 'v6.7.0' for w in menu.walk()))
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

    def test_tutorial_and_author_share_components(self):
        tutorial = self.show('TutorialFactionScreen')
        self.assertTrue(tutorial.start_btn.disabled)
        tutorial._faction_btns['Север'].dispatch('on_release')
        self.assertEqual(tutorial.selected_faction, 'Север')
        self.assertFalse(tutorial.start_btn.disabled)
        author = self.show('AuthorScreen')
        self.assertTrue(any(isinstance(w, StrategyButton) and w.text == 'В меню' for w in author.walk()))

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
