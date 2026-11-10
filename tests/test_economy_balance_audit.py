import unittest
from tools.economy_balance_audit import simulate,trade_cycle,make_player


class EconomyAuditTests(unittest.TestCase):
    def test_real_new_game_budget_builds_hospital_and_factory(self):
        p=make_player('Север')
        try:
            self.assertEqual((p.money,p.population,p.raw_material,p.hospitals,p.factories),(0,10,0,1,1))
        finally:p.conn.close()

    def test_real_tax_and_growth_order_for_first_winter_income(self):
        north=simulate('Север','Смирение',[34])['final']
        elines=simulate('Элины','Смирение',[34])['final']
        self.assertEqual((north['crowns'],north['population'],north['crystals']),(280,478,693))
        self.assertEqual((elines['crowns'],elines['population'],elines['crystals']),(8,478,730))

    def test_valuation_uses_same_quote_and_real_terminal_sell_multiplier(self):
        for faction in ('Север','Элины'):
            result=simulate(faction,'Борьба',[34]*14)
            end=result['final']
            self.assertAlmostEqual(result['wealth_at_crystal_quote_1'],round(end['crowns']+end['crystals']*result['final_sell_multiplier'],2))

    def test_actual_trade_round_trip_costs_money_and_elines_get_better_quotes(self):
        north=trade_cycle('Север');elines=trade_cycle('Элины')
        self.assertEqual(north['crowns_after'],9135.50)
        self.assertEqual(elines['crowns_after'],9379.84)
        self.assertLess(elines['crowns_after'],elines['crowns_before'])
        self.assertGreater(trade_cycle('Элины',True)['crowns_after'],elines['crowns_after'])
