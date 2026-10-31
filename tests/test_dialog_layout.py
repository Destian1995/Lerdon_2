import time
import unittest

from dialog700_fixture import market, taxes, equipment, council_event, crafting
from strategy_ui_fixture import Window, dp, sp, city_fixture
from kivy.base import EventLoop
from kivy.metrics import Metrics
from kivy.uix.button import Button
from kivy.uix.popup import Popup
from kivy.uix.slider import Slider
from kivy.uix.scrollview import ScrollView
from window_theme import install_window_theme
from recruitment_ui import RecruitmentSession
from types import SimpleNamespace


def settle():
    for _ in range(12):
        time.sleep(.015)
        EventLoop.idle()


class DialogLayoutTests(unittest.TestCase):
    def setUp(self):
        self.original = Popup.open
        self.size = Window.size
        self.metrics = Metrics.density, Metrics.fontscale
        install_window_theme()

    def tearDown(self):
        for popup in list(Window.children):
            if isinstance(popup, Popup):
                popup.dismiss(animation=False)
        Popup.open = self.original
        Metrics.density, Metrics.fontscale = self.metrics
        Window.size = self.size
        settle()

    def visible(self, button, popup):
        self.assertGreaterEqual(button.x + 1, popup.x)
        self.assertGreaterEqual(button.y + 1, popup.y)
        self.assertLessEqual(button.right, popup.right + 1)
        self.assertLessEqual(button.top, popup.top + 1)
        self.assertGreaterEqual(button.height, dp(48) - 1)
        parent = button.parent
        while parent and parent is not popup:
            self.assertNotIsInstance(parent, ScrollView, button.text)
            parent = parent.parent

    def test_market_tax_and_council_actions_are_pinned_at_phone_metrics(self):
        for size, density, scale in (((640, 360), 1, 1), ((1280, 576), 2, 1.2), ((360, 640), 1, 1)):
            Metrics.density, Metrics.fontscale = density, scale
            Window.size = size
            settle()
            for show, captions in ((market, {'Купить', 'Продать'}), (taxes, {'Применить'}),
                                   (council_event, {'Провести', 'Отмена'})):
                db = show()
                popup = next(w for w in Window.children if isinstance(w, Popup))
                try:
                    settle()
                    buttons = [w for w in popup.content.walk() if isinstance(w, Button) and w.text in captions]
                    self.assertEqual({w.text for w in buttons}, captions)
                    for button in buttons:
                        self.visible(button, popup)
                    if show in (market, taxes):
                        slider = next(w for w in popup.content.walk() if isinstance(w, Slider))
                        _, y = slider.to_window(slider.x, slider.y)
                        self.assertGreaterEqual(y + 1, popup._window_action_dock.top)
                        self.assertLessEqual(y + slider.height, popup._window_flow.top + 1)
                finally:
                    popup.dismiss(animation=False)
                    if db:
                        db.close()

    def test_equipment_slots_stats_and_portrait_fit_without_outer_scroll(self):
        for size, density, scale in (((1280, 576), 1, 1), ((640, 360), 1, 1),
                                     ((360, 640), 1, 1), ((1280, 576), 2, 1.2)):
            Metrics.density, Metrics.fontscale = density, scale
            Window.size = size
            settle()
            equipment()
            popup = next(w for w in Window.children if isinstance(w, Popup))
            try:
                settle()
                panel = popup.hero_panel
                widgets = [popup.hero_portrait, popup.hero_stats, *popup.equipment_slots.values(), *popup.slot_labels.values()]
                for widget in widgets:
                    self.assertGreaterEqual(widget.y, panel.y - 1)
                    self.assertLessEqual(widget.top, panel.top + 1)
                    self.assertGreaterEqual(widget.x, panel.x - 1)
                    self.assertLessEqual(widget.right, panel.right + 1)
                self.assertLessEqual(popup._window_flow.body.height, popup._window_flow.height + 1)
                self.assertGreaterEqual(popup.inventory_scroll.height, dp(70))
            finally:
                popup.dismiss(animation=False)

    def test_recruitment_stats_portrait_and_controls_remain_visible_at_android_scale(self):
        from kivy.uix.floatlayout import FloatLayout
        for size, density in (((640, 360), 1), ((1280, 576), 2)):
            Metrics.density, Metrics.fontscale = density, 1.2
            Window.size = size
            settle()
            units = {'Паладины': dict(image='files/army/adepts/paladin.jpg', cost=(150, 2),
                        stats={'Класс юнита': '1 класс', 'Урон': 145, 'Защита': 320,
                               'Живучесть': 210, 'Потребление Кристаллов': 5})}
            host = FloatLayout()
            Window.add_widget(host)
            session = RecruitmentSession('Адепты', SimpleNamespace(class_faction=SimpleNamespace(
                get_resource_now=lambda name: 50000)), units, lambda *args: None)
            host.add_widget(session)
            try:
                session.open()
                settle()
                card = session.cards[0]
                self.assertLess(card.stat_grid.x, card.portrait.x)
                self.assertGreaterEqual(card.portrait.height, dp(90))
                for row, caption, value in card.stat_rows:
                    self.assertGreaterEqual(row.y, card.controls.top)
                    self.assertLessEqual(row.top, card.top)
                    self.assertGreaterEqual(caption.font_size, sp(15))
                    self.assertGreaterEqual(value.font_size, sp(20))
                for button in card.controls.children:
                    if isinstance(button, Button) and button.text.strip():
                        self.visible(button, session.popup)
            finally:
                session.release()
                Window.remove_widget(host)

    def test_garrison_unit_card_has_one_header_cross_and_no_bottom_close(self):
        Window.size = (640, 360)
        owner, db = city_fixture(populated=True)
        try:
            owner._show_unit_stats_popup('Страж', 20, 15, 30, 100, '1', 'files/army/people/vlad.jpg')
            popup = next(w for w in Window.children if isinstance(w, Popup))
            settle()
            buttons = [w for w in popup.content.walk() if isinstance(w, Button)]
            self.assertEqual([w.text for w in buttons], ['×'])
            self.visible(buttons[0], popup)
            self.assertGreater(buttons[0].y, popup.center_y)
        finally:
            db.close()

    def test_market_trade_callback_uses_selected_quantity(self):
        calls = []
        market(calls)
        popup = next(w for w in Window.children if isinstance(w, Popup))
        slider = next(w for w in popup.content.walk() if isinstance(w, Slider))
        slider.value = -3
        button = next(w for w in popup.content.walk() if isinstance(w, Button) and w.text == 'Продать')
        button.dispatch('on_release')
        self.assertEqual(calls[0][1:3], ('sell', 3))

    def test_crafting_all_stages_keep_navigation_and_create_action_visible(self):
        Window.size = (640, 360)
        crafting()
        popup = next(w for w in Window.children if isinstance(w, Popup))
        for stage in range(3):
            settle()
            buttons = [w for w in popup._window_action_dock.walk() if isinstance(w, Button)]
            self.assertGreaterEqual(len(buttons), 2)
            for button in buttons:
                self.visible(button, popup)
            if stage < 2:
                next(w for w in buttons if 'Далее' in w.text).dispatch('on_release')


if __name__ == '__main__':
    unittest.main()
