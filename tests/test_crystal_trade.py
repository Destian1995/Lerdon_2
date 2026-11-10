import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from utils.crystal_trade import crystal_quotes,total_price,trade_efficiency,affordable_lots
from tools.economy_balance_audit import make_player
from test_trade_audio import action


class CrystalTradeTests(unittest.TestCase):
    def test_positive_spread_for_all_prices_and_extreme_efficiencies(self):
        for price in (.01,76.3,100,148.7,200):
            for efficiency in (1,1.1,1.55,1.9875,100,1000000):
                buy,sell=crystal_quotes(price,efficiency)
                self.assertGreaterEqual(buy,price)
                self.assertLessEqual(sell,price)
                self.assertGreater(buy,sell)
                for lots in (1,9,10000):self.assertGreater(total_price(buy,lots),total_price(sell,lots))

    def test_more_markets_council_and_elines_summer_improve_both_quotes_safely(self):
        basic=crystal_quotes(100,trade_efficiency('Север'))
        north=crystal_quotes(100,trade_efficiency('Север',1))
        elines=crystal_quotes(100,trade_efficiency('Элины',1))
        summer=crystal_quotes(100,trade_efficiency('Элины',1,2))
        for previous,current in zip((basic,north,elines),(north,elines,summer)):
            self.assertLess(current[0],previous[0]);self.assertGreater(current[1],previous[1])
        self.assertGreater(summer[0],summer[1])

    def test_round_trips_never_mint_cash_or_crystals_for_any_faction(self):
        for faction in ('Север','Эльфы','Вампиры','Адепты','Элины'):
            for season in range(4):
                p=make_player(faction,developed=True)
                try:
                    p.conn.execute('UPDATE season SET season_index=?',(season,))
                    p.money=10000;p.raw_material=0;p._sync_resources()
                    for _ in range(4):
                        before=p.money
                        self.assertTrue(p.trade_raw_material('buy',1))
                        self.assertEqual(p.raw_material,100)
                        self.assertTrue(p.trade_raw_material('sell',1))
                        self.assertEqual(p.raw_material,0);self.assertLess(p.money,before)
                    before=(p.money,p.raw_material)
                    for invalid in (0,-1,.5,float('nan'),float('inf')):
                        self.assertFalse(p.trade_raw_material('buy',invalid))
                        self.assertEqual((p.money,p.raw_material),before)
                finally:p.conn.close()

    def test_exact_affordability_and_backend_charge_match(self):
        p=make_player('Элины',developed=True)
        try:
            buy,sell=crystal_quotes(100,p._get_trade_bonus())
            p.money=total_price(buy,3);p._sync_resources()
            self.assertEqual(affordable_lots(p.money,buy),3)
            self.assertEqual(affordable_lots(p.money-.01,buy),2)
            self.assertTrue(p.trade_raw_material('buy',3))
            self.assertEqual((p.money,p.raw_material),(0,300))
            self.assertTrue(p.trade_raw_material('sell',3))
            self.assertAlmostEqual(p.money,total_price(sell,3))
        finally:p.conn.close()

    def test_handler_checks_and_reports_real_quote_and_sends_one_success_sound(self):
        messages=Mock()
        handle=action('economic.py','handle_trade',show_message=messages,format_number=str)
        p=make_player('Север',developed=True)
        try:
            buy,_=crystal_quotes(100,p._get_trade_bonus())
            p.money=buy-.01;p._sync_resources();p.update_economic_efficiency=Mock()
            with patch('game_audio.play_effect') as sound:
                handle(p,'buy',1,Mock());sound.assert_not_called()
            self.assertEqual(p.raw_material,0)
            p.money=buy;p._sync_resources()
            with patch('game_audio.play_effect') as sound:
                handle(p,'buy',1,Mock());sound.assert_called_once_with('coins')
            self.assertEqual((p.money,p.raw_material),(0,100))
        finally:p.conn.close()

    def test_north_zero_tax_growth_and_34_percent_income_remain_unchanged(self):
        p=make_player('Север',developed=True)
        try:
            self.assertEqual(p.tax_effect(0),57)
            self.assertEqual(p.tax_effect(34),0)
            self.assertEqual(p.get_base_tax_rate(),.12)
            p.population=50000;p.current_tax_rate='34%';p.set_taxes(34)
            self.assertEqual(p.calculate_tax_income(),204000)
            p.raw_material=100000;p.money=0;p._sync_resources();p.save_resources_to_db()
            p.update_resources();p.apply_player_bonuses()
            self.assertEqual(p.money,1876752)
        finally:p.conn.close()
