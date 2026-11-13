import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import developer_access as developer


class DeveloperAccessTests(unittest.TestCase):
    def setUp(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        self.root=Path(directory.name)
        self.state=self.root/'developer_access.local.json'
        self.root.joinpath('.git').mkdir()
        for item in (patch.object(developer,'SOURCE_ROOT',self.root),
                     patch.object(developer,'STATE_FILE',self.state),
                     patch.object(developer,'_state',None),
                     patch.dict(os.environ,{k:v for k,v in os.environ.items()
                                if k not in ('ANDROID_ARGUMENT','ANDROID_PRIVATE')},clear=True)):
            item.start();self.addCleanup(item.stop)

    def test_defaults_off_and_explicit_switch_persists(self):
        self.assertTrue(developer.available())
        self.assertFalse(developer.enabled())
        developer.set_enabled(True)
        self.assertTrue(developer.enabled())
        self.assertEqual(json.loads(self.state.read_text()),{'full_access':True})
        developer._state=None
        self.assertTrue(developer.enabled())
        developer.set_enabled(False)
        self.assertFalse(developer.enabled())

    def test_android_ignores_checkout_settings_and_rejects_activation(self):
        developer.set_enabled(True)
        with patch.dict(os.environ,ANDROID_ARGUMENT='/data/user/0/game/files/app'):
            self.assertFalse(developer.available())
            self.assertFalse(developer.enabled())
            with self.assertRaises(ValueError):developer.set_enabled(True)

    def test_packaged_desktop_build_without_git_ignores_settings(self):
        developer.set_enabled(True)
        self.root.joinpath('.git').rmdir()
        self.assertFalse(developer.enabled())
        with self.assertRaises(ValueError):developer.set_enabled(True)

    def test_malformed_settings_and_string_values_do_not_unlock(self):
        for content in ('broken','[]','{"full_access":"true"}'):
            developer._state=None;self.state.write_text(content)
            self.assertFalse(developer.enabled())

    def test_menu_switch_actually_toggles_the_gate(self):
        from strategy_ui_fixture import Window
        button=developer.create_toggle()
        self.assertIn('выключен',button.text)
        button.dispatch('on_release')
        self.assertTrue(developer.enabled())
        self.assertIn('ВКЛЮЧЁН',button.text)
        button.dispatch('on_release')
        self.assertFalse(developer.enabled())

    def test_developer_purchase_screen_does_not_initialize_payment_service(self):
        from premium_options_ui import show_full_access
        developer.set_enabled(True)
        with patch('billing_flow.get_billing_controller') as billing:
            popup=show_full_access()
            self.addCleanup(popup.dismiss,animation=False)
            self.assertIn('РАЗРАБОТЧИКА',popup.status.text)
            self.assertIn('Покупка не оформлена',popup.status.text)
            billing.assert_not_called()
