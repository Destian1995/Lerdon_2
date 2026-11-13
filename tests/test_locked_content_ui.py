import unittest
from unittest.mock import patch
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from premium_options_ui import LockedContentPopup


class LockedContentTests(unittest.TestCase):
    def setUp(self):
        self.size=Window.size
        self.addCleanup(setattr,Window,'size',self.size)
        self.popup=LockedContentPopup()
        self.popup.open(animation=False)
        self.popup._anim_duration=0
        self.addCleanup(self.popup.dismiss,animation=False)
        settle()

    def test_notice_and_touch_controls_fit_small_screens(self):
        for size in ((640,360),(320,240),(320,568)):
            Window.size=size
            # Hidden SDL test windows do not emit the native resize event.
            Window.dispatch('on_resize',*size)
            settle()
            popup=self.popup
            self.assertLessEqual(popup.width,Window.width)
            self.assertLessEqual(popup.height,Window.height)
            self.assertGreater(popup.message.height,25)
            for button in (popup.get_full,popup.close_button):
                self.assertGreaterEqual(button.height,48)
                self.assertGreaterEqual(button.y,popup.y)
                self.assertLessEqual(button.top,popup.top)

    def test_purchase_options_open_only_after_explicit_button_press(self):
        with patch('premium_options_ui.show_full_access') as purchase:
            settle()
            purchase.assert_not_called()
            self.popup.get_full.dispatch('on_release');settle()
            purchase.assert_called_once_with()
            self.assertIsNone(self.popup.parent)

    def test_close_keeps_purchase_options_closed(self):
        with patch('premium_options_ui.show_full_access') as purchase:
            self.popup.close_button.dispatch('on_release');settle()
            purchase.assert_not_called()
            self.assertIsNone(self.popup.parent)
