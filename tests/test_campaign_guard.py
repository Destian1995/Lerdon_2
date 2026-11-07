from types import SimpleNamespace
from unittest.mock import Mock,patch
import unittest
from test_tactical_battle_ui import Window,settle
from kivy.uix.popup import Popup
from test_otherworlds import fixture
import otherworlds
from campaign_guard import finish_portal_campaign


class PortalDefeatPresentationTests(unittest.TestCase):
    def test_captured_portal_closes_mirror_windows_and_finishes_once(self):
        db=fixture();self.addCleanup(db.close)
        otherworlds.enter(db,'Север','Home')
        popup=Popup(title='Зазеркалье');popup.open(animation=False);settle()
        self.addCleanup(lambda:popup.dismiss(animation=False))
        db.execute("UPDATE cities SET faction='Эльфы' WHERE name='Home'")
        screen=SimpleNamespace(end_turn_button=SimpleNamespace(disabled=False),_turn_overlay=None)
        results=Mock()
        with patch.dict('sys.modules',{'results_game':SimpleNamespace(ResultsGame=results)}):
            self.assertTrue(finish_portal_campaign(db,'Север',screen))
            self.assertFalse(finish_portal_campaign(db,'Север',screen))
        self.assertTrue(screen._game_ended);self.assertTrue(screen.end_turn_button.disabled)
        self.assertIsNone(popup.parent)
        self.assertEqual(results.call_count,1)
        self.assertEqual(results.call_args.args[0],'lose')


if __name__=='__main__':unittest.main()
