import unittest
from unittest.mock import Mock
from types import SimpleNamespace
from billing_flow import BillingController


class BillingFlowTests(unittest.TestCase):
    def setUp(self):
        self.callbacks=[];self.client=Mock()
        self.client.config={'test_mode':True,'sdk_key':'sdk-key'}
        self.client.pending={'request_id':'session','stage':'checking'}
        self.client.access.return_value=None
        self.native=Mock()
        self.controller=BillingController(self.client,self.native,
            schedule=lambda fn,delay=0:self.callbacks.append(fn),run=lambda fn:fn())

    def tick(self):self.callbacks.pop(0)()

    def test_confirmation_launches_sdk_but_does_not_grant_access(self):
        self.client.check_order.return_value={'status':'pending','confirmation_url':'https://yoomoney.ru/confirmation'}
        self.controller.check();self.tick()
        self.native.confirm.assert_called_once()
        self.client.refresh_access.assert_not_called()

    def test_gift_activation_without_android_payment_sdk_notifies_views(self):
        self.controller.native=None
        self.controller.redeem_gift('gift-key','test@example.org')
        self.client.redeem_gift.assert_called_once_with('gift-key','test@example.org')
        self.assertTrue(self.controller.busy)
        self.tick()
        self.assertFalse(self.controller.busy)
        self.assertIn('Ключ принят',self.controller.message)
        self.assertIn('ТЕСТОВЫЙ',self.controller.message)

    def test_sdk_confirmation_result_always_rechecks_server(self):
        self.client.check_order.return_value={'status':'succeeded'}
        self.controller.native_event({'session':'session','type':'confirmation'});self.tick()
        self.client.check_order.assert_called_once()

    def test_old_sdk_callback_cannot_act_on_current_order(self):
        self.controller.native_event({'session':'old-session','type':'token','payment_token':'t'})
        self.client.token_received.assert_not_called();self.assertFalse(self.controller.busy)

    def test_double_click_does_not_start_second_request(self):
        self.client.check_order.return_value={'status':'pending'}
        self.controller.check();self.controller.check()
        self.client.check_order.assert_called_once()

    def test_unexpected_error_keeps_pending_and_never_exposes_exception_text(self):
        pending=self.client.pending.copy()
        self.client.check_order.side_effect=RuntimeError('SECRET-payment-token')
        self.controller.check();self.tick()
        self.assertEqual(self.client.pending,pending)
        self.assertIn('RuntimeError',self.controller.message)
        self.assertNotIn('SECRET',self.controller.message)
        self.native.tokenize.assert_not_called()


if __name__=='__main__':unittest.main()
