import unittest
from types import SimpleNamespace
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_unique_development import fixture
from kivy.metrics import Metrics,dp
from development_ui import open_development
from city_construction import buy_building


class DevelopmentTests(unittest.TestCase):
    def test_each_city_warns_only_about_missing_economy_buildings_and_refreshes(self):
        db=fixture();popup=open_development(SimpleNamespace(conn=db,faction='Север'))
        try:
            self.assertIn('обязательны',popup.priority_hint.text)
            rows={row.text.split(' · ')[0]:row for row in popup.city_rows.children}
            self.assertIn('Обязательно постройте больницу и фабрику.',rows['A'].text)
            buy_building(db,'A','Север','Больница');popup.refresh()
            rows={row.text.split(' · ')[0]:row for row in popup.city_rows.children}
            self.assertIn('Обязательно постройте фабрику.',rows['A'].text)
            for city in ('A','B'):
                for kind in ('Больница','Фабрика'):
                    if not db.execute('SELECT 1 FROM buildings WHERE city_name=? AND building_type=?',(city,kind)).fetchone():
                        buy_building(db,city,'Север',kind)
            popup.refresh();settle()
            self.assertEqual(popup.priority_hint.text,'')
            self.assertTrue(all('Обязательно' not in row.text for row in popup.city_rows.children))
            self.assertTrue(all('Осталось:' in row.text for row in popup.city_rows.children))
        finally:
            popup.dismiss(animation=False);settle();db.close()

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
