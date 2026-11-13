import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
import premium_access as access


class PremiumAccessTests(unittest.TestCase):
    def setUp(self):
        developer=patch('developer_access.enabled',return_value=False)
        developer.start();self.addCleanup(developer.stop)

    def test_local_developer_mode_unlocks_without_contacting_billing(self):
        with patch('developer_access.enabled',return_value=True), \
             patch('billing_flow.get_billing_controller') as billing:
            self.assertTrue(access.full_access())
            for feature in access.PAID_FEATURES:self.assertTrue(access.allowed(feature))
            self.assertTrue(access.allowed('faction','Север'))
            billing.assert_not_called()

    def test_free_factions_and_basic_features_without_license(self):
        with patch.object(access,'full_access',return_value=False):
            for faction in ('Эльфы','Вампиры','Адепты'):
                self.assertTrue(access.allowed('faction',faction))
            for faction in ('Север','Элины','Нежить'):
                self.assertFalse(access.allowed('faction',faction))
            for feature in access.PAID_FEATURES:self.assertFalse(access.allowed(feature))
            for feature in ('quick_battle','trade','reconnaissance','load_save'):
                self.assertTrue(access.allowed(feature))

    def test_license_unlocks_all_paid_features(self):
        with patch.object(access,'full_access',return_value=True):
            for feature in access.PAID_FEATURES:self.assertTrue(access.allowed(feature))
            self.assertTrue(access.allowed('faction','Север'))

    def test_only_verified_client_access_is_used_and_errors_fail_closed(self):
        from kivy.app import App
        controller=SimpleNamespace(client=Mock())
        with patch.object(App,'get_running_app',return_value=object()),patch('billing_flow.get_billing_controller',return_value=controller):
            controller.client.access.return_value=None
            self.assertFalse(access.full_access())
            controller.client.access.return_value={'permanent':True}
            self.assertTrue(access.full_access())
            controller.client.access.side_effect=RuntimeError('invalid signature')
            self.assertFalse(access.full_access())

    def test_denied_action_shows_notice_without_granting_access(self):
        with patch.object(access,'full_access',return_value=False),patch('premium_options_ui.show_locked_content') as popup:
            self.assertFalse(access.require('mirror'))
            popup.assert_called_once()
            self.assertTrue(access.require('faction','Эльфы'))
            popup.assert_called_once()

    def test_portal_denial_never_enters_and_existing_party_can_return(self):
        import otherworld_ui as portal
        city=SimpleNamespace(conn=object(),player_fraction='Север')
        with patch.object(portal,'_busy',return_value=False),patch.object(access,'full_access',return_value=False), \
             patch.object(portal.worlds,'party',return_value=None) as party, \
             patch('portal_entry_ui.PortalEntryPopup') as preview, \
             patch.object(portal.worlds,'enter') as enter, \
             patch.object(access,'return_from_mirror') as returning:
            portal.open_portal(city)
            enter.assert_not_called();preview.return_value.open.assert_called_once();returning.assert_not_called()
            party.return_value={'source':'Дом'}
            portal.open_portal(city)
            returning.assert_called_once_with(city.conn,'Север')
            enter.assert_not_called()


if __name__=='__main__':unittest.main()
