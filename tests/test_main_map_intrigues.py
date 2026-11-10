import json
import random
import sqlite3
import unittest
from unittest.mock import patch
import main_map_intrigues as plots


def fixture():
    db=sqlite3.connect(':memory:')
    db.executescript('''
        CREATE TABLE cities(id INTEGER PRIMARY KEY,name TEXT UNIQUE,faction TEXT);
        INSERT INTO cities VALUES(1,'Дом','Север'),(2,'Вражеский','Адепты'),
            (3,'Нейтральный','Нейтрал'),(4,'Дальний','Адепты'),(5,'Союзный','Эльфы');
        CREATE TABLE roads(city1 INTEGER,city2 INTEGER);INSERT INTO roads VALUES(1,2),(2,4);
        CREATE TABLE diplomacies(faction1 TEXT,faction2 TEXT,relationship TEXT,UNIQUE(faction1,faction2));
        INSERT INTO diplomacies VALUES('Север','Адепты','война'),('Север','Эльфы','союз');
        CREATE TABLE resources(faction TEXT,resource_type TEXT,amount INTEGER);
        INSERT INTO resources VALUES('Север','Кроны',100000),('Север','Кристаллы',1000),('Север','Население',200);
        CREATE TABLE buildings(city_name TEXT,faction TEXT,building_type TEXT,count INTEGER);
        INSERT INTO buildings VALUES('Дом','Север','Фабрика',1),('Дом','Север','Больница',1);
        CREATE TABLE turn(turn_count INTEGER);INSERT INTO turn VALUES(3);
        CREATE TABLE user_faction(faction_name TEXT);INSERT INTO user_faction VALUES('Север');
        CREATE TABLE units(unit_name TEXT,faction TEXT);
        CREATE TABLE garrisons(city_name TEXT,unit_name TEXT,unit_count INTEGER);
    ''')
    plots.ensure_schema(db);db.commit()
    return db


