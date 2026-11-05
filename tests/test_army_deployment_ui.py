"""Reserve layout stays compact on phones and quantity controls obey army limits."""
import sqlite3
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from strategy_ui_fixture import Window
from kivy.base import EventLoop
from kivy.metrics import Metrics, dp
from army_deployment_ui import show_army_reserve, show_deployment_quantity


def settle():
    for _ in range(10):
        time.sleep(.015)
        EventLoop.idle()


class DeploymentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from window_theme import install_window_theme
        install_window_theme()

    def setUp(self):
        self.original_size = Window.size
        self.db = sqlite3.connect(':memory:')
        self.db.execute('CREATE TABLE units(unit_name, consumption)')
        self.db.execute("INSERT INTO units VALUES('Маг крови', 2)")
        self.owner = SimpleNamespace(city_name='Багровый замок', conn=self.db,
                                     add_to_garrison_with_slider=Mock(),
                                     transfer_army_to_garrison=Mock(),
                                     get_army_consumption_and_limit=lambda: (90, 100))
        self.row = ('Маг крови', 120, 70, 1, 2, '1', 'files/status/army.png')
        self.data = dict(unit_type='Маг крови', quantity=120)
        self.popups = []

    def tearDown(self):
        for popup in self.popups:
            popup.dismiss(animation=False)
        Metrics.density = 1
        Metrics.fontscale = 1
        Window.size = self.original_size
        settle()
        self.db.close()

    def test_cards_on_phone_rotation_and_desktop(self):
        popup = show_army_reserve(self.owner, [self.row] * 12)
        self.popups.append(popup)
        for density, size, columns in [(1, (640, 360), 1), (1, (392, 844), 1),
                                       (1, (1840, 940), 3), (2.5, (1280, 576), 1)]:
            Metrics.density = density
            Window.size = size
            if density != 1:
                popup.dismiss(animation=False)
                popup = show_army_reserve(self.owner, [self.row] * 12)
                self.popups.append(popup)
            settle()
            self.assertEqual(popup.cards.cols, columns)
            if size[0] < 1000 or density > 1:
                self.assertGreater(popup.cards.height, popup.list_scroll.height)
            for card in popup.cards.children:
                self.assertLess(card.height, dp(280))
                button = card.add_button
                self.assertGreaterEqual(button.height, dp(48))
                self.assertGreaterEqual(button.y, card.y)
                self.assertLessEqual(button.top, card.top)
                self.assertLessEqual(card.art.right, card.name_label.x)
                if card.orientation == 'horizontal':
                    self.assertGreaterEqual(button.x, card.count_label.right)
                else:
                    self.assertGreaterEqual(card.count_label.y, button.top)
                self.assertLessEqual(card.name_label.texture_size[1], card.name_label.height + 1)
        card = popup.cards.children[0]
        card.add_button.dispatch('on_release')
        self.owner.add_to_garrison_with_slider.assert_called_once_with(card.unit_data, card.add_button)

    def test_quantity_shortcuts_and_confirm_respect_limit(self):
        Window.size = (640, 360)
        popup = show_deployment_quantity(self.owner, self.data)
        self.popups.append(popup)
        settle()
        self.assertEqual(popup.slider.max, 5)
        popup.quick_buttons.children[0].dispatch('on_release')
        self.assertEqual(popup.slider.value, 5)
        popup.quantity_controls.children[-1].dispatch('on_release')
        self.assertEqual(popup.slider.value, 4)
        self.assertGreaterEqual(popup.confirm_button.height, dp(48))
        popup.confirm_button.dispatch('on_release')
        self.owner.transfer_army_to_garrison.assert_called_once_with(self.data, 4)

    def test_large_text_and_long_unit_names_grow_without_overlapping_actions(self):
        Metrics.fontscale = 1.5
        Window.size = (392, 844)
        row = ('Ветераны багрового ордена древних хранителей', *self.row[1:])
        popup = show_army_reserve(self.owner, [row])
        self.popups.append(popup)
        settle()
        card = popup.cards.children[0]
        self.assertGreaterEqual(card.name_label.height, card.name_label.texture_size[1])
        self.assertGreaterEqual(card.count_label.y, card.add_button.top)
        self.assertLessEqual(card.name_label.top, card.top)

    def test_full_army_cannot_deploy_even_one_unit(self):
        self.owner.get_army_consumption_and_limit = lambda: (100, 100)
        popup = show_deployment_quantity(self.owner, self.data)
        self.popups.append(popup)
        settle()
        self.assertTrue(popup.confirm_button.disabled)
        popup.confirm_button.dispatch('on_release')
        self.owner.transfer_army_to_garrison.assert_not_called()

    def test_single_reserve_unit_deploys_without_quantity_dialog(self):
        self.data['quantity'] = 1
        with patch('army_deployment_ui.Popup') as popup:
            self.assertIsNone(show_deployment_quantity(self.owner, self.data))
        popup.assert_not_called()
        self.owner.transfer_army_to_garrison.assert_called_once_with(self.data, 1)

    def test_single_unit_still_requires_free_army_capacity(self):
        self.data['quantity'] = 1
        self.owner.get_army_consumption_and_limit = lambda: (100, 100)
        with patch('army_deployment_ui.Popup') as popup, patch('ui_components.show_message') as message:
            self.assertIsNone(show_deployment_quantity(self.owner, self.data))
        popup.assert_not_called()
        message.assert_called_once()
        self.owner.transfer_army_to_garrison.assert_not_called()


if __name__ == '__main__':
    unittest.main()
