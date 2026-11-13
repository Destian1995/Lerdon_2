import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from kivy.metrics import Metrics
from kivy.core.text import Label as CoreLabel
from strategy_ui_fixture import Window,hud_fixture,cleanup_hud
from test_dialog_layout import settle
from test_otherworlds import fixture
from portal_shortcut_ui import PortalShortcut
import otherworlds as worlds


class PortalShortcutTests(unittest.TestCase):
    def setUp(self):
        self.size=Window.size;self.density=max(1,Metrics.density)
        Metrics.density=1;Window.size=(800,600);settle()
        self.db=fixture()
        self.host=hud_fixture();self.host.portal_shortcut.close()
        self.host.conn=self.db;self.host.selected_faction='Север';self.host.faction_label.text='Север'
        self.host.portal_shortcut=PortalShortcut(self.host)
        self.shortcut=self.host.portal_shortcut
        self.screen_patch=patch.dict(sys.modules,game_process=SimpleNamespace(_active_game_screen=self.host))
        self.screen_patch.start()
        self.access_patch=patch('premium_access.allowed',return_value=True)
        self.access_patch.start()
        Window.add_widget(self.host);settle()

    def tearDown(self):
        cleanup_hud(self.host)
        if self.host.parent:Window.remove_widget(self.host)
        self.screen_patch.stop();self.db.close()
        self.access_patch.stop()
        Metrics.density=self.density;Window.size=self.size;settle()

    def enter(self):
        worlds.enter(self.db,'Север','Home')
        self.shortcut.refresh();settle()

    def test_only_visible_for_own_expedition_and_refresh_is_read_only(self):
        self.assertIsNone(self.shortcut.button.parent)
        self.enter()
        self.assertIsNotNone(self.shortcut.button.parent)
        before=list(self.db.iterdump())
        self.shortcut.refresh();settle()
        self.assertEqual(list(self.db.iterdump()),before)
        worlds.return_home(self.db,'Север')
        self.shortcut.refresh();settle()
        self.assertIsNone(self.shortcut.button.parent)

    def test_resume_opens_same_city_without_changing_party_resources_or_moves(self):
        self.enter()
        self.db.execute("UPDATE portal_parties SET city_id=3 WHERE faction='Север'");self.db.commit()
        before=(worlds.party(self.db,'Север'),list(self.db.execute('SELECT * FROM resources')),
                list(self.db.execute('SELECT * FROM turn_check_move')))
        self.shortcut.button.dispatch('on_release');settle()
        self.assertIsNotNone(self.shortcut.popup.parent)
        after=(worlds.party(self.db,'Север'),list(self.db.execute('SELECT * FROM resources')),
               list(self.db.execute('SELECT * FROM turn_check_move')))
        self.assertEqual(after,before)
        self.shortcut.popup.dismiss(animation=False);settle()
        self.assertTrue(self.shortcut.visible)

    def test_phone_android_density_and_portrait_keep_control_inside_hud(self):
        self.enter()
        for size,density in (((1920,1080),1),((640,360),1),((1280,576),2),((320,568),1),((392,844),1)):
            Window.size=size;Metrics.density=density;settle()
            self.host._hud_fit();self.shortcut.fit();settle()
            b=self.shortcut.button;overlay=self.host.root_overlay
            with self.subTest(size=size,density=density):
                self.assertGreaterEqual(b.width,48*density)
                self.assertGreaterEqual(b.height,48*density-20)
                self.assertGreaterEqual(b.x,overlay.x)
                self.assertGreaterEqual(b.y,overlay.y)
                self.assertLessEqual(b.right,overlay.right)
                self.assertLessEqual(b.top,overlay.top)
                self.assertFalse(b.collide_widget(self.host.resource_box))
                self.assertFalse(b.collide_widget(self.host.end_turn_button))
                end_button=self.host.end_turn_button
                measure=CoreLabel(text=end_button.text,font_name=end_button.font_name,
                                  font_size=end_button.font_size,bold=True)
                measure.refresh()
                self.assertLessEqual(measure.texture.width,end_button.width+1)
                self.assertLessEqual(measure.texture.height,end_button.height+1)

    def test_busy_turn_blocks_resume_and_detach_stops_polling(self):
        self.enter()
        self.host._troop_movement_busy=True
        self.shortcut.refresh()
        self.assertTrue(self.shortcut.button.disabled)
        self.shortcut.button.dispatch('on_release')
        self.assertIsNone(self.shortcut.popup)
        self.assertIsNotNone(self.shortcut._poll)
        Window.remove_widget(self.host);settle()
        self.assertIsNone(self.shortcut._poll)

    def test_turn_poll_never_touches_worker_connection_and_resumes(self):
        self.enter()
        original=self.host.conn
        from unittest.mock import Mock
        forbidden=Mock()
        forbidden.execute.side_effect=AssertionError('UI queried worker connection')
        self.host.conn=forbidden
        self.host._turn_overlay=object()
        self.shortcut.refresh()
        self.shortcut.open()
        forbidden.execute.assert_not_called()
        self.assertTrue(self.shortcut.button.disabled)
        self.host._turn_overlay=None
        self.host.conn=original
        self.shortcut.refresh()
        self.assertTrue(self.shortcut.visible)
        self.assertFalse(self.shortcut.button.disabled)

    def test_deferred_morgana_can_be_reopened_from_main_map_without_expedition(self):
        import morgana_covenant as covenant
        covenant.ensure_schema(self.db)
        self.db.execute("INSERT INTO morgana_covenants VALUES('Север','deferred',0,NULL,1)")
        self.shortcut.refresh();settle()
        self.assertTrue(self.shortcut.visible)
        self.assertEqual(self.shortcut.button.caption.text,'Моргана')
        with patch('morgana_covenant_ui.show_offer',return_value=None) as show:
            self.shortcut.open()
            show.assert_called_once_with(self.db,'Север',force=True)
