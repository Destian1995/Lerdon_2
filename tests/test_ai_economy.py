"""Exercise the AI's real persistence and spending code against an isolated DB."""
import ast
from contextlib import redirect_stdout
import io
from pathlib import Path
import random
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import ai_strategy as strategy


def controller_class():
    tree = ast.parse(Path('ii.py').read_text(encoding='utf-8'))
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'AIController')
    names = {'load_cities', 'load_garrison', 'update_buildings_for_current_cities', 'update_buildings_from_db',
             'build_in_city', 'save_buildings', 'save_resources_to_db', 'load_resources_from_db',
             'calculate_current_consumption', 'calculate_and_deduct_consumption', 'calculate_army_limit',
             'calculate_tax_income', 'generate_raw_material_price', 'update_resources', 'apply_political_system_bonus'}
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    namespace = dict(sqlite3=sqlite3, random=random)
    exec(compile(ast.Module(body=methods, type_ignores=[]), 'ii.py', 'exec'), namespace)
    return type('EconomyController', (), {n.name: namespace[n.name] for n in methods})


class AIEconomyTests(unittest.TestCase):
    def setUp(self):
        self.output = io.StringIO()
        self.redirect = redirect_stdout(self.output)
        self.redirect.__enter__()
        self.db = sqlite3.connect(':memory:')
        self.db.executescript('''
            CREATE TABLE cities(id INTEGER PRIMARY KEY, name, faction);
            CREATE TABLE buildings(faction, city_name, building_type, count);
            CREATE TABLE resources(faction, resource_type, amount);
            CREATE TABLE units(unit_name, consumption, faction);
            CREATE TABLE garrisons(city_name, unit_name, unit_count);
            INSERT INTO cities VALUES (1,'Столица','Север');
            INSERT INTO buildings VALUES ('Север','Столица','Больница',2),
                ('Север','Столица','Фабрика',2), ('Север','Столица','Стена',1);
        ''')
        self.ai = controller_class()()
        ai = self.ai
        ai.db_connection, ai.cursor, ai.faction = self.db, self.db.cursor(), 'Север'
        ai.buildings, ai.garrison = {}, {}
        ai.turn, ai.hospitals, ai.factories = 0, 0, 0
        ai.resources = {'Кроны': 50, 'Рабочие': 1000, 'Кристаллы': 1000, 'Население': 100}
        self.db.executemany('INSERT INTO resources VALUES (?,?,?)', [('Север', k, v) for k, v in ai.resources.items()])
        ai.money, ai.free_peoples, ai.raw_material, ai.population = 50, 1000, 1000, 100
        ai.total_consumption, ai.tax_effects, ai.food_peoples = 0, 0, 0
        ai.army = {'Страж': {'cost': {'money': 40, 'time': 1}, 'consumption': 1, 'stats': {'Класс': '1'}},
                   'Стрелок': {'cost': {'money': 40, 'time': 1}, 'consumption': 1, 'stats': {'Класс': '1'}}}
        ai._situation = {'stage': 'early', 'threat_level': 'safe', 'our_strength': 0}
        ai.manage_buildings = lambda: strategy.manage_buildings_v2(ai)
        ai.sell_resources = lambda: strategy.sell_resources_v2(ai)
        ai.save_all_data = lambda: (ai.save_resources_to_db(), ai.save_buildings())
        for name in ('update_trade_resources_from_db', 'process_trade_agreements', '_apply_supply_line_losses',
                     'process_queries', 'update_relations_based_on_political_system', 'update_economic_efficiency'):
            setattr(ai, name, lambda *args: None)
        ai.load_political_system = lambda: 'Смирение'

    def tearDown(self):
        self.db.close()
        self.redirect.__exit__(None, None, None)

    def test_resuming_first_turn_preserves_existing_buildings_and_improvements(self):
        with patch.object(strategy, 'assess_situation', return_value=self.ai._situation), \
                patch.object(strategy, 'apply_leader_pressure'):
            strategy.make_turn_v2(self.ai)
        rows = dict(self.db.execute('SELECT building_type,count FROM buildings'))
        self.assertEqual(self.ai.turn, 1, self.output.getvalue())
        self.assertEqual(rows, {'Больница': 3, 'Фабрика': 4, 'Стена': 1})

    def test_fifty_crowns_can_fund_partial_building_budget(self):
        self.ai.update_buildings_for_current_cities()
        self.ai.turn = 15
        self.ai._situation = {'stage': 'mid', 'threat_level': 'critical'}
        strategy.manage_buildings_v2(self.ai)
        self.assertLess(self.ai.resources['Кроны'], 50)
        self.assertEqual(self.db.execute('SELECT SUM(count) FROM buildings').fetchone()[0], 6)

    def test_two_build_calls_cannot_exceed_city_limit(self):
        self.db.execute('UPDATE buildings SET count=11 WHERE building_type="Больница"')
        self.db.execute('UPDATE buildings SET count=12 WHERE building_type="Фабрика"')
        self.ai.update_buildings_for_current_cities()
        self.ai.build_in_city('Больница', 4)
        self.ai.build_in_city('Фабрика', 4)
        self.ai.save_all_data()
        rows = dict(self.db.execute('SELECT building_type,count FROM buildings'))
        self.assertEqual(rows['Больница'] + rows['Фабрика'], 24)
        self.assertEqual(rows['Стена'], 1)

    def test_diversity_budget_does_not_block_one_affordable_unit(self):
        garrison = {'Столица': []}
        strategy.hire_units_v2(self.ai, garrison, 50, 100, 100)
        self.assertEqual(sum(unit['unit_count'] for unit in garrison['Столица']), 1)
        self.assertEqual(self.ai.resources['Кроны'], 10)

    def test_upkeep_sums_all_stacks_and_persists_the_deduction(self):
        self.db.execute('INSERT INTO units VALUES ("Страж",2,"Север")')
        self.db.executemany('INSERT INTO garrisons VALUES (?,"Страж",?)', [('Столица', 10), ('Граница', 20)])
        self.ai.calculate_and_deduct_consumption()
        self.ai.save_resources_to_db()
        self.assertEqual(self.ai.total_consumption, 60)
        self.assertEqual(self.ai.resources['Кристаллы'], 940)
        self.assertEqual(self.db.execute('SELECT amount FROM resources WHERE resource_type="Кристаллы"').fetchone()[0], 940)

    def test_sales_leave_supply_and_emergency_only_raises_needed_cash(self):
        ai = self.ai
        ai.total_consumption, ai.food_peoples, ai.raw_material_price = 300, 200, 200
        ai.resources['Кроны'] = 0
        self.assertTrue(strategy.emergency_sell_crystals(ai))
        self.assertGreaterEqual(ai.resources['Кристаллы'], 500)
        self.assertLessEqual(ai.resources['Кроны'], strategy.recovery_cash_target(ai) + 200)
        strategy.sell_resources_v2(ai)
        self.assertEqual(ai.resources['Кристаллы'], 500)
        self.assertEqual(ai.resources['Кроны'], 500 * 200)

    def test_negative_income_is_not_charged_again_as_ideology_bonus(self):
        self.ai.money_up = -100
        self.ai.apply_political_system_bonus()
        self.assertEqual(self.ai.resources['Кроны'], 50)

    def test_poor_faction_develops_across_turns_without_erasing_previous_builds(self):
        ai = self.ai
        ai.get_factions_at_war = lambda: []
        for name in ('hire_army', 'generate_and_buy_artifacts_for_ai_hero', 'send_proactive_diplomacy',
                     'send_help_request_if_needed', 'send_mercy_request_if_needed'):
            setattr(ai, name, lambda: None)
        counts = []
        with patch.object(strategy, 'assess_situation', return_value=ai._situation), \
                patch.object(strategy, 'apply_leader_pressure'), patch.object(strategy, 'ensure_scout_unit'), \
                patch.object(strategy, 'early_expansion'), patch.object(strategy, 'rally_units_to_hero'):
            for _ in range(6):
                strategy.make_turn_v2(ai)
                counts.append(self.db.execute('SELECT SUM(count) FROM buildings').fetchone()[0])
        self.assertEqual(ai.turn, 6, self.output.getvalue())
        self.assertEqual(counts, sorted(counts))
        self.assertGreater(counts[-1], counts[0])
        self.assertGreaterEqual(ai.resources['Кроны'], 0)


if __name__ == '__main__':
    unittest.main()
