"""Economy and distinct combat allocations of Mirror Realm recruits."""
import unittest
from decimal import Decimal,ROUND_HALF_UP,ROUND_CEILING
from test_otherworlds import fixture
import otherworlds as w
from otherworld_content import balance_mirror_unit
from otherworld_themes import THEMES


class MirrorUnitBalanceTests(unittest.TestCase):
    def test_balanced_fourth_tier_scales_94_points_without_losing_the_budget(self):
        base=dict(unit_name='Маг',attack=94,defense=0,cost_money=100,durability=8,consumption=2)
        unit=balance_mirror_unit(dict(id=4),base,'Элины')
        self.assertEqual((unit['attack'],unit['defense']),(170.38,170.37))
        self.assertEqual(unit['cost_money'],288)
        self.assertAlmostEqual(unit['crowns_per_stat'],100/94)
        self.assertEqual(unit['durability'],20)
        self.assertEqual(unit['consumption'],5.75)

    def test_one_main_map_recruit_yields_five_distinct_profiles_for_every_faction(self):
        db=fixture();self.addCleanup(db.close)
        before=list(db.execute('SELECT * FROM units'))
        for faction in THEMES:
            roster=w.unit_offers(db,faction)
            self.assertEqual(len({(u['attack'],u['defense']) for u in roster}),5)
            self.assertTrue(any(abs(u['attack']-u['defense'])<.011 for u in roster))
            self.assertTrue(any(u['attack']==0 and u['defense']>0 for u in roster))
            self.assertTrue(any(u['defense']==0 and u['attack']>0 for u in roster))
            for u in roster:
                expected=(Decimal(str(u['base_combat_points']))*Decimal('1.45')*Decimal(str(u['tier_multiplier']))).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
                self.assertAlmostEqual(u['attack']+u['defense'],float(expected))
                price=Decimal(str(u['base_cost_money']))*Decimal('1.15')*Decimal(str(u['tier_multiplier']))
                self.assertEqual(u['cost_money'],int(price.to_integral_value(rounding=ROUND_CEILING)))
            for first,second in zip(roster,roster[1:]):
                self.assertLess(first['cost_money'],second['cost_money'])
                self.assertLess(first['combat_budget'],second['combat_budget'])
                self.assertLess(first['durability'],second['durability'])
                self.assertLess(first['consumption'],second['consumption'])
        self.assertEqual(list(db.execute('SELECT * FROM units')),before)

    def test_tier_price_has_city_markup_once_and_template_keeps_base_price(self):
        db=fixture();self.addCleanup(db.close)
        party=w.enter(db,'Север','Home')
        db.execute('UPDATE portal_cities SET price=133 WHERE id=1')
        u=w.unit_offers(db,'Север')[3]
        cost=w.recruit(db,'Север',u['id'],13)
        marked_up=int((Decimal(u['cost_money'])*Decimal('1.33')).to_integral_value(rounding=ROUND_CEILING))
        self.assertEqual(cost,marked_up*13)
        name='Странник: '+u['unit_name']+' / Север'
        self.assertEqual(db.execute('SELECT attack,defense,cost_money FROM units WHERE unit_name=?',(name,)).fetchone(),
                         (u['attack'],u['defense'],u['cost_money']))
        db.execute('UPDATE units SET attack=1,defense=1,cost_money=999 WHERE unit_name=?',(name,))
        db.execute('UPDATE portal_presentation SET version=4')
        before=list(db.execute('SELECT * FROM garrisons'))
        w.upgrade_world(db)
        self.assertEqual(db.execute('SELECT attack,defense,cost_money FROM units WHERE unit_name=?',(name,)).fetchone(),
                         (u['attack'],u['defense'],u['cost_money']))
        self.assertEqual(list(db.execute('SELECT * FROM garrisons')),before)
        self.assertEqual(w.party(db,'Север'),party)

    def test_mixed_ordinary_roles_cannot_invert_tier_prices_or_power(self):
        db=fixture();self.addCleanup(db.close)
        db.execute('''INSERT INTO units(id,faction,unit_name,cost_money,cost_time,image_path,attack,defense,
            durability,unit_class,consumption,unit_type) VALUES(7,'Север','Дорогой маг',5000,1,'',1,2,3,'1',1,'mage')''')
        roster=w.unit_offers(db,'Север')
        self.assertEqual({u['base_unit_name'] for u in roster},{'troop1'})
        for first,second in zip(roster,roster[1:]):
            self.assertLess(first['cost_money'],second['cost_money'])
            self.assertLess(first['attack']+first['defense'],second['attack']+second['defense'])

    def test_small_prices_still_increase_after_rounding_to_whole_crowns(self):
        base=dict(unit_name='Рекрут',attack=1,defense=1,cost_money=1,durability=1,consumption=1)
        roster=[balance_mirror_unit(dict(id=i),base,'Север') for i in range(1,6)]
        self.assertEqual([u['cost_money'] for u in roster],[2,3,4,5,6])
