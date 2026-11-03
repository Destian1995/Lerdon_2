import unittest

from strategy_ui_fixture import Window,Clock
from test_dialog_layout import settle
from test_otherworlds import fixture
from otherworld_ui import OtherworldMap,ForeignCityPopup
from window_theme import install_window_theme
from kivy.uix.popup import Popup


class OtherworldUITests(unittest.TestCase):
    def setUp(self):
        import otherworlds
        self.db=fixture();self.addCleanup(self.db.close)
        self.size=Window.size
        Window.size=(1280,576)
        install_window_theme();settle()
        otherworlds.enter(self.db,'Север','Home')

    def tearDown(self):
        for popup in list(Window.children):
            if isinstance(popup,Popup): popup.dismiss(animation=False)
        settle();Window.size=self.size

    def test_map_foreign_city_and_five_unit_offers_fit_phone(self):
        import otherworlds
        overview=OtherworldMap(self.db,'Север');overview.open(animation=False);settle()
        self.assertEqual(len(overview.map.hits),7)
        self.assertEqual(len(overview.map.city_textures),7)
        self.assertTrue(overview.map.effects._event)
        city=otherworlds.cities(self.db)[0]
        popup=ForeignCityPopup(overview,city);popup.open(animation=False);settle()
        popup.show_market('units');settle()
        self.assertEqual(len(popup.offers.pages),5)
        self.assertEqual(popup.offers.page_index,0)
        popup.offers.next.dispatch('on_release');settle()
        self.assertEqual(popup.offers.page_index,1)
        self.assertGreater(popup.army_box.parent.height,100)
        self.assertGreater(popup.market.height,100)
        self.assertFalse(popup.battle_button.disabled)

        self.assertTrue(popup.travel_button.disabled)
        for widget in (popup.info,popup.market,popup.feedback,popup.travel_button):
            self.assertGreaterEqual(widget.x,popup.x)
            self.assertGreaterEqual(widget.y,popup.y)
            self.assertLessEqual(widget.right,popup.right+1)
            self.assertLessEqual(widget.top,popup.top+1)

    def test_ambience_stops_when_world_map_closes(self):
        overview=OtherworldMap(self.db,'Север');overview.open(animation=False);settle()
        self.assertTrue(overview.map.effects._event)
        overview.dismiss(animation=False)
        self.assertIsNone(overview.map.effects._event)

    def test_remote_market_disabled_and_travel_has_live_party(self):
        import otherworlds
        overview=OtherworldMap(self.db,'Север');overview.open(animation=False);settle()
        neighbor=self.db.execute('SELECT CASE WHEN city1=1 THEN city2 ELSE city1 END FROM portal_roads WHERE city1=1 OR city2=1 LIMIT 1').fetchone()[0]
        city=next(c for c in otherworlds.cities(self.db) if c['id']==neighbor)
        popup=ForeignCityPopup(overview,city);popup.open(animation=False);settle()
        self.assertFalse(popup.travel_button.disabled)
        self.assertTrue(popup.battle_button.disabled)
        self.assertTrue(all(button.disabled for button in popup.offer_buttons))
        popup.go();settle()
        self.assertEqual(otherworlds.party(self.db,'Север')['city_id'],1)
        self.assertIsNotNone(otherworlds.beam(self.db,'Север'))
        for _ in range(150):overview.map.effects.update(1/30)
        self.assertEqual(otherworlds.party(self.db,'Север')['city_id'],neighbor)
        self.assertTrue(overview.map.beam.finished)
        self.assertIsNone(otherworlds.beam(self.db,'Север'))

    def test_swipe_selects_unit_and_purchase_keeps_the_selected_card(self):
        from kivy.tests.common import UnitTestTouch
        import otherworlds
        overview=OtherworldMap(self.db,'Север');overview.open(animation=False);settle()
        popup=ForeignCityPopup(overview,otherworlds.cities(self.db,'Север')[0])
        popup.open(animation=False);popup.show_market('units');settle()
        carousel=popup.offers.carousel
        x,y=carousel.x+carousel.width*.8,carousel.center_y
        end_x=carousel.x+carousel.width*.15
        touch=UnitTestTouch(x,y)
        touch.touch_down()
        touch.touch_move(x-25,y)
        touch.touch_move(end_x,y)
        touch.touch_up();settle();settle()
        self.assertEqual(popup.offers.page_index,1)
        unit=otherworlds.unit_offers(self.db,'Север')[1]
        current=popup.offers.carousel.current_slide
        self.assertEqual(current.title_label.text,unit['unit_name'])
        current.button.dispatch('on_release');settle()
        self.assertEqual(popup.offers.page_index,1)
        camp=otherworlds.party(self.db,'Север')['camp']
        row=self.db.execute('SELECT unit_count FROM garrisons WHERE city_name=? AND unit_name=?',
                            (camp,'Странник: '+unit['unit_name']+' / Север')).fetchone()
        self.assertEqual(row,(100,))


if __name__=='__main__': unittest.main()
