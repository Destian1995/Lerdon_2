import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch

from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from portal_entry_ui import PortalEntryPopup,PORTALS,portal_art
from window_theme import install_window_theme
from kivy.metrics import Metrics
from kivy.uix.popup import Popup


class PortalEntryUITests(unittest.TestCase):
    def setUp(self):
        license=patch('premium_access.full_access',return_value=True)
        license.start();self.addCleanup(license.stop)
        self.db=fixture();self.addCleanup(self.db.close)
        self.size=Window.size
        self.metrics=Metrics.density,Metrics.fontscale
        install_window_theme()
        self.source=SimpleNamespace(conn=self.db,player_fraction='Север',city_name='Home',dismiss=Mock())

    def test_unpaid_portal_shows_preview_but_never_transfers_army(self):
        from premium_options_ui import LockedContentPopup,FullVersionNotice
        with patch('premium_access.full_access',return_value=False),patch('portal_entry_ui.worlds.enter') as enter:
            popup=PortalEntryPopup(self.source);popup.open(animation=False);settle()
            self.assertTrue(popup.art.texture)
            self.assertFalse(any(isinstance(w,FullVersionNotice) for w in popup.walk()))
            panels=(popup.art_panel,popup.details,popup.readiness,popup.enter_button)
            geometry=[(tuple(w.pos),tuple(w.size)) for w in panels]
            children=tuple(popup.root.children)
            popup.enter_button.dispatch('on_release');settle()
            enter.assert_not_called()
            notice=next(w for w in Window.children if isinstance(w,LockedContentPopup))
            self.assertIn('полной версии',notice.message.text)
            self.assertEqual(popup.status.text,'')
            self.assertEqual(children,tuple(popup.root.children))
            self.assertEqual(geometry,[(tuple(w.pos),tuple(w.size)) for w in panels])
            notice.dismiss(animation=False)
            self.assertIsNotNone(popup.parent)
            self.source.dismiss.assert_not_called()
            for size,density in (((640,360),1),((1280,576),2),((390,844),1)):
                Window.size=size;Metrics.density=density;settle();popup.fit();settle()
                for widget in (popup.enter_button,popup.status):
                    self.assertGreaterEqual(widget.y,popup.y-1)
                    self.assertLessEqual(widget.top,popup.top+1)
                self.assertGreater(popup.art.height,40)

    def tearDown(self):
        for popup in list(Window.children):
            if isinstance(popup,Popup):popup.dismiss(animation=False)
        settle()
        Metrics.density,Metrics.fontscale=self.metrics
        Window.size=self.size;settle()

    def test_art_rules_and_departure_remain_visible_on_small_and_large_screens(self):
        popup=PortalEntryPopup(self.source);popup.open(animation=False)
        for size,density in [((1280,820),1),((1280,576),1),((640,360),1),((390,844),1),((1280,576),2)]:
            with self.subTest(size=size,density=density):
                Metrics.density=density
                Window.size=size;settle();popup.fit();settle()
                self.assertTrue(popup.art.texture)
                self.assertGreater(popup.art.height,100)
                self.assertGreater(popup.art.width,100)
                self.assertFalse(popup.enter_button.disabled)
                for widget in [popup.art_panel,popup.details,popup.readiness,popup.enter_button,*popup.rules]:
                    self.assertGreaterEqual(widget.x,popup.x-1)
                    self.assertGreaterEqual(widget.y,popup.y-1)
                    self.assertLessEqual(widget.right,popup.right+1)
                    self.assertLessEqual(widget.top,popup.top+1)
                self.assertLessEqual(popup.enter_button.top,popup.readiness.y+1)
                self.assertLessEqual(popup.rules[-1].top,popup.rules[-2].y+1)

    def test_factions_load_distinct_real_art_and_missing_hero_has_clear_reason(self):
        paths={portal_art(faction) for faction in PORTALS}
        self.assertEqual(len(paths),5)
        self.assertTrue(all(Path(path).is_file() for path in paths))
        for faction in PORTALS:
            self.source.player_fraction=faction
            popup=PortalEntryPopup(self.source)
            self.assertTrue(popup.art.texture)
            self.assertEqual(tuple(popup.heading.color),popup.accent)
        self.source.player_fraction='Север'
        self.db.execute("DELETE FROM garrisons WHERE unit_name='Hero'");self.db.commit()
        popup=PortalEntryPopup(self.source)
        self.assertTrue(popup.enter_button.disabled)
        self.assertIn('герой',popup.readiness.text)
        self.assertFalse(self.source.dismiss.called)

    def test_departure_keeps_real_army_transfer_and_opens_world_once(self):
        import otherworlds
        popup=PortalEntryPopup(self.source);popup.open(animation=False);settle()
        with patch('portal_entry_ui.OtherworldMap') as overview:
            popup.enter_button.dispatch('on_release')
            self.assertIsNotNone(otherworlds.party(self.db,'Север'))
            self.assertFalse(self.db.execute("SELECT 1 FROM garrisons WHERE city_name='Home'").fetchone())
            self.source.dismiss.assert_called_once_with()
            overview.return_value.open.assert_called_once_with()

    def test_class_four_alone_cannot_enable_departure(self):
        self.db.execute("UPDATE units SET unit_class='4' WHERE unit_name='Hero'")
        popup=PortalEntryPopup(self.source)
        self.assertTrue(popup.enter_button.disabled)
        self.assertIn('2–3',popup.readiness.text)
        self.assertIn('4 класса',popup.rules[0].description.text)


if __name__=='__main__':unittest.main()
