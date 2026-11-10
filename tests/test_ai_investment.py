"""AI spends real money, protects supply and ranks economic returns."""
import sqlite3
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from ai_economy import investment_plan, develop, secure_supply, hire_with_budget, supply_reserve
from city_construction import building_counts


class InvestmentTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE cities(name,faction);
            CREATE TABLE buildings(city_name,faction,building_type,count);
            CREATE TABLE resources(faction,resource_type,amount);
            CREATE TABLE political_systems(faction,system);
            INSERT INTO cities VALUES('Home','Север');
            INSERT INTO political_systems VALUES('Север','Смирение');''')
        self.ai = SimpleNamespace(db_connection=self.db, faction='Север',
            resources={'Кроны':2500,'Кристаллы':3000,'Население':200,'Рабочие':200},
            raw_material_price=100, total_consumption=0, food_peoples=80,
            food_info=0, army_limit=10000, army={}, garrison={}, turn=1,
            get_factions_at_war=lambda: [])
        def save():
            self.db.execute('DELETE FROM resources')
            self.db.executemany('INSERT INTO resources VALUES(?,?,?)',
                [('Север',k,v) for k,v in self.ai.resources.items()])
        self.ai.save_resources_to_db=save

    def test_factory_precedes_growth_when_supplies_are_insufficient(self):
        self.assertEqual(investment_plan(self.ai)[0][2], 'Фабрика')
        with patch('city_development.refresh_ai_buildings'):
            built=develop(self.ai)
        self.assertEqual(built,[('Home','Фабрика'),('Home','Больница')])
        self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE resource_type='Кроны'").fetchone()[0],0)
        with patch('city_development.refresh_ai_buildings'):
            # Reload the real remaining balance, as the production refresh does.
            self.ai.resources['Кроны']=0
            self.assertEqual(develop(self.ai),[])
        self.assertEqual(len(building_counts(self.db,'Home','Север')),2)

    def test_market_priority_follows_politics_and_existing_production(self):
        self.ai.faction='Элины'
        self.db.execute("UPDATE cities SET faction='Элины'")
        self.db.execute("UPDATE political_systems SET faction='Элины',system='Борьба'")
        self.db.execute("INSERT INTO buildings VALUES('Home','Элины','Фабрика',1)")
        self.db.execute("INSERT INTO buildings VALUES('Home','Элины','Больница',1)")
        self.assertEqual(investment_plan(self.ai)[0][2],'Рынок')

    def test_food_is_bought_with_real_crowns_at_ask_price(self):
        self.ai.resources['Кристаллы']=0
        bought=secure_supply(self.ai)
        self.assertEqual(bought,supply_reserve(self.ai))
        self.assertAlmostEqual(self.ai.resources['Кроны'],2500-160*1.05)
        self.assertEqual(secure_supply(self.ai),0)

    def test_entire_recruitment_including_heroes_has_an_investment_budget(self):
        old_limit=self.ai.army_limit
        def hire():
            self.assertEqual(self.ai.resources['Кроны'],1000)
            self.assertLess(self.ai.army_limit,old_limit)
            self.ai.resources['Кроны']=0
        self.ai._orig_hire_army=hire
        hire_with_budget(self.ai)
        self.assertEqual(self.ai.resources['Кроны'],1500)
        self.assertEqual(self.ai.army_limit,old_limit)

    def test_failed_recruitment_restores_reserved_cash_and_cap(self):
        self.ai._orig_hire_army=lambda: (_ for _ in ()).throw(RuntimeError('failure'))
        with self.assertRaises(RuntimeError):hire_with_budget(self.ai)
        self.assertEqual(self.ai.resources['Кроны'],2500)
        self.assertEqual(self.ai.army_limit,10000)


if __name__=='__main__':unittest.main()
