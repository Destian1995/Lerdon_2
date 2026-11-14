from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

from strategy_ui_fixture import Window
from test_dialog_layout import settle
from premium_options_ui import FullAccessPopup
from billing_client import BillingClient
from billing_flow import BillingController


class BillingUITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.size=Window.size;self.addCleanup(setattr,Window,'size',self.size)
        catalog=dict(currency='RUB',plans={'full_monthly':5500,'full_permanent':25000},test=True,subscriptions_available=False)
        def api(action,*args,**kwargs):
            if action=='catalog':return catalog
            if action=='register':return dict(account_id='a'*32,recovery_code='b'*64)
            raise AssertionError('Unexpected API action')
        config=dict(api_url='https://example.org/api.php',test_mode=True,sdk_key='sdk-test-key',shop_id='123',public_key='unused')
        self.client=BillingClient(Path(self.temp.name)/'state.json',config,api=api)
        self.native=Mock()
        self.controller=BillingController(self.client,self.native,schedule=lambda fn,delay=0:fn(),run=lambda fn:fn())
        self.popup=FullAccessPopup();self.popup.open(animation=False)
        self.addCleanup(self.popup.dismiss,animation=False)
        self.popup.attach_billing(self.controller);settle()

    def test_mobile_layout_keeps_footer_and_scrollable_purchase_controls(self):
        for size in ((640,360),(320,568)):
            Window.size=size;settle()
            self.assertGreaterEqual(self.popup.footer.height,48)
            self.assertGreater(self.popup.scroll.height,40)
            for button in self.popup.buy_buttons.values():self.assertGreaterEqual(button.height,48)
            self.assertNotIn('full_monthly',self.popup.buy_buttons)
            self.assertGreaterEqual(self.popup.reward_button.height,48)
            self.assertFalse(self.popup.buy_buttons['full_permanent'].disabled)

    def test_gift_input_is_usable_on_phone_and_activates_without_payment_sdk(self):
        self.controller.native=None
        self.client.validate_license=Mock(return_value=dict(account_id='a'*32,permanent=True,full_access=True,expires_at=0,auto_renew=False))
        def api(action,*args,**kwargs):
            if action=='register':return dict(account_id='a'*32,recovery_code='b'*64)
            if action=='redeem_gift':return {'signed':'test-fixture'}
            raise AssertionError(action)
        self.client.api=Mock(side_effect=api)
        Window.size=(640,360);settle()
        self.assertFalse(self.popup.gift_button.disabled)
        self.popup.gift_button.dispatch('on_release');settle()
        gift=self.popup.gift_popup;self.addCleanup(gift.dismiss,animation=False)
        gift.email_input.text='gift@example.org'
        gift.code_input.text='LERDON-'+ '-'.join(['ABCDEF01']*5)
        self.assertGreaterEqual(gift.submit_button.height,48)
        self.assertGreaterEqual(gift.submit_button.y,gift.y)
        gift.export_to_png('.release/gift-key-phone.png')
        gift.submit_button.dispatch('on_release');settle()
        self.assertIn('Ключ принят',self.popup.status.text)
        self.assertTrue(self.popup.gift_button.disabled)
        self.assertEqual(self.popup.buy_buttons['full_permanent'].text,'Полная версия открыта')
        self.native.tokenize.assert_not_called()

    def test_purchase_button_opens_sdk_once_and_exposes_recovery_copy_action(self):
        self.popup.email.text='test@example.org'
        self.popup.buy_buttons['full_permanent'].dispatch('on_release')
        self.native.tokenize.assert_called_once()
        self.assertTrue(self.popup.buy_buttons['full_permanent'].disabled)
        self.assertFalse(self.popup.copy_code.disabled)
        self.assertIn('Отменить подготовку',self.popup.check_button.text)
        self.assertNotIn('b'*64,self.popup.code_label.text)
        self.popup.check_button.dispatch('on_release')
        self.assertIsNone(self.client.pending)

    def test_verified_purchase_is_explicit_and_status_is_outside_scroll(self):
        from unittest.mock import patch
        with patch.object(self.client,'access',return_value={'permanent':True}):
            self.controller.message='';self.controller.notify()
        self.assertEqual(self.popup.buy_buttons['full_permanent'].text,'Полная версия открыта')
        self.assertTrue(self.popup.buy_buttons['full_permanent'].disabled)
        self.assertIn('подтверждена',self.popup.status.text)
        self.assertIs(self.popup.status.parent,self.popup.content)
        self.assertIs(self.popup.check_button.parent,self.popup.content)

    def test_unfinished_form_can_be_canceled_without_scrolling(self):
        self.popup.email.text='test@example.org'
        self.popup.start_purchase('full_permanent')
        self.controller.message='';self.controller.notify()
        self.assertIn('Оплата подготовлена',self.popup.status.text)
        self.assertIs(self.popup.check_button.parent,self.popup.content)
        self.assertFalse(self.popup.check_button.disabled)
        self.assertGreater(self.popup.email.disabled_foreground_color[0],.5)


if __name__=='__main__':unittest.main()
