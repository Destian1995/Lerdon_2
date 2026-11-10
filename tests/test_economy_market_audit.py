import unittest
from tools.economy_market_audit import simulate_exports


class ActiveMarketAuditTests(unittest.TestCase):
    def test_north_switches_to_34_only_after_reaching_50000_population(self):
        plan=[lambda player,turn:34 if player.population>=50000 else 9]*14
        result=simulate_exports('Север','Смирение',plan)
        self.assertEqual(result['history'][-2]['population'],53522)
        self.assertEqual(result['history'][-2]['tax'],9)
        self.assertEqual(result['final']['tax'],34)
        self.assertGreater(result['final']['crowns'],3300000)

    def test_three_city_active_exports_reproduce_the_elines_advantage(self):
        rates=[34]*14
        north=simulate_exports('Север','Борьба',rates,cities=3)
        elines=simulate_exports('Элины','Борьба',rates,cities=3)
        self.assertEqual(north['wealth'],859987.40)
        self.assertEqual(elines['wealth'],1026362.16)
        self.assertEqual(north['final']['markets'],elines['final']['markets'])
        self.assertEqual(north['final']['factories'],elines['final']['factories'])

    def test_exports_never_sell_more_than_current_turn_net_production(self):
        for faction in ('Север','Элины'):
            result=simulate_exports(faction,'Смирение',[9]*14,cities=1)
            if faction=='Север':self.assertTrue(any(row['purchased']>0 for row in result['history']))
            for row in result['history']:
                self.assertLessEqual(row['sold'],row['net_produced'])
                self.assertGreaterEqual(row['crowns'],0)
                self.assertGreaterEqual(row['crystals'],0)
