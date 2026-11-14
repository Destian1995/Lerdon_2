import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from premium_options_ui import FullAccessPopup
from rewarded_access_ui import ExpiredAccessPopup


class RewardedUITests(unittest.TestCase):
    def setUp(self):
        self.old=Window.size
        self.addCleanup(setattr,Window,'size',self.old)
        self.controller=SimpleNamespace(bank=Mock(caption='14:32'),available=True,native=Mock(),
            session=None,message='',views=set(),watch=Mock(),expiry_popup=None)
        p=patch('rewarded_access.get_rewarded',return_value=self.controller)
        p.start();self.addCleanup(p.stop)
        p=patch('rewarded_access.paid_access',return_value=False)
        p.start();self.addCleanup(p.stop)

    def test_reward_controls_fit_landscape_and_portrait_and_require_explicit_tap(self):
        popup=FullAccessPopup()
        popup.open(animation=False);self.addCleanup(popup.dismiss,animation=False)
        for size in ((640,360),(320,568)):
            Window.size=size;settle()
            self.assertGreater(popup.scroll.height,45)
            self.assertGreaterEqual(popup.reward_button.height,48)
            self.assertGreaterEqual(popup.footer.y,popup.y)
            self.assertNotIn('full_monthly',popup.buy_buttons)
            self.assertIn('14:32',popup.reward_status.text)
        Window.size=(640,360);settle()
        popup.export_to_png('.release/rewarded-access-phone.png')
        self.controller.watch.assert_not_called()
        popup.reward_button.dispatch('on_release')
        self.controller.watch.assert_called_once()
        self.assertIn(popup,self.controller.views)
        popup.dismiss(animation=False)
        self.assertNotIn(popup,self.controller.views)

    def test_expired_paid_campaign_has_no_close_bypass(self):
        Window.size=(640,360)
        popup=ExpiredAccessPopup(self.controller,True)
        popup.open(animation=False);self.addCleanup(popup.dismiss,animation=False);settle()
        self.assertFalse(popup.auto_dismiss)
        buttons=[widget for widget in popup.content.children if hasattr(widget,'text')]
        self.assertTrue(any(widget.text=='Сохранить и выйти' for widget in buttons))
        self.assertFalse(any('бесплатными' in widget.text for widget in buttons))
        self.assertGreaterEqual(min(widget.y for widget in popup.content.children),popup.y)


if __name__=='__main__':unittest.main()
