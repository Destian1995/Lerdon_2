import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from rebel_attack_ui import RebelAttackMap
from rebel_orders import issue_order
from kivy.metrics import Metrics


class RebelMapTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)
        self.size=Window.size;self.density=Metrics.density
        self.db.executescript('''CREATE TABLE diplomacies(faction1,faction2,relationship);
            CREATE TABLE roads(city1,city2);
            UPDATE cities SET faction='Мятежники' WHERE name='Home';
            INSERT INTO cities VALUES(3,'Enemy','Вампиры','[600,400]');
            INSERT INTO roads VALUES(1,3);''')
        self.popup=None

    def tearDown(self):
        if self.popup:self.popup.dismiss(animation=False)
        Window.size=self.size;Metrics.density=self.density;settle()

    def test_map_targets_and_confirmation_fit_small_screens(self):
        callback=Mock();self.popup=RebelAttackMap(self.db,'Север',on_order=callback)
        self.popup.open(animation=False)
        for size,density in [((1280,576),1),((640,360),1),((320,240),1),((390,844),1),((1280,576),2)]:
            with self.subTest(size=size,density=density):
                Metrics.density=density;Window.size=size;settle();self.popup.draw();settle()
                for button in (self.popup.confirm,self.popup.scroll):
                    self.assertGreaterEqual(button.y,self.popup.layout.y-1)
                    self.assertLessEqual(button.top,self.popup.layout.top+1)
                self.assertFalse(self.popup.nodes['Enemy'][1].disabled)
                self.assertTrue(self.popup.nodes['Safe'][1].disabled)
                self.assertGreaterEqual(self.popup.nodes['Enemy'][1].width,40*density)
        self.popup.select('Enemy')
        self.assertFalse(self.popup.confirm.disabled)
        self.popup.submit()
        callback.assert_called_once_with('Enemy','Вампиры')
        self.assertEqual(self.db.execute('SELECT target_city FROM rebel_attack_order').fetchone()[0],'Enemy')

    def test_cancel_and_stale_target_do_not_issue_orders(self):
        self.popup=RebelAttackMap(self.db,'Север');self.popup.select('Enemy')
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Enemy'")
        self.popup.submit()
        self.assertTrue(self.popup.confirm.disabled)
        self.assertIsNone(self.db.execute("SELECT name FROM sqlite_master WHERE name='rebel_attack_order'").fetchone())
        with self.assertRaises(ValueError):issue_order(self.db,'Север','Safe')

    def test_current_map_background_is_reused_and_zoom_does_not_write_coordinates(self):
        from rebel_attack_ui import current_map_source
        screen=SimpleNamespace(conn=self.db,parent=SimpleNamespace(children=[SimpleNamespace(random_map_source='files/map/generate/map_1.png')]))
        before=list(self.db.execute('SELECT coordinates FROM cities'))
        with patch.dict(sys.modules,{'game_process':SimpleNamespace(_active_game_screen=screen)}):
            self.assertEqual(current_map_source(self.db),'files/map/generate/map_1.png')
        self.popup=RebelAttackMap(self.db,'Север');self.popup.open(animation=False);settle()
        self.popup.set_zoom(1);settle()
        self.assertEqual(self.popup.zoom,2)
        self.assertEqual(before,list(self.db.execute('SELECT coordinates FROM cities')))
