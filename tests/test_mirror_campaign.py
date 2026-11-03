import ast
import math
import json
from pathlib import Path
import random
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest

from test_otherworlds import fixture
import otherworlds as w
import portal_items as items
import otherworld_quests as q
from otherworld_themes import THEMES,asset_exists
from utils.resource_caps import caps


class MirrorCampaignTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)
        self.db.execute('DELETE FROM artifacts')
        for slot in range(5):
            self.db.execute('INSERT INTO artifacts VALUES(?,?,?,?,?,?,?,?,0)',
                (slot+1,10*(slot+1),20*(slot+1),'Все','files/pict/hire/sword.png','Analog'+str(slot),1000*(slot+1),slot))
        self.db.execute('UPDATE turn_check_move SET moves_left=100')
        self.db.commit()
        self.p=w.enter(self.db,'Север','Home')

    def turn(self,t):
        self.db.execute('UPDATE turn SET turn_count=?',(t,))
        self.db.execute('UPDATE turn_check_move SET moves_left=100')
        self.db.commit()

    def at(self,city):
        self.db.execute("UPDATE portal_parties SET city_id=? WHERE faction='Север'",(city,));self.db.commit()

    def solve_detective(self):
        run=q.state(self.db,'Север');d=q.details(run)['detective']
        self.at(d['cities'][0]);q.action(self.db,'Север','witness')
        self.at(d['cities'][1]);q.action(self.db,'Север','ledger')
        self.at(d['cities'][2]);q.action(self.db,'Север','accuse',d['suspects'][run['culprit']])

    def solve_war(self,side=None):
        war=q.details(q.state(self.db,'Север'))['war']
        side=war['sides'][1 if side else 0]
        self.at(war['embassy']);q.action(self.db,'Север','side',side)
        self.at(war['supplies'][war['sides'].index(side)]);q.action(self.db,'Север','supply')
        self.at(war['target'])
        def win(unit,guard,*args,**kwargs):guard['unit_count']=0
        result=w.fight_guards(self.db,'Север',win)
        self.assertTrue(result['quest_win'])
        self.assertEqual(result['guards'][0]['initial_count']*result['guards'][0]['defense'],170_000_000)

    def test_clues_stay_in_source_cities_and_never_appear_at_accusation_or_after_solving(self):
        q.begin(self.db,'Север',random.Random(54))
        run=q.state(self.db,'Север');d=q.details(run)['detective']
        witness,ledger,accusation=d['cities']
        self.assertTrue(all(not q.local_detective_clue(run,city) for city in range(1,8)))

        self.at(witness);q.action(self.db,'Север','witness')
        run=q.state(self.db,'Север')
        self.assertIn(d['tokens'][run['culprit']],q.local_detective_clue(run,witness))
        self.assertFalse(q.local_detective_clue(run,ledger))
        self.at(ledger);q.action(self.db,'Север','ledger')
        run=q.state(self.db,'Север')
        self.assertNotIn('Записи:',q.local_detective_clue(run,witness))
        self.assertNotIn('Улика свидетеля:',q.local_detective_clue(run,ledger))
        for name,token in zip(d['suspects'],d['tokens']):self.assertIn(name+' — '+token,q.local_detective_clue(run,ledger))
        for city in set(range(1,8))-{witness,ledger}:
            self.assertEqual(q.local_detective_clue(run,city),'')
        self.at(accusation);q.action(self.db,'Север','accuse',d['suspects'][run['culprit']])
        run=q.state(self.db,'Север')
        self.assertTrue(all(not q.local_detective_clue(run,city) for city in range(1,8)))

    def test_quest_garrison_has_exactly_170_million_defense_for_either_side_in_any_city(self):
        q.begin(self.db,'Север',random.Random(54))
        scenario=q.details(q.state(self.db,'Север'));war=scenario['war']
        for side in war['sides']:
            for city in w.cities(self.db,'Север'):
                war['target']=city['id']
                self.db.execute("UPDATE portal_quest_runs SET war=2,side=?,scenario=? WHERE faction='Север'",
                                (side,json.dumps(scenario)))
                guard,enemy=w.guard_profile(self.db,'Север',city)
                self.assertEqual(guard['initial_count']*guard['defense'],170_000_000)
                self.assertEqual(guard['units_stats']['Защита'],guard['defense'])
                self.assertNotEqual(enemy,side)
        self.db.execute("UPDATE portal_quest_runs SET war=0 WHERE faction='Север'")
        normal,_=w.guard_profile(self.db,'Север',city)
        self.assertEqual(normal['unit_count'],city['guards'])
        self.assertEqual(normal['defense'],75+city['id']*20)

    def test_all_factions_have_independent_art_rosters_and_city_names(self):
        maps=set();portraits=set();relics=set()
        for faction in THEMES:
            maps.add(w.world(self.db,faction)['background'])
            roster=w.unit_offers(self.db,faction)
            portraits.update(u['image_path'] for u in roster)
            relics.update(a['image_url'] for a in w.artifact_offers(self.db,faction))
            self.assertTrue(all(asset_exists(u['image_path']) for u in roster))
            self.assertEqual(len(w.cities(self.db,faction)),7)
        self.assertEqual(len(maps),5);self.assertEqual(len(portraits),25);self.assertEqual(len(relics),25)

    def test_every_unit_role_has_different_attack_and_defense_in_each_faction(self):
        rosters=[w.unit_offers(self.db,faction) for faction in THEMES]
        for role in range(5):
            self.assertEqual(len({roster[role]['attack'] for roster in rosters}),5)
            self.assertEqual(len({roster[role]['defense'] for roster in rosters}),5)
        self.assertGreater(rosters[0][4]['defense'],rosters[1][4]['defense'])

    def test_old_hired_units_upgrade_without_resetting_party_xp_or_market_stock(self):
        w.recruit(self.db,'Север',2)
        name='Странник: '+w.unit_offers(self.db,'Север')[1]['unit_name']+' / Север'
        self.db.execute('UPDATE units SET attack=1,defense=1 WHERE unit_name=?',(name,))
        self.db.execute('UPDATE portal_presentation SET version=1')
        self.db.commit()
        before={table:list(self.db.execute('SELECT * FROM '+table))
                for table in ('garrisons','portal_market','portal_parties','portal_roads')}
        w.upgrade_world(self.db)
        offer=w.unit_offers(self.db,'Север')[1]
        self.assertEqual(self.db.execute('SELECT attack,defense FROM units WHERE unit_name=?',(name,)).fetchone(),
                         (offer['attack'],offer['defense']))
        for table,rows in before.items():self.assertEqual(list(self.db.execute('SELECT * FROM '+table)),rows)
        self.db.execute('UPDATE units SET attack=999 WHERE unit_name=?',(name,))
        w.upgrade_world(self.db)
        self.assertEqual(self.db.execute('SELECT attack FROM units WHERE unit_name=?',(name,)).fetchone()[0],999)

    def test_only_class_three_can_buy_and_wrong_class_does_not_spend(self):
        self.db.execute("UPDATE units SET unit_class='2' WHERE unit_name='Hero'");self.db.commit()
        before=list(self.db.execute('SELECT * FROM resources'))
        with self.assertRaisesRegex(ValueError,'3 класса'):w.buy_artifact(self.db,'Север',1)
        self.assertEqual(list(self.db.execute('SELECT * FROM resources')),before)
        self.assertFalse(self.db.execute('SELECT 1 FROM portal_market').fetchone())

    def test_exact_strength_and_price_based_five_to_twelve_turn_lifetime(self):
        offers=w.artifact_offers(self.db,'Север')
        self.assertEqual(min(a['duration'] for a in offers),5)
        self.assertEqual(max(a['duration'] for a in offers),12)
        for i,offer in enumerate(offers,1):
            self.assertEqual(offer['attack'],math.ceil(i*10*3.3))
            self.assertEqual(offer['defense'],math.ceil(i*20*3.3))

    def test_expiry_restores_previous_equipment_and_hides_expired_item(self):
        self.db.execute("INSERT INTO hero_equipment VALUES('Север','Hero','0',1,'old.png')");self.db.commit()
        w.buy_artifact(self.db,'Север',1)
        aid=self.db.execute('SELECT artifact_id FROM portal_artifacts').fetchone()[0]
        self.turn(4);self.assertEqual(items.remaining(self.db,aid),1);self.assertFalse(items.expire(self.db))
        self.turn(5);self.assertTrue(items.expire(self.db))
        self.assertEqual(self.db.execute('SELECT artifact_id,image_url FROM hero_equipment').fetchone(),(1,'old.png'))
        from monster_sites import artifact_visible
        self.assertFalse(artifact_visible(self.db,'Север',aid))
        self.db.commit();w.buy_artifact(self.db,'Север',1)
        self.assertNotEqual(self.db.execute('SELECT artifact_id FROM portal_artifacts').fetchone()[0],aid)

    def test_nested_temporary_items_do_not_restore_an_expired_parent(self):
        self.db.execute("INSERT INTO hero_equipment VALUES('Север','Hero','0',1,'old.png')");self.db.commit()
        long=items.issue(self.db,'Север',self.p['camp'],items.reward(self.db,'Север',102));self.db.commit()
        short=items.issue(self.db,'Север',self.p['camp'],w.artifact_offers(self.db,'Север')[0]);self.db.commit()
        self.turn(1)
        later=dict(w.artifact_offers(self.db,'Север')[0],duration=12)
        latest=items.issue(self.db,'Север',self.p['camp'],later);self.db.commit()
        self.turn(5);items.expire(self.db);self.db.commit()
        self.assertEqual(self.db.execute('SELECT artifact_id FROM hero_equipment').fetchone()[0],latest)
        self.turn(13);items.expire(self.db);self.db.commit()
        self.assertEqual(self.db.execute('SELECT artifact_id FROM hero_equipment').fetchone()[0],long)
        self.turn(25);items.expire(self.db);self.db.commit()
        self.assertEqual(self.db.execute('SELECT artifact_id FROM hero_equipment').fetchone()[0],1)

    def test_legendary_upgrade_keeps_original_deadline(self):
        from monster_sites import ensure_schema,upgrade_artifact
        w.buy_artifact(self.db,'Север',1)
        aid=self.db.execute('SELECT artifact_id FROM portal_artifacts').fetchone()[0]
        ensure_schema(self.db)
        self.db.execute("INSERT INTO monster_progress(faction,relic_earned) VALUES('Север',1)")
        self.db.commit()
        upgraded=upgrade_artifact(self.db,'Север','artifacts',aid,'attack','Hero','0')
        new_id=self.db.execute('SELECT artifact_id FROM hero_equipment').fetchone()[0]
        self.assertNotEqual(aid,new_id)
        self.assertEqual(items.remaining(self.db,aid),items.remaining(self.db,new_id))
        self.turn(5);items.expire(self.db)
        self.assertIsNone(self.db.execute('SELECT artifact_id FROM hero_equipment').fetchone()[0])

    def test_wrong_accusation_is_free_but_requires_new_evidence(self):
        q.begin(self.db,'Север',random.Random(1))
        d=q.details(q.state(self.db,'Север'))['detective']
        self.at(d['cities'][0]);q.action(self.db,'Север','witness')
        self.at(d['cities'][1]);q.action(self.db,'Север','ledger')
        self.at(d['cities'][2])
        culprit=q.state(self.db,'Север')['culprit']
        before=self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0]
        q.action(self.db,'Север','accuse',d['suspects'][(culprit+1)%3])
        self.assertEqual(q.state(self.db,'Север')['detective'],0)
        self.assertEqual(q.pending(self.db,'Север'),[])
        self.assertEqual(self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0],before)

    def test_complete_quests_and_battle_at_zero_moves_only_travel_spends_actions(self):
        self.db.execute('UPDATE turn_check_move SET moves_left=0');self.db.commit()
        q.begin(self.db,'Север',random.Random(45))
        self.solve_detective();self.solve_war()
        self.assertEqual(len(q.claim(self.db,'Север')),3)
        self.assertEqual(self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0],0)
        self.assertEqual(self.db.execute('SELECT turn_count FROM turn').fetchone()[0],0)
        source=w.party(self.db,'Север')['city_id']
        neighbor=self.db.execute('SELECT CASE WHEN city1=? THEN city2 ELSE city1 END FROM portal_roads WHERE city1=? OR city2=? LIMIT 1',
                                 (source,source,source)).fetchone()[0]
        with self.assertRaises(ValueError):w.begin_beam(self.db,'Север',neighbor)
        self.db.execute('UPDATE turn_check_move SET moves_left=1');self.db.commit()
        w.begin_beam(self.db,'Север',neighbor);w.finish_beam(self.db,'Север')
        self.assertEqual(w.party(self.db,'Север')['city_id'],neighbor)
        self.assertEqual(self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0],0)

    def test_campaign_rewards_repeat_delay_and_resource_caps_do_not_stack(self):
        q.begin(self.db,'Север',random.Random(2))
        self.solve_detective();self.solve_war()
        self.assertEqual(q.pending(self.db,'Север'),[101,102,103])
        issued=q.claim(self.db,'Север')
        self.assertEqual(len(issued),3)
        self.assertTrue(all(items.remaining(self.db,aid)==25 for aid in issued))
        self.assertEqual(caps(self.db,'Север'),{'Кроны':13500000,'Кристаллы':13500000,'Рабочие':675000,'Население':135000000})
        with self.assertRaises(ValueError):q.claim(self.db,'Север')
        self.at(1);self.turn(14)
        with self.assertRaises(ValueError):q.begin(self.db,'Север')
        self.turn(15);q.begin(self.db,'Север',random.Random(3))
        self.solve_detective();self.solve_war(q.SIDES[1]);q.claim(self.db,'Север')
        self.assertEqual(q.cap_turns(self.db,'Север'),25)
        self.assertEqual(caps(self.db,'Север')['Кроны'],13500000)
        self.turn(40);items.expire(self.db)
        self.assertEqual(caps(self.db,'Север')['Кроны'],10000000)

    def test_pending_rewards_wait_until_a_champion_is_available(self):
        q.begin(self.db,'Север');self.solve_detective()
        self.db.execute("UPDATE units SET unit_class='2' WHERE unit_name='Hero'");self.db.commit()
        with self.assertRaises(ValueError):q.claim(self.db,'Север')
        self.assertEqual(q.pending(self.db,'Север'),[101])
        self.db.execute("UPDATE units SET unit_class='3' WHERE unit_name='Hero'");self.db.commit()
        q.claim(self.db,'Север');self.assertEqual(q.pending(self.db,'Север'),[])

    def test_expired_relic_loses_its_real_seasonal_stat_bonus(self):
        self.db.executescript('''CREATE TABLE units_default AS SELECT * FROM units;
            CREATE TABLE artifact_effects_log(hero_name,artifact_id,stat_name,value_change,
                PRIMARY KEY(hero_name,artifact_id,stat_name));
            CREATE TABLE ai_hero_equipment(faction_name,hero_name,slot_type,artifact_id);''')
        self.db.execute('CREATE TABLE artifacts_ai AS SELECT * FROM artifacts WHERE 0')
        cls=next(n for n in ast.parse(Path('seasons.py').read_text(encoding='utf-8')).body
                 if isinstance(n,ast.ClassDef) and n.name=='SeasonManager')
        namespace={'sqlite3':sqlite3}
        exec(compile(ast.Module(body=[cls],type_ignores=[]),'seasons.py','exec'),namespace)
        manager=namespace['SeasonManager']();manager.update(1,self.db)
        before=self.db.execute("SELECT attack FROM units WHERE unit_name='Hero'").fetchone()[0]
        w.buy_artifact(self.db,'Север',1);manager.apply_artifact_bonuses(self.db)
        boosted=self.db.execute("SELECT attack FROM units WHERE unit_name='Hero'").fetchone()[0]
        self.assertGreater(boosted,before)
        self.turn(5);manager.apply_artifact_bonuses(self.db)
        self.assertEqual(self.db.execute("SELECT attack FROM units WHERE unit_name='Hero'").fetchone()[0],before)

    def test_actual_economy_sync_uses_and_expires_the_bonus_caps(self):
        q.ensure_schema(self.db)
        self.db.execute("INSERT INTO portal_quest_buffs VALUES('Север',25)");self.db.commit()
        cls=next(n for n in ast.parse(Path('economic.py').read_text(encoding='utf-8')).body
                 if isinstance(n,ast.ClassDef) and n.name=='Faction')
        method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_sync_resources')
        namespace={}
        exec(compile(ast.Module(body=[method],type_ignores=[]),'economic.py','exec'),namespace)
        player=SimpleNamespace(conn=self.db,faction='Север',money=50000000,raw_material=50000000,
            population=200000000,free_peoples=1000000,resources={},current_consumption=0,
            max_army_limit=5000,_on_resources_changed=None)
        namespace['_sync_resources'](player)
        self.assertEqual((player.money,player.free_peoples,player.population),(13500000,675000,135000000))
        self.assertEqual(player.resources['Лимит Армии'],5000)
        self.turn(25);namespace['_sync_resources'](player)
        self.assertEqual((player.money,player.free_peoples,player.population),(10000000,500000,100000000))

    def test_beam_is_saved_blocks_other_actions_and_finishes_exactly_once(self):
        before=self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0]
        neighbor=self.db.execute('SELECT city2 FROM portal_roads WHERE city1=1 LIMIT 1').fetchone()[0]
        w.begin_beam(self.db,'Север',neighbor)
        self.assertEqual(w.party(self.db,'Север')['city_id'],1)
        with self.assertRaises(ValueError):w.trade_crystals(self.db,'Север')
        with self.assertRaises(ValueError):w.return_home(self.db,'Север')
        with self.assertRaises(ValueError):w.begin_beam(self.db,'Север',neighbor)
        w.finish_beam(self.db,'Север');w.finish_beam(self.db,'Север')
        self.assertEqual(w.party(self.db,'Север')['city_id'],neighbor)
        self.assertEqual(self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0],before-1)

    def test_all_authored_roads_work_in_both_directions_and_old_edges_are_repaired(self):
        self.db.execute('UPDATE portal_roads SET city1=3,city2=1 WHERE city1=1 AND city2=3');self.db.commit()
        w.ensure_schema(self.db)
        self.assertFalse(self.db.execute('SELECT 1 FROM portal_roads WHERE city1>city2').fetchone())
        roads=list(self.db.execute('SELECT city1,city2 FROM portal_roads'))
        for a,b in roads:
            self.at(a);w.travel(self.db,'Север',b);w.travel(self.db,'Север',a)
            self.assertEqual(w.party(self.db,'Север')['city_id'],a)

    def test_saved_temporary_gear_expires_after_reload(self):
        q.begin(self.db,'Север');self.at(q.details(q.state(self.db,'Север'))['detective']['cities'][0]);q.action(self.db,'Север','witness')
        w.buy_artifact(self.db,'Север',1)
        self.turn(5)
        with tempfile.TemporaryDirectory(dir='.release') as folder:
            path=folder+'/save.db'
            target=sqlite3.connect(path);self.db.backup(target);target.close()
            target=sqlite3.connect(path)
            try:
                items.expire(target)
                self.assertIsNone(target.execute('SELECT artifact_id FROM hero_equipment').fetchone()[0])
                self.assertEqual(q.state(target,'Север')['detective'],1)
            finally:target.close()

    def test_story_decks_do_not_repeat_until_exhausted_or_at_boundary(self):
        from otherworld_quest_pool import DETECTIVE,WARS
        seen={'detective':[],'war':[]}
        previous=None
        for cycle in range(17):
            self.at(1);self.turn(cycle*15)
            q.begin(self.db,'Север',random.Random(31+cycle))
            scenario=q.details(q.state(self.db,'Север'))
            for kind in seen:
                if previous:self.assertNotEqual(scenario[kind]['id'],previous[kind]['id'])
                seen[kind].append(scenario[kind]['id'])
            previous=scenario
            # Complete flags only here: full gameplay on both sides is tested above.
            self.db.execute("UPDATE portal_quest_runs SET finished_turn=?,repeat_turn=? WHERE faction='Север'",(cycle*15,cycle*15+15))
            self.db.commit()
        for kind,pool in (('detective',DETECTIVE),('war',WARS)):
            self.assertEqual(len(set(seen[kind][:8])),len(pool))
            self.assertEqual(len(set(seen[kind][8:16])),len(pool))

    def test_generated_routes_gate_steps_and_use_selected_supply_resource(self):
        q.begin(self.db,'Север',random.Random(45))
        run=q.state(self.db,'Север');scenario=q.details(run)
        d,war=scenario['detective'],scenario['war']
        self.assertEqual(len(set(d['cities'])),3)
        self.assertEqual(len(set([war['embassy'],*war['supplies'],war['target']])),4)
        self.assertEqual(q.objectives(self.db,'Север'),{d['cities'][0],war['embassy']})
        self.at(1)
        before=list(self.db.execute('SELECT * FROM turn_check_move'))
        with self.assertRaises(ValueError):q.action(self.db,'Север','witness')
        self.assertEqual(list(self.db.execute('SELECT * FROM turn_check_move')),before)
        self.at(war['embassy']);q.action(self.db,'Север','side',war['sides'][1])
        self.at(war['supplies'][1])
        def balance():
            return self.db.execute("SELECT amount FROM resources WHERE faction='Север' AND resource_type=?",(war['resource'],)).fetchone()[0]
        before=balance()
        q.action(self.db,'Север','supply')
        self.assertEqual(balance(),before-war['amount'])
        self.assertEqual(q.war_target(self.db,'Север',war['target']),war['sides'][0])
        self.assertIsNone(q.war_target(self.db,'Север',war['embassy']))

    def test_restarting_preserves_generated_people_clues_routes_and_story(self):
        q.begin(self.db,'Север',random.Random(82))
        run=q.state(self.db,'Север');scenario=q.details(run)
        self.at(scenario['detective']['cities'][0]);q.action(self.db,'Север','witness')
        saved=q.state(self.db,'Север')
        with self.assertRaises(ValueError):q.begin(self.db,'Север')
        self.assertEqual(q.state(self.db,'Север'),saved)
        with tempfile.TemporaryDirectory(dir='.release') as folder:
            path=folder+'/quests.db';target=sqlite3.connect(path)
            self.db.backup(target);target.close()
            target=sqlite3.connect(path)
            try:
                self.assertEqual(q.state(target,'Север'),saved)
                self.assertEqual(q.details(q.state(target,'Север')),scenario)
            finally:target.close()

    def test_old_active_campaign_keeps_its_original_people_and_routes(self):
        self.db.execute('DROP TABLE IF EXISTS portal_quest_runs')
        self.db.execute('''CREATE TABLE portal_quest_runs(faction TEXT PRIMARY KEY,cycle INTEGER,
            culprit INTEGER,detective INTEGER,war INTEGER,side TEXT,finished_turn INTEGER,repeat_turn INTEGER)''')
        self.db.execute("INSERT INTO portal_quest_runs VALUES('Север',1,1,1,1,'Лунный двор',NULL,0)")
        self.db.commit()
        run=q.state(self.db,'Север');d=q.details(run)
        self.assertEqual(d['detective']['cities'],[3,5,4])
        self.assertEqual(d['detective']['suspects'][run['culprit']],'Валтор')
        self.at(5);q.action(self.db,'Север','ledger')
        self.at(4);q.action(self.db,'Север','accuse','Валтор')
        self.at(2);q.action(self.db,'Север','supply')
        self.assertEqual(q.war_target(self.db,'Север',7),'Стеклянный престол')
        self.assertEqual(q.pending(self.db,'Север'),[101])


if __name__=='__main__':unittest.main()