class MainIntriguesTests(unittest.TestCase):
    def setUp(self):self.db=fixture();self.addCleanup(self.db.close)

    def amount(self,resource='Кроны'):
        return self.db.execute('SELECT amount FROM resources WHERE resource_type=?',(resource,)).fetchone()[0]

    def offer(self,condition='governor'):
        self.db.execute('''INSERT INTO map_intrigue_offers(faction,city,enemy,noble,condition,ally,price,created,deadline)
            VALUES('Север','Вражеский','Адепты','Барон Ренар',?,'Эльфы',?,3,8)''',(condition,20000 if condition=='rescue' else 0))
        return self.db.execute('SELECT MAX(id) FROM map_intrigue_offers').fetchone()[0]

    def uncover(self,kind,city='Дом'):
        self.db.execute('INSERT INTO map_city_secrets(faction,city,kind,stage,last_turn) VALUES(?,?,?,2,2)',('Север',city,kind))

    def test_frontier_offer_is_persistent_once_per_turn_and_requires_war(self):
        plots.advance(self.db,'Север',random.Random(2))
        before=list(self.db.execute('SELECT * FROM map_intrigue_offers'))
        self.assertEqual(len(before),1);self.assertEqual(before[0][2],'Вражеский')
        plots.advance(self.db,'Север',random.Random(9));self.assertEqual(before,list(self.db.execute('SELECT * FROM map_intrigue_offers')))
        self.db.execute("UPDATE diplomacies SET relationship='мир' WHERE faction2='Адепты'")
        self.db.execute('UPDATE turn SET turn_count=4');plots.advance(self.db,'Север')
        self.assertEqual(self.db.execute('SELECT status FROM map_intrigue_offers').fetchone()[0],'expired')

    def test_rescue_is_paid_once_and_insufficient_payment_rolls_back(self):
        offer=self.offer('rescue');self.db.execute("UPDATE resources SET amount=100 WHERE resource_type='Кроны'")
        with self.assertRaises(ValueError):plots.accept_offer(self.db,'Север',offer)
        self.assertEqual(self.amount(),100)
        self.assertEqual(self.db.execute('SELECT status FROM map_intrigue_offers').fetchone()[0],'offered')
        self.db.execute("UPDATE resources SET amount=50000 WHERE resource_type='Кроны'")
        plots.accept_offer(self.db,'Север',offer);self.assertEqual(self.amount(),30000)
        with self.assertRaises(ValueError):plots.accept_offer(self.db,'Север',offer)
        self.assertEqual(self.amount(),30000)

    def test_betrayal_declares_war_in_both_directions_and_removes_truce(self):
        self.db.executescript("CREATE TABLE truces(faction1,faction2,truce_until_turn); INSERT INTO truces VALUES('Эльфы','Север',50);")
        plots.accept_offer(self.db,'Север',self.offer('betray'))
        self.assertTrue(plots._relation(self.db,'Север','Эльфы','война'))
        self.assertEqual(self.db.execute("SELECT relationship FROM diplomacies WHERE faction1='Эльфы' AND faction2='Север'").fetchone()[0],'война')
        self.assertFalse(list(self.db.execute('SELECT * FROM truces')))

    def test_gate_is_consumed_once_only_by_player_before_deadline_no_unit_movement(self):
        offer=self.offer();plots.accept_offer(self.db,'Север',offer)
        army=[dict(units_stats={'Защита':200,'Урон':50})]
        self.assertFalse(plots.apply_gate(self.db,'Элины','Вражеский',army))
        self.assertTrue(plots.apply_gate(self.db,'Север','Вражеский',army));self.assertEqual(army[0]['units_stats']['Защита'],100)
        self.assertFalse(plots.apply_gate(self.db,'Север','Вражеский',army));self.assertEqual(army[0]['units_stats']['Защита'],100)
        self.assertEqual(plots.owner(self.db,'Вражеский'),'Адепты');self.assertFalse(list(self.db.execute('SELECT * FROM garrisons')))
        other=self.offer();plots.accept_offer(self.db,'Север',other);self.db.execute('UPDATE turn SET turn_count=8')
        self.assertFalse(plots.apply_gate(self.db,'Север','Вражеский',army))

    def test_capture_is_explicit_reward_once_and_new_capture_invalidates_previous_choice(self):
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Вражеский'")
        plots.captured(self.db,'Вражеский','Север',1);plots.captured(self.db,'Вражеский','Север',1)
        self.assertEqual(self.amount(),100000)
        plots.captured(self.db,'Вражеский','Север',2)
        pending=plots.journal(self.db,'Север')['captures'];self.assertEqual(len(pending),1)
        plots.settle_capture(self.db,'Север',pending[0]['id'],'plunder')
        self.assertEqual((self.amount(),self.amount('Кристаллы')),(115000,6000))
        with self.assertRaises(ValueError):plots.settle_capture(self.db,'Север',pending[0]['id'],'plunder')
        self.assertEqual(self.amount(),115000)

    def test_lost_city_cannot_be_looted_and_breaking_promise_blocks_new_offers(self):
        offer=self.offer();plots.accept_offer(self.db,'Север',offer)
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Вражеский'")
        plots.captured(self.db,'Вражеский','Север',1)
        capture=plots.journal(self.db,'Север')['captures'][0]['id']
        self.db.execute("UPDATE cities SET faction='Адепты' WHERE name='Вражеский'")
        with self.assertRaises(ValueError):plots.settle_capture(self.db,'Север',capture,'plunder')
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Вражеский'")
        plots.settle_capture(self.db,'Север',capture,'plunder')
        self.db.execute('UPDATE turn SET turn_count=12')
        self.db.execute("UPDATE cities SET faction='Адепты' WHERE name='Вражеский'")
        plots.advance(self.db,'Север');self.assertEqual(self.db.execute('SELECT COUNT(*) FROM map_intrigue_offers').fetchone()[0],1)

    def test_city_war_hook_only_queues_player_captures_not_defenses_or_ai(self):
        from city_war import record_capture
        record_capture(self.db,'Вражеский','Адепты','battle_capture')
        self.assertFalse(list(self.db.execute('SELECT * FROM map_intrigue_captures')))
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Вражеский'")
        record_capture(self.db,'Вражеский','Север','battle_capture')
        self.assertEqual(len(plots.journal(self.db,'Север')['captures']),1)
        record_capture(self.db,'Вражеский','Север','battle')
        self.assertEqual(len(plots.journal(self.db,'Север')['captures']),1)

    def test_tavern_conversation_is_free_persistent_and_neutral_city_uses_tribute(self):
        row=plots.investigate(self.db,'Север','Нейтральный');self.assertEqual(row['kind'],'tribute')
        self.assertEqual(row['stage'],2);self.assertEqual(self.amount(),100000)
        with self.assertRaises(ValueError):plots.investigate(self.db,'Север','Нейтральный')
        plots.resolve_secret(self.db,'Север','Нейтральный','exploit')
        self.assertEqual(self.amount(),135000)
        with self.assertRaises(ValueError):plots.resolve_secret(self.db,'Север','Нейтральный','exploit')

    def test_factory_policy_is_permanent_local_and_capture_clears_it(self):
        self.uncover('factory');plots.resolve_secret(self.db,'Север','Дом','exploit')
        self.assertEqual(self.amount('Кристаллы'),1000)
        self.assertEqual(plots.economy_adjustments(self.db,'Север',crowns=1000,crystals=10000,growth=400),dict(crowns=0,crystals=1500,population=-60))
        self.db.execute('UPDATE turn SET turn_count=1000')
        self.assertEqual(plots.economy_adjustments(self.db,'Север',crystals=10000)['crystals'],1500)
        self.db.execute("UPDATE cities SET faction='Адепты' WHERE name='Дом'")
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Дом'")
        self.assertEqual(plots.economy_adjustments(self.db,'Север',crystals=10000)['crystals'],0)

    def test_reveal_and_encouragement_have_opposite_local_income_effects_without_destroying_buildings(self):
        self.uncover('factory');plots.resolve_secret(self.db,'Север','Дом','expose')
        self.assertTrue(self.db.execute("SELECT 1 FROM buildings WHERE building_type='Фабрика'").fetchone())
        self.assertTrue(self.db.execute("SELECT 1 FROM buildings WHERE building_type='Больница'").fetchone())
        self.assertEqual(plots.economy_adjustments(self.db,'Север',crystals=10000,growth=400),dict(crowns=0,crystals=-2500,population=100))
        self.db.execute('DELETE FROM map_city_secrets');self.uncover('hospital')
        plots.resolve_secret(self.db,'Север','Дом','exploit')
        self.assertEqual(self.amount('Население'),200);self.assertEqual(self.amount(),100000)
        self.assertEqual(plots.economy_adjustments(self.db,'Север',crowns=1000,crystals=10000),dict(crowns=350,crystals=-3500,population=0))
        self.db.execute('DELETE FROM map_city_secrets');self.uncover('hospital')
        plots.resolve_secret(self.db,'Север','Дом','expose')
        self.assertEqual(plots.economy_adjustments(self.db,'Север',crowns=1000,crystals=10000),dict(crowns=-350,crystals=3500,population=0))

    def test_save_load_does_not_reroll_and_other_faction_cannot_use_choice(self):
        self.offer();plots.investigate(self.db,'Север','Нейтральный');self.db.commit()
        saved=sqlite3.connect(':memory:');self.addCleanup(saved.close);self.db.backup(saved)
        self.assertEqual(plots.journal(self.db,'Север'),plots.journal(saved,'Север'))
        with self.assertRaises(ValueError):plots.accept_offer(saved,'Элины',1)

    def test_secret_production_is_counted_once_in_real_player_income_and_upkeep(self):
        from test_adaptive_market import production
        base=production('economic.py','Север','Смирение',full=True)
        with patch('main_map_intrigues.economy_adjustments',side_effect=lambda *a,**kw:dict(crowns=0,crystals=1000 if kw.get('crystals') else 0,population=0)):
            actual=production('economic.py','Север','Смирение',full=True)
        self.assertEqual(actual,(base[0]+1000,1))

    def test_sabotage_reaches_the_actual_tactical_battle_handoff(self):
        import contextlib,io
        from test_battle_ui import combat_namespace
        from test_tactical_combat import unit
        from tactical_combat import TacticalBattle
        from unittest.mock import Mock
        from test_otherworlds import fixture as campaign_fixture
        db=campaign_fixture();self.addCleanup(db.close)
        db.executescript("CREATE TABLE user_faction(faction_name); INSERT INTO user_faction VALUES('Север');"
                        "CREATE TABLE diplomacies(faction1,faction2,relationship); INSERT INTO diplomacies VALUES('Север','Адепты','война');")
        db.execute("UPDATE cities SET faction='Адепты' WHERE name='Safe'")
        db.execute('UPDATE turn SET turn_count=3');plots.ensure_schema(db)
        seen=[]
        def battle(a,d,*args):
            seen.append(d[0]['units_stats']['Защита'])
            model=TacticalBattle(a,d);model.winner='defender';model.round=2;model._snapshot();return model
        ns=combat_namespace();ns.update(update_garrisons_after_battle=Mock(),update_results_table=Mock(),
            cleanup_equipment_after_battle=Mock(),show_battle_report=Mock())
        with patch('tactical_battle_bridge.request_battle',side_effect=battle),patch('city_war.record_battle'), \
             patch('kivy.clock.Clock.schedule_once'),contextlib.redirect_stdout(io.StringIO()):
            ns['fight']('Home','Safe',[unit('Enemy',count=10)],[unit('troop1',count=1000)],'Север','Адепты',db)
            db.execute("INSERT INTO map_intrigue_offers(faction,city,enemy,noble,condition,price,created,deadline,status) VALUES('Север','Safe','Адепты','Барон Ренар','governor',0,3,8,'accepted')")
            ns['fight']('Home','Safe',[unit('Enemy',count=10)],[unit('troop1',count=1000)],'Север','Адепты',db)
        self.assertEqual(seen[1],seen[0]*.5)


