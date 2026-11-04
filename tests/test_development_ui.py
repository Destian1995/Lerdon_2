import unittest
from types import SimpleNamespace
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_unique_development import fixture
from kivy.metrics import Metrics,dp
from development_ui import open_development


class DevelopmentTests(unittest.TestCase):
    def test_loyalty_gate_and_city_progress_fit_small_screens(self):
        original=Window.size,Metrics.density,Metrics.fontscale
        db=fixture();model=SimpleNamespace(conn=db,faction='Север')
        popup=open_development(model)
        try:
            for size,density in (((640,360),1),((1280,576),2),((320,568),1)):
                Window.size=size;Metrics.density=density;Metrics.fontscale=1.2;settle();popup.fit();settle()
                self.assertGreaterEqual(popup.actions.height,dp(44)-1)
                self.assertGreaterEqual(popup.actions.y,popup.root.y-1)
                self.assertLessEqual(popup.actions.top,popup.root.top+1)
                self.assertEqual(len(popup.city_rows.children),2)
                self.assertFalse(model.auto_build_enabled)
                self.assertIn('80.0%',popup.loyalty_label.text)
            db.execute("UPDATE nobles SET loyalty=81 WHERE status='active'");popup.refresh()
            self.assertTrue(model.auto_build_enabled)
            self.assertIn('работает',popup.loyalty_label.text)
            self.assertFalse(db.execute('SELECT 1 FROM buildings').fetchone())
        finally:
            popup.dismiss(animation=False);settle();db.close()
            Window.size,Metrics.density,Metrics.fontscale=original
