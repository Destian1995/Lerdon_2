"""Free undead rebuilding and paid hiring are independent of invasion waves."""
from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import Mock
from test_rebel_campaign import extracted_class
from test_otherworlds import fixture
from ai_strategy import apply_ai_improvements
from undead_economy import initialize_resources,restore_undead_buildings
from city_construction import CATALOG,building_counts


class UndeadEconomyTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)
        self.db.executescript('''CREATE TABLE diplomacies(faction1,faction2,relationship);
            CREATE TABLE relations(faction1,faction2,relationship);
            CREATE TABLE results(faction PRIMARY KEY,Units_Combat DEFAULT 0);
            CREATE TABLE roads(city1,city2);
            CREATE TABLE undead_invasion(id PRIMARY KEY,capital_city,invasion_started,king_alive,invasion_turn,army_limit);
            INSERT INTO undead_invasion VALUES(1,'Home',1,1,4,12500);
            UPDATE cities SET faction='Нежить' WHERE name='Home';
            INSERT INTO units VALUES(7,'Нежить','Ghost',5,1,'',30,20,10,'1',.8,'infantry');
            INSERT INTO garrisons VALUES('Home','Ghost',10,'',0);''')
        cls=extracted_class('ii.py','AIController');apply_ai_improvements(cls)
        self.ai=cls('Нежить',self.db)
        for name in ('update_trade_resources_from_db','process_trade_agreements','_apply_supply_line_losses','save_results_to_db'):
            setattr(self.ai,name,lambda:None)
        self.ai._undead_attack_nearest_cities=Mock()

    def test_active_turn_builds_pays_for_recruits_and_keeps_invasion_state(self):
        self.ai.generate_raw_material_price=lambda:setattr(self.ai,'raw_material_price',200)
        before=list(self.db.execute('SELECT * FROM undead_invasion'))
        player=sorted(self.db.execute("SELECT * FROM resources WHERE faction='Север'"))
        with redirect_stdout(io.StringIO()):self.ai.make_turn()
        self.assertEqual(self.ai.turn,1)
        self.assertEqual(dict(self.db.execute("SELECT building_type,count FROM buildings WHERE faction='Нежить'")),
                         dict.fromkeys(CATALOG,1))
        count=self.db.execute("SELECT unit_count FROM garrisons WHERE unit_name='Ghost'").fetchone()[0]
        self.assertGreater(count,10)
        resources=dict(self.db.execute("SELECT resource_type,amount FROM resources WHERE faction='Нежить'"))
        self.assertLess(resources['Рабочие'],420)
        self.assertGreater(resources['Население'],200)
        self.assertEqual(player,sorted(self.db.execute("SELECT * FROM resources WHERE faction='Север'")))
        self.assertEqual(before,list(self.db.execute('SELECT * FROM undead_invasion')))
        self.ai._undead_attack_nearest_cities.assert_called_once()
        with redirect_stdout(io.StringIO()):self.ai.make_turn()
        self.assertEqual(self.ai.turn,2)

    def test_existing_zero_treasury_is_not_refilled_and_owned_buildings_are_inherited(self):
        self.db.executescript("INSERT INTO resources VALUES('Нежить','Кроны',0); INSERT INTO buildings VALUES('Home','Север','Больница',1);")
        self.ai.sell_resources=lambda:None
        with redirect_stdout(io.StringIO()):self.ai.make_turn()
        self.assertEqual(self.ai.turn,1)
        # It earns actual taxes, rather than receiving starting crowns again.
        amount=self.db.execute("SELECT amount FROM resources WHERE faction='Нежить' AND resource_type='Кроны'").fetchone()[0]
        self.assertLess(amount,5000)
        self.assertEqual(self.db.execute("SELECT faction FROM buildings WHERE building_type='Больница'").fetchone()[0],'Нежить')

    def test_invasion_wave_above_regular_army_cap_does_not_disable_paid_hiring(self):
        self.db.execute("UPDATE garrisons SET unit_count=100000 WHERE unit_name='Ghost'")
        with redirect_stdout(io.StringIO()):self.ai.make_turn()
        self.assertEqual(self.ai.turn,1)
        self.assertGreater(self.db.execute("SELECT unit_count FROM garrisons WHERE unit_name='Ghost'").fetchone()[0],100000)

    def test_starting_resources_are_100000_crowns_and_200_population_once(self):
        initialize_resources(self.db)
        balances=dict(self.db.execute("SELECT resource_type,amount FROM resources WHERE faction='Нежить'"))
        self.assertEqual(balances['Кроны'],100000)
        self.assertEqual(balances['Население'],200)
        self.db.execute("UPDATE resources SET amount=0 WHERE faction='Нежить'")
        initialize_resources(self.db)
        self.assertTrue(all(amount==0 for amount, in self.db.execute("SELECT amount FROM resources WHERE faction='Нежить'")))

    def test_all_owned_towns_finish_all_six_buildings_while_hiring_spends_its_budget(self):
        self.db.execute("UPDATE cities SET faction='Нежить' WHERE name='Safe'")
        initialize_resources(self.db)
        hired=[]
        def income():
            self.ai.resources['Кроны']+=15000
            self.ai.save_resources_to_db()
        def hire():
            hired.append(self.ai.resources['Кроны'])
            self.ai.resources['Кроны']=0
        self.ai.update_resources=income
        self.ai.sell_resources=lambda:None
        self.ai.hire_army=hire
        with redirect_stdout(io.StringIO()):
            self.ai.make_turn()
        for city in ('Home','Safe'):
            self.assertEqual(building_counts(self.db,city,'Нежить'),dict.fromkeys(CATALOG,1))
        self.assertTrue(any(amount>0 for amount in hired))
        cash=self.db.execute("SELECT amount FROM resources WHERE faction='Нежить' AND resource_type='Кроны'").fetchone()[0]
        self.assertEqual(100000+15000,sum(hired)+cash)

    def test_zero_balances_restore_full_catalogue_without_spending_or_duplicates(self):
        initialize_resources(self.db)
        self.db.execute("UPDATE resources SET amount=0 WHERE faction='Нежить'")
        before=list(self.db.execute('SELECT * FROM resources'))
        restore_undead_buildings(self.db)
        self.db.execute("DELETE FROM buildings WHERE city_name='Home'")
        restore_undead_buildings(self.db)
        restore_undead_buildings(self.db)
        self.assertEqual(building_counts(self.db,'Home','Нежить'),dict.fromkeys(CATALOG,1))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM buildings WHERE city_name='Home'").fetchone()[0],6)
        self.assertEqual(before,list(self.db.execute('SELECT * FROM resources')))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM buildings WHERE city_name='Safe'").fetchone()[0],0)

    def test_damaged_town_recovers_next_turn_and_lost_town_does_not(self):
        from city_war import record_battle,read_city_war_states
        with redirect_stdout(io.StringIO()):self.ai.make_turn()
        record_battle(self.db,'Home',30_000_000,30_000_000,'Нежить')
        self.assertFalse(building_counts(self.db,'Home','Нежить'))
        self.assertTrue(read_city_war_states(self.db)['Home'].ruined)
        with redirect_stdout(io.StringIO()):self.ai.make_turn()
        self.assertEqual(building_counts(self.db,'Home','Нежить'),dict.fromkeys(CATALOG,1))
        self.assertFalse(read_city_war_states(self.db)['Home'].ruined)
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Home'")
        with redirect_stdout(io.StringIO()):self.ai.make_turn()
        self.assertFalse(building_counts(self.db,'Home','Север'))
