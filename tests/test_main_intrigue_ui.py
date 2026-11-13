import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from kivy.metrics import Metrics,dp
from kivy.uix.popup import Popup
from test_main_map_intrigues import fixture
from main_intrigue_ui import MainIntriguesPopup,advisor_panel
import main_map_intrigues as plots


class MainIntrigueUITests(unittest.TestCase):
    def setUp(self):
        license=patch('premium_access.full_access',return_value=True)
        license.start();self.addCleanup(license.stop)
        self.db=fixture();self.size=Window.size;self.metrics=Metrics.density,Metrics.fontscale
        Metrics.density=Metrics.fontscale=1;Window.size=(1000,700)

    def test_unpaid_player_sees_secret_preview_but_cannot_apply_choice(self):
        from premium_options_ui import FullVersionNotice
        self.db.execute("INSERT INTO map_city_secrets(faction,city,kind,stage) VALUES('Север','Дом','factory',2)")
        with patch('premium_access.full_access',return_value=False):
            popup=MainIntriguesPopup(self.db,'Север','Дом');popup.open(animation=False);settle()
            self.assertTrue(any(isinstance(w,FullVersionNotice) for w in popup.body.children))
            before=list(self.db.iterdump())
            popup.controls[('secret','Дом','expose')].dispatch('on_release');settle()
            self.assertEqual(before,list(self.db.iterdump()))
            self.assertIn('полной версии',popup.notice.text)

    def tearDown(self):
        for p in list(Window.children):
            if isinstance(p,Popup):p.dismiss(animation=False)
        settle();self.db.close();Metrics.density,Metrics.fontscale=self.metrics;Window.size=self.size;settle()

    def test_phone_layout_scrolls_instead_of_clipping_choices_and_keeps_close_visible(self):
        plots.advance(self.db,'Север')
        self.db.execute("INSERT INTO map_city_secrets(faction,city,kind,stage) VALUES('Север','Дом','factory',2)")
        popup=MainIntriguesPopup(self.db,'Север','Дом');popup.open(animation=False);settle()
        for screen,density,scale in (((1000,700),1,1),((640,360),1,1),((1280,576),2,1.2),((320,568),1,1.2)):
            Window.size=screen;Metrics.density=density;Metrics.fontscale=scale;settle();popup.fit();settle()
            self.assertGreater(popup.scroll.height,dp(60))
            footer=popup.root.children[0]
            self.assertGreaterEqual(footer.y,popup.y)
            self.assertLessEqual(footer.top,popup.top)
            for button in popup.controls.values():
                self.assertGreaterEqual(button.height,dp(48)-1)
                self.assertGreater(button.width,dp(72))
            if screen==(640,360):popup.export_to_png('.release/main-intrigues-phone.png')
            if screen==(1000,700):popup.export_to_png('.release/tavern-desktop.png')

    def test_actual_secret_choice_sets_policy_once_and_rebuilds_buttons(self):
        self.db.execute("INSERT INTO map_city_secrets(faction,city,kind,stage) VALUES('Север','Дом','factory',2)")
        popup=MainIntriguesPopup(self.db,'Север','Дом');popup.open(animation=False);settle()
        button=popup.controls[('secret','Дом','expose')]
        screen=SimpleNamespace(refresh_map=Mock())
        with patch.dict('sys.modules',game_process=screen):
            button.dispatch('on_release');settle()
            button.dispatch('on_release');settle()
        self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE resource_type='Кроны'").fetchone()[0],100000)
        self.assertTrue(self.db.execute("SELECT 1 FROM buildings WHERE building_type='Фабрика'").fetchone())
        self.assertNotIn(('secret','Дом','expose'),popup.controls)
        self.assertIn('Сначала',popup.notice.text)

    def test_city_entry_and_advisor_entry_open_the_main_map_journal(self):
        from kivy.uix.widget import Widget
        panel=advisor_panel(SimpleNamespace(conn=self.db,selected_faction='Север'),Widget())
        panel.children[0].dispatch('on_release');settle()
        self.assertTrue(any(isinstance(p,MainIntriguesPopup) for p in Window.children))
        from strategy_ui_fixture import city_fixture
        Window.size=(640,360);settle()
        city,conn=city_fixture();self.addCleanup(conn.close)
        conn.execute("ALTER TABLE units ADD COLUMN faction TEXT")
        city.open(animation=False);settle();city.export_to_png('.release/main-city-intrigue-entry.png')
        city.city_action_buttons['intrigues'].dispatch('on_release');settle()
        popup=next(p for p in Window.children if isinstance(p,MainIntriguesPopup) and p.city=='Виндгар')
        self.assertEqual(popup.faction,'Адепты')

    def test_capture_choice_is_a_separate_phone_popup_and_citizens_only_talk(self):
        from city_capture_ui import present_capture
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Вражеский'")
        plots.captured(self.db,'Вражеский','Север',1)
        self.db.commit()
        tavern=MainIntriguesPopup(self.db,'Север',city='Вражеский');tavern.open(animation=False)
        tavern.select_category('citizens');settle()
        self.assertFalse(any(key[0]=='capture' for key in tavern.controls))
        popup=present_capture(self.db,'Север','Вражеский');settle()
        self.assertEqual(set(popup.buttons),{'spare','plunder'})
        self.assertIs(present_capture(self.db,'Север','Вражеский'),popup)
        for size in ((640,360),(320,568)):
            Window.size=size;settle();popup.fit();settle()
            self.assertGreater(popup.scroll.height,dp(60))
            for button in popup.buttons.values():
                self.assertGreaterEqual(button.height,dp(48))
                self.assertGreaterEqual(button.y,popup.y)
        popup.export_to_png('.release/enemy-city-capture-choice.png')
        screen=SimpleNamespace(refresh_map=Mock())
        with patch.dict('sys.modules',game_process=screen):
            popup.buttons['spare'].dispatch('on_release');settle()
            popup.choose('plunder')
        self.assertEqual(self.db.execute('SELECT status FROM map_intrigue_captures').fetchone()[0],'spare')
        self.assertIsNone(present_capture(self.db,'Север','Вражеский'))


if __name__=='__main__':unittest.main()
