"""Rebel gifts, economics and persistent orders against an isolated SQLite DB."""
import ast
from contextlib import redirect_stdout
import io
from pathlib import Path
import random
import sqlite3
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import ai_strategy
import rebel_campaign as rebels
from rebel_equipment import transfer_artifact
from test_otherworlds import fixture


def extracted_class(filename, name):
    node = next(n for n in ast.parse(Path(filename).read_text(encoding='utf-8')).body
                if isinstance(n, ast.ClassDef) and n.name == name)
    ns = {'sqlite3': sqlite3, 'random': random}
    exec(compile(ast.Module(body=[node], type_ignores=[]), filename, 'exec'), ns)
    return ns[name]


class RebelTests(unittest.TestCase):
    def setUp(self):
        self.db = fixture()
        self.addCleanup(self.db.close)
        output = redirect_stdout(io.StringIO())
        output.__enter__()
        self.addCleanup(output.__exit__, None, None, None)
        self.db.executescript('''
            UPDATE cities SET faction='Мятежники' WHERE name='Home';
            CREATE TABLE roads(city1,city2);
            CREATE TABLE diplomacies(faction1,faction2,relationship);
            CREATE TABLE relations(faction1,faction2,relationship);
            CREATE TABLE results(faction PRIMARY KEY,Units_Combat DEFAULT 0);
            CREATE TABLE rebel_attack_order(id PRIMARY KEY,target_city,target_faction);
            CREATE TABLE season(season_index); INSERT INTO season VALUES(2);
            INSERT INTO units VALUES(7,'Мятежники','Кейдж',100,1,'',250,180,40,'3',10,'infantry');
            INSERT INTO units VALUES(8,'Мятежники','Мятежники',40,1,'',30,20,10,'1',1,'infantry');
            DELETE FROM garrisons;
            INSERT INTO garrisons VALUES('Home','Кейдж',1,'',0),('Home','Мятежники',10,'',0);
            CREATE TABLE units_default AS SELECT * FROM units;
            CREATE TABLE artifact_effects_log(hero_name,artifact_id,stat_name,value_change,
                PRIMARY KEY(hero_name,artifact_id,stat_name));
            CREATE TABLE ai_hero_equipment(faction_name,hero_name,slot_type,artifact_id);
            CREATE TABLE artifacts_ai AS SELECT * FROM artifacts WHERE 0;
            INSERT INTO hero_equipment VALUES('Север','Hero','0',1,'');
        ''')
        self.manager = extracted_class('seasons.py', 'SeasonManager')()
        self.manager.last_idx = 2

    def stats(self, hero):
        return self.db.execute('SELECT attack,defense FROM units WHERE unit_name=?', (hero,)).fetchone()

    def test_gift_immediately_updates_both_heroes_and_does_not_stack_next_turn(self):
        self.manager.apply_artifact_bonuses(self.db)
        boosted_donor = self.stats('Hero')
        transfer_artifact(self.db, 'Север', 'Hero', '0', 1, self.manager)
        self.assertEqual(self.stats('Кейдж'), (375, 216))
        self.assertLess(self.stats('Hero')[0], boosted_donor[0])
        self.manager.apply_artifact_bonuses(self.db)
        self.assertEqual(self.stats('Кейдж'), (375, 216))
        with self.assertRaises(ValueError):
            transfer_artifact(self.db, 'Север', 'Hero', '0', 1, self.manager)

    def test_replacement_removes_old_bonus_and_honors_season(self):
        self.db.executescript('''
            INSERT INTO artifacts VALUES(2,100,100,'Зима','','Winter',100,0,0);
            INSERT INTO hero_equipment VALUES('Мятежники','Кейдж','weapon',1,'');
            UPDATE hero_equipment SET artifact_id=2 WHERE faction_name='Север';
        ''')
        self.manager.apply_artifact_bonuses(self.db)
        self.assertEqual(self.stats('Кейдж'), (375,216))
        transfer_artifact(self.db, 'Север', 'Hero', '0', 2, self.manager)
        self.assertEqual(self.stats('Кейдж'), (250,180))
        self.assertEqual(list(self.db.execute("SELECT slot_type FROM hero_equipment WHERE faction_name='Мятежники' ORDER BY slot_type")),
                         [(str(i),) for i in range(5)])

    def test_starting_purse_is_not_refilled_on_controller_recreation(self):
        rebels.initialize_resources(self.db, new_uprising=True)
        self.assertEqual(dict(self.db.execute("SELECT resource_type,amount FROM resources WHERE faction='Мятежники'"))['Кроны'],100000)
        for amount in (0,42,100000):
            self.db.execute("UPDATE resources SET amount=? WHERE faction='Мятежники' AND resource_type='Кроны'",(amount,))
            rebels.initialize_resources(self.db)
            self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE faction='Мятежники' AND resource_type='Кроны'").fetchone()[0],amount)

    def test_successful_uprising_seeds_cash_and_another_city_does_not_reset_it(self):
        self.db.execute('ALTER TABLE cities ADD COLUMN color_faction')
        self.db.execute("UPDATE cities SET faction='Север'")
        self.db.execute('DELETE FROM garrisons')
        node = next(n for n in ast.parse(Path('diversion.py').read_text(encoding='utf-8')).body
                    if isinstance(n,ast.FunctionDef) and n.name=='execute_diversion_operation')
        ns = {'random':random,'show_result_popup':lambda *a:None}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'diversion.py','exec'),ns)
        with patch.dict(sys.modules,{'game_process':SimpleNamespace(refresh_map=lambda:None)}):
            for city, expected in [('Home',100000),('Safe',47)]:
                ns['execute_diversion_operation'](self.db,'Эльфы','Мятеж',{},'Север',
                    {'Север':{'cities_without_garrison':[city]}},rebels_count=10)
                self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE faction='Мятежники' AND resource_type='Кроны'").fetchone()[0],expected)
                self.db.execute("UPDATE resources SET amount=47 WHERE faction='Мятежники' AND resource_type='Кроны'")

    def test_gift_refreshes_active_controller_stats_before_next_turn(self):
        refreshed = []
        controller = SimpleNamespace(load_army=lambda:self.stats('Кейдж'),load_garrison=lambda:{'Home':1})
        game = SimpleNamespace(_active_game_screen=SimpleNamespace(
            season_manager=self.manager,ai_controllers={'Мятежники':controller}),
            refresh_map=lambda:refreshed.append(True))
        with patch.dict(sys.modules,{'game_process':game}):
            transfer_artifact(self.db,'Север','Hero','0',1)
        self.assertEqual(controller.army,(375,216))
        self.assertEqual(refreshed,[True])

    def arrange_order(self):
        self.db.executescript('''
            INSERT INTO cities VALUES(3,'Border','Вампиры','[200,200]'),(4,'Target','Вампиры','[300,200]');
            INSERT INTO roads VALUES(1,3),(3,4);
            INSERT INTO rebel_attack_order VALUES(1,'Target','Вампиры');
        ''')

    def test_distant_order_takes_approaches_and_survives_failed_attacks(self):
        self.arrange_order()
        calls = []
        ai = SimpleNamespace(db_connection=self.db, get_factions_at_war=lambda:['Вампиры'],
                             attack_city=lambda *args:calls.append(args))
        rebels.attack(ai)
        rebels.attack(ai)
        self.assertEqual(calls,[('Border','Вампиры')]*2)
        self.assertEqual(self.db.execute('SELECT count(*) FROM rebel_attack_order').fetchone()[0],1)
        self.db.execute("UPDATE cities SET faction='Мятежники' WHERE name='Border'")
        def capture(city, faction):
            calls.append((city,faction))
            self.db.execute("UPDATE cities SET faction='Мятежники' WHERE name=?",(city,))
        ai.attack_city = capture
        rebels.attack(ai)
        self.assertEqual(calls[-1],('Target','Вампиры'))
        self.assertEqual(self.db.execute('SELECT count(*) FROM rebel_attack_order').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT relationship FROM diplomacies').fetchone()[0],'война')

    def test_reverse_diplomacy_row_does_not_stop_war_after_order_is_completed(self):
        self.db.execute("INSERT INTO diplomacies VALUES('Вампиры','Мятежники','мир')")
        rebels.declare_war(self.db,'Вампиры')
        self.assertEqual(self.db.execute("SELECT relationship FROM diplomacies WHERE faction1='Мятежники'").fetchone()[0],'война')
        self.assertEqual(self.db.execute("SELECT relationship FROM diplomacies WHERE faction1='Вампиры'").fetchone()[0],'война')

    def test_orders_never_teleport_through_player_territory(self):
        self.arrange_order()
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Border'")
        self.assertEqual(rebels.offensive_route(self.db,'Target','Вампиры'),[])
        ai = SimpleNamespace(db_connection=self.db,get_factions_at_war=lambda:['Вампиры'],
                             attack_city=lambda *args:self.fail('Illegal attack'))
        rebels.attack(ai)
        self.assertEqual(self.db.execute('SELECT count(*) FROM rebel_attack_order').fetchone()[0],1)

    def test_order_captures_neutral_approach_using_the_normal_attack_path(self):
        self.arrange_order()
        self.db.execute("UPDATE cities SET faction='Нейтрал' WHERE name='Border'")
        calls=[]
        ai=SimpleNamespace(db_connection=self.db,get_factions_at_war=lambda:['Вампиры'],
                           attack_city=lambda *args:calls.append(args))
        rebels.attack(ai)
        self.assertEqual(calls,[('Border','Нейтрал')])

    def test_existing_unique_index_and_captured_buildings_do_not_abort_rebel_turn(self):
        from city_construction import ensure_unique_buildings
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Home'")
        self.db.execute("INSERT INTO buildings VALUES('Home','Север','Больница',1)")
        ensure_unique_buildings(self.db)
        self.db.execute("UPDATE cities SET faction='Мятежники' WHERE name='Home'")
        self.db.execute("UPDATE units SET consumption=0 WHERE faction='Мятежники'")
        cls=extracted_class('ii.py','AIController')
        ai_strategy.apply_ai_improvements(cls)
        ai=cls('Мятежники',self.db,self.manager)
        for name in ('update_trade_resources_from_db','process_trade_agreements','_apply_supply_line_losses'):
            setattr(ai,name,lambda:None)
        calls=[]
        ai.attack_enemy_cities=lambda:calls.append('attack')
        ai.save_results_to_db=lambda:None
        ai.make_turn()
        self.assertEqual(ai.turn,1)
        self.assertEqual(calls,['attack'])
        self.assertEqual(self.db.execute("SELECT faction FROM buildings WHERE building_type='Больница'").fetchone()[0],'Мятежники')
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM buildings WHERE building_type='Больница'").fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM buildings WHERE building_type='Фабрика'").fetchone()[0],1)
        self.assertGreater(self.db.execute("SELECT unit_count FROM garrisons WHERE unit_name='Мятежники'").fetchone()[0],10)

    def test_rebels_commit_full_force_even_against_a_stronger_defender(self):
        ai = SimpleNamespace(faction='Мятежники')
        self.assertEqual(ai_strategy.can_attack_target(ai,'Target',1),(True,1.0))
        self.assertEqual(ai_strategy.can_attack_target(ai,'Target',0),(False,1.0))

    def test_active_attack_executes_order_with_all_soldiers_and_one_action_per_turn(self):
        self.arrange_order()
        cls = extracted_class('ii.py','AIController')
        ai_strategy.apply_ai_improvements(cls)
        ai = cls('Мятежники',self.db,self.manager)
        battles = []
        def fight(**kwargs):
            battles.append(kwargs)
            return {'winner':'attacker','efficiency_ratio':1}
        # Isolate the battle result and map animation; use real road, staging,
        # collection, class checks, army selection and ownership persistence.
        with patch.dict(sys.modules, {'fight': SimpleNamespace(fight=fight)}), \
             patch('terrain_journeys.start_journey',return_value=False), \
             patch('troop_movement.queue_ai_march'):
            ai.attack_enemy_cities()
            self.assertEqual(len(battles),1)
            army = {u['unit_name']:u['unit_count'] for u in battles[0]['attacking_army']}
            self.assertEqual(army,{'Мятежники':10,'Кейдж':1})
            self.assertEqual(self.db.execute("SELECT faction FROM cities WHERE name='Border'").fetchone()[0],'Мятежники')
            ai.attack_enemy_cities()
            self.assertEqual(len(battles),1)
        self.assertEqual(self.db.execute('SELECT count(*) FROM rebel_attack_order').fetchone()[0],1)

    def test_rebel_attack_waits_in_forest_like_other_factions(self):
        from terrain_journeys import ensure_schema
        self.arrange_order()
        ensure_schema(self.db)
        self.db.execute("INSERT INTO map_features VALUES(1,'forest',1,3,.5,150,150,2,1)")
        cls=extracted_class('ii.py','AIController')
        ai_strategy.apply_ai_improvements(cls)
        ai=cls('Мятежники',self.db,self.manager)
        fight=Mock(side_effect=AssertionError('Battle before arrival'))
        with patch.dict(sys.modules,{'fight':SimpleNamespace(fight=fight)}):
            ai.attack_enemy_cities()
        fight.assert_not_called()
        journey=self.db.execute('SELECT faction,destination,ready_turn FROM terrain_journeys').fetchone()
        self.assertEqual(journey,('Мятежники','Border',2))
        self.assertEqual(self.db.execute("SELECT faction FROM cities WHERE name='Border'").fetchone()[0],'Вампиры')
        self.assertTrue(ai._action_taken_this_turn)

    def test_active_turn_builds_produces_and_hires_with_real_persistence(self):
        cls = extracted_class('ii.py','AIController')
        ai_strategy.apply_ai_improvements(cls)
        ai = cls('Мятежники',self.db,self.manager,player_faction='Север')
        for name in ('update_trade_resources_from_db','process_trade_agreements','_apply_supply_line_losses'):
            setattr(ai,name,lambda:None)
        ai.save_results_to_db = lambda:None
        ai.make_turn()
        self.assertEqual(ai.turn,1)
        buildings = dict(self.db.execute("SELECT building_type,count FROM buildings WHERE faction='Мятежники'"))
        self.assertEqual(buildings.get('Больница'),1)
        self.assertEqual(buildings.get('Фабрика'),1)
        resources = dict(self.db.execute("SELECT resource_type,amount FROM resources WHERE faction='Мятежники'"))
        self.assertGreater(resources['Население'],100)
        self.assertGreater(ai.money_up,0)
        self.assertGreater(resources['Кристаллы'],0)
        count = self.db.execute("SELECT unit_count FROM garrisons WHERE unit_name='Мятежники'").fetchone()[0]
        self.assertGreater(count,10)
        self.assertEqual(resources['Кроны'],ai.resources['Кроны'])
        ai.make_turn()
        self.assertEqual(ai.turn,2)
        self.assertGreater(self.db.execute("SELECT amount FROM resources WHERE faction='Мятежники' AND resource_type='Население'").fetchone()[0],resources['Население'])

    def test_recruiting_in_one_city_does_not_duplicate_other_garrisons(self):
        self.db.execute("UPDATE cities SET faction='Мятежники' WHERE name='Safe'")
        self.db.execute("INSERT INTO garrisons VALUES('Safe','Мятежники',3,'',0)")
        cls = extracted_class('ii.py','AIController')
        ai_strategy.apply_ai_improvements(cls)
        ai = cls('Мятежники',self.db,self.manager)
        for name in ('update_trade_resources_from_db','process_trade_agreements','_apply_supply_line_losses'):
            setattr(ai,name,lambda:None)
        ai.save_results_to_db = lambda:None
        ai.make_turn()
        self.assertEqual(self.db.execute("SELECT unit_count FROM garrisons WHERE city_name='Safe'").fetchone()[0],3)