class CompanionTemperTests(unittest.TestCase):
    def test_warning_conflict_monster_boost_and_recovery_recalculate_without_stacking(self):
        from test_soul_pact import SoulPactTests
        import mirror_monster_quest as hunt
        fixture=SoulPactTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        db=fixture.db;prize=hunt.claim_heart(db,'Север','Hero');plots.ensure_schema(db)
        base=(prize['attack'],prize['defense']);plots.react(db,'Север',False)
        self.assertEqual(db.execute('SELECT loyalty FROM map_companion_temper').fetchone()[0],40)
        self.assertEqual((hunt.set_form(db,'Север','noble')['attack']),base[0])
        plots.react(db,'Север',False)
        for _ in range(3):self.assertEqual(hunt.set_form(db,'Север','noble')['attack'],int(base[0]*.75))
        data=hunt.companion_form(db,'Север');monster=hunt.set_form(db,'Север','monster')
        self.assertEqual(monster['attack'],int((data['base_attack']//2)*1.1))
        db.execute('UPDATE turn SET turn_count=3');plots.advance(db,'Север')
        self.assertEqual(hunt.set_form(db,'Север','noble')['attack'],base[0])
        plots.react(db,'Север',True)
        self.assertEqual(db.execute('SELECT loyalty,blood FROM map_companion_temper').fetchone(),(30,1))


if __name__=='__main__':unittest.main()
