"""Integer diplomacy, turn-bound crystal quotes and clean city/shop presentation."""
import unittest
from unittest.mock import patch
from strategy_ui_fixture import Window
from kivy.uix.popup import Popup
from kivy.metrics import Metrics
from test_dialog_layout import settle
from test_otherworlds import fixture
from otherworld_ui import OtherworldMap,ForeignCityPopup
from utils.trade_offers import full_balance_offer
import otherworlds as w


class MarketRulesTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)
        w.enter(self.db,'Север','Home')

    def test_fractional_ai_balances_quote_integer_amounts_rounded_down(self):
        self.db.execute("INSERT INTO resources VALUES('Игрок','Кристаллы',34232.122321321)")
        self.db.execute("INSERT INTO resources VALUES('Игрок','Кроны',0)")
        deal=full_balance_offer(self.db,'Север','Игрок')
        self.assertEqual(deal[3],34232)
        self.assertEqual(deal[1],34232*5//6)
        self.assertIsInstance(deal[1],int);self.assertIsInstance(deal[3],int)
        self.assertNotRegex(deal[4],r'\d[.,]\d')

    def test_quote_is_saved_for_the_turn_and_walks_only_on_next_turn(self):
        with patch('random.uniform',return_value=100):self.assertEqual(w.crystal_quote(self.db),100)
        with patch('random.uniform',side_effect=AssertionError('must reuse quote')):
            self.assertEqual(w.crystal_quote(self.db),100)
            self.assertEqual(w.crystal_trade_price(self.db),10500)
            self.assertEqual(w.crystal_trade_price(self.db,False),9500)
        self.db.execute('UPDATE portal_crystal_quotes SET price=100.6')
        self.assertEqual(w.crystal_trade_price(self.db),10563)
        self.assertEqual(w.crystal_trade_price(self.db,False),9557)
        self.db.execute('UPDATE portal_crystal_quotes SET price=100')
        self.db.execute('UPDATE turn SET turn_count=1');self.db.commit()
        with patch('random.uniform',return_value=-4):self.assertEqual(w.crystal_quote(self.db),96)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM portal_crystal_quotes').fetchone()[0],2)

    def test_city_markup_affects_recruitment_but_not_crystal_buy_or_sell(self):
        with patch('random.uniform',return_value=100):w.crystal_quote(self.db)
        unit=w.unit_offers(self.db,'Север')[0]
        for markup in (100,160):
            self.db.execute('UPDATE portal_cities SET price=? WHERE id=1',(markup,));self.db.commit()
            self.assertEqual(w.trade_crystals(self.db,'Север'),10500)
            self.assertEqual(w.trade_crystals(self.db,'Север',False),9500)
            paid=w.recruit(self.db,'Север',unit['id'],1)
            self.assertEqual(paid,w.price({'price':markup},unit['cost_money']))


class MarketPresentationTests(unittest.TestCase):
    def setUp(self):
        self.size=Window.size;self.metrics=(Metrics.density,Metrics.fontscale)
        Metrics.density=Metrics.fontscale=1;Window.size=(640,360);settle()
        self.db=fixture();w.enter(self.db,'Север','Home')
        self.owner=OtherworldMap(self.db,'Север');self.owner.open(animation=False);settle()

    def tearDown(self):
        for widget in list(Window.children):
            if isinstance(widget,Popup):widget.dismiss(animation=False)
        settle();self.db.close();Metrics.density,Metrics.fontscale=self.metrics
        Window.size=self.size;settle()

    def test_remote_city_only_lists_player_garrison_and_art_fills_panel(self):
        city=ForeignCityPopup(self.owner,w.cities(self.db,'Север')[2]);city.open(animation=False);settle()
        self.assertIs(city.guard_label.parent,city.city_titles)
        self.assertEqual(city.army_totals.text,'')
        texts=[getattr(widget,'text','') for widget in city.army_panel.walk()]
        self.assertFalse(any('Стража' in text or 'Независимый' in text or '+3%' in text for text in texts))
        self.assertEqual(city.travel_button.text,'Прийти сюда')
        self.assertEqual(city.bartender.size,city.art_frame.size)
        self.assertEqual(city.bartender.pos,city.art_frame.pos)
        self.assertEqual(city.bartender.fit_mode,'cover')

    def test_crystal_board_shows_both_actions_and_trades_exact_displayed_price(self):
        city=ForeignCityPopup(self.owner,w.cities(self.db,'Север')[0]);city.open(animation=False);settle()
        city.open_market();settle()
        board=city.crystal_market
        self.assertEqual(board.cards.cols,2)
        self.assertEqual(len(board.panels),2)
        self.assertEqual(city.offers.previous.width,0)
        self.assertEqual(city.offers.next.width,0)
        self.assertIn(f'{w.crystal_quote(self.db)/100:.3f}',board.quote.text)
        for panel in board.panels:
            bottom=panel.button.to_window(*panel.button.pos)[1]
            top=panel.button.to_window(panel.button.x,panel.button.top)[1]
            viewport_bottom=board.to_window(*board.pos)[1]
            viewport_top=board.to_window(board.x,board.top)[1]
            self.assertGreaterEqual(bottom,viewport_bottom-1)
            self.assertLessEqual(top,viewport_top+1)
            money=self.db.execute("SELECT amount FROM resources WHERE faction='Север' AND resource_type='Кроны'").fetchone()[0]
            crystals=self.db.execute("SELECT amount FROM resources WHERE faction='Север' AND resource_type='Кристаллы'").fetchone()[0]
            price=w.crystal_trade_price(self.db,panel.buy)
            self.assertIn(f'{price:,}'.replace(',',' '),panel.price.text)
            panel.button.dispatch('on_release');settle()
            after=dict(self.db.execute("SELECT resource_type,amount FROM resources WHERE faction='Север'"))
            self.assertEqual(after['Кроны'],money+(-price if panel.buy else price))
            self.assertEqual(after['Кристаллы'],crystals+(10000 if panel.buy else -10000))
        city.show_market('artifacts');settle()
        self.assertIsNone(board.parent)
        city.show_market('resources');settle()
        self.assertIs(board.parent,city.market)

    def test_artifact_list_hero_slots_purchase_and_resource_tab_switch(self):
        city=ForeignCityPopup(self.owner,w.cities(self.db,'Север')[0]);city.open(animation=False);settle()
        city.open_market();city.show_market('artifacts');settle()
        shop=city.artifact_shop
        self.assertEqual(len(shop.rows.children),5)
        self.assertEqual(len(shop.equipment_slots),5)
        self.assertIsNone(city.offers.parent)
        self.assertIs(shop.parent,city.market)
        self.assertFalse(shop.buy_buttons[0].disabled)
        shop.buy_buttons[0].dispatch('on_release');settle()
        self.assertTrue(shop.buy_buttons[0].disabled)
        self.assertTrue(shop.slot_images['0'].source)
        self.assertFalse(shop.equipment_slots['0'].disabled)
        for size,density in (((640,360),1),((1280,576),2.5),((392,844),1)):
            Window.size=size;Metrics.density=density;settle()
            for slot in shop.equipment_slots.values():
                self.assertGreaterEqual(slot.x,shop.hero_panel.x-1)
                self.assertGreaterEqual(slot.y,shop.hero_panel.y-1)
                self.assertLessEqual(slot.right,shop.hero_panel.right+1)
                self.assertLessEqual(slot.top,shop.hero_panel.top+1)
            self.assertGreaterEqual(shop.hero_portrait.y,shop.hero_panel.y-1)
            self.assertLessEqual(shop.hero_portrait.top,shop.hero_panel.top+1)
        city.show_market('resources');settle()
        self.assertIsNone(shop.parent)
        self.assertIs(city.crystal_market.parent,city.market)
        self.assertEqual(len(city.crystal_market.panels),2)
