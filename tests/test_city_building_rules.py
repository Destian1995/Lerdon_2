"""City upgrades affect real spending, upkeep and the military AI turn."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from city_construction import CATALOG,building_counts,ensure_unique_buildings,garrison_consumption_multipliers
from city_development import develop_military_cities
from test_unique_development import fixture,methods


class BuildingRulesTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)

    def army(self):
        self.db.executescript('''CREATE TABLE units(unit_name,consumption,faction,unit_class);
            CREATE TABLE garrisons(city_name,unit_name,unit_count);
            INSERT INTO units VALUES('Soldier',2,'Север','1');
            INSERT INTO garrisons VALUES('A','Soldier',100),('B','Soldier',100);
            INSERT INTO buildings VALUES('A','Север','Кузница',7);''')

    def test_prices_and_old_watchtower_migration_after_unique_index_exists(self):
        self.assertEqual([CATALOG[k]['cost'] for k in ('Кузница','Цитадель','Стена')],[30000,50000,40000])
        ensure_unique_buildings(self.db)
        self.db.executemany('INSERT INTO buildings VALUES(?,?,?,1)',[
            ('A','Север','Вышка'),('B','Север','Вышка'),('B','Север','Цитадель')])
        for _ in range(2):
            self.assertEqual(building_counts(self.db,'A','Север'),{'Цитадель':1})
            self.assertEqual(building_counts(self.db,'B','Север'),{'Цитадель':1})

    def test_forge_is_local_does_not_stack_and_requires_current_ownership(self):
        self.army()
        self.assertEqual(garrison_consumption_multipliers(self.db),{'A':.95})
        self.db.execute("UPDATE cities SET faction='Эльфы' WHERE name='A'")
        self.assertEqual(garrison_consumption_multipliers(self.db),{})

    def test_player_display_and_actual_crystal_deduction_match(self):
        self.army()
        cls=type('Player',(),methods('economic.py','Faction',[
            'recalculate_consumption','calculate_and_deduct_consumption']))
        model=cls();model.conn=self.db;model.cursor=self.db.cursor();model.faction='Север'
        model.resources={};model.raw_material=1000;model.max_army_limit=10000
        model.save_resources_to_db=lambda:None
        self.assertAlmostEqual(model.recalculate_consumption(),390)
        model.calculate_and_deduct_consumption()
        self.assertAlmostEqual(model.resources['Потребление'],390)
        self.assertAlmostEqual(model.raw_material,610)

    def test_ai_charges_the_same_discount(self):
        self.army()
        cls=type('AI',(),methods('ii.py','AIController',[
            'calculate_current_consumption','calculate_and_deduct_consumption']))
        ai=cls();ai.db_connection=self.db;ai.cursor=self.db.cursor();ai.faction='Север'
        ai.resources={'Кристаллы':1000};ai.raw_material=1000
        ai.calculate_and_deduct_consumption()
        self.assertAlmostEqual(ai.total_consumption,390)
        self.assertAlmostEqual(ai.resources['Кристаллы'],610)

    def test_rebels_and_undead_build_all_six_once_from_their_own_treasury(self):
        names=['load_cities','load_buildings','load_resources','update_buildings_for_current_cities']
        cls=type('AI',(),methods('ii.py','AIController',names))
        for faction in ('Мятежники','Нежить'):
            with self.subTest(faction=faction):
                self.db.execute('DELETE FROM buildings')
                self.db.execute('UPDATE cities SET faction=?,is_undead=1',(faction,))
                self.db.execute("INSERT OR REPLACE INTO resources VALUES(?,'Кроны',1000000)",(faction,))
                ai=cls();ai.db_connection=self.db;ai.cursor=self.db.cursor();ai.faction=faction
                ai.resources={};ai.buildings={};ai.cities_buildings={}
                self.assertEqual(len(develop_military_cities(ai)),12)
                self.assertEqual(develop_military_cities(ai),[])
                expected=1000000-2*sum(v['cost'] for v in CATALOG.values())
                self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE faction=? AND resource_type='Кроны'",(faction,)).fetchone()[0],expected)
                self.assertEqual(ai.resources['Кроны'],expected)
                self.assertTrue(all(set(data['Здания'])==set(CATALOG) for data in ai.buildings.values()))

    def test_active_ai_turn_invokes_military_city_construction_before_attack(self):
        from ai_strategy import make_turn_v2
        for faction in ('Мятежники','Нежить'):
            calls=[]
            ai=SimpleNamespace(faction=faction,cursor=self.db.cursor(),db_connection=self.db,
                turn=1,attack_enemy_cities=lambda:calls.append('attack'),
                _undead_attack_nearest_cities=lambda:calls.append('attack'),save_all_data=lambda:None)
            with patch('city_development.develop_military_cities',side_effect=lambda _:calls.append('build')), \
                 patch('undead_invasion._declare_war_to_all'):
                make_turn_v2(ai)
            self.assertEqual(calls,['build','attack'])
