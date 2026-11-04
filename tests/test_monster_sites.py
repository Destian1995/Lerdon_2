import json
import sqlite3
import unittest

from monster_sites import (ensure_schema,sites,reward,progress,begin_hunt,resolve_hunt,finish_hunt,
    cooldown_left,effective_experience,owned_artifacts,upgrade_artifact,artifact_visible,recover_hunts)
from utils.garrison_stats import garrison_totals


def fixture():
    db=sqlite3.connect(':memory:')
    db.executescript('''CREATE TABLE cities(id,name,faction,coordinates);
        INSERT INTO cities VALUES(1,'Home','Север','[100,100]'),(2,'Away','Эльфы','[300,100]');
        CREATE TABLE turn(turn_count); INSERT INTO turn VALUES(0);
        CREATE TABLE season(season_index); INSERT INTO season VALUES(0);
        CREATE TABLE garrisons(city_name,unit_name,unit_count,unit_image,experience,UNIQUE(city_name,unit_name));
        CREATE TABLE units(unit_name,unit_class,attack,defense,durability);
        INSERT INTO units VALUES('troop','1',1000000,100,20),('hero','2',1,5,5);
        INSERT INTO garrisons VALUES('Home','troop',250,'',0),('Home','hero',1,'',0);
        CREATE TABLE resources(faction,resource_type,amount);
        INSERT INTO resources VALUES('Север','Кроны',100),('Север','Кристаллы',200);
        CREATE TABLE buildings(city_name,faction,building_type,count);
        CREATE TABLE turn_check_move(faction,moves_left); INSERT INTO turn_check_move VALUES('Север',2);
        CREATE TABLE artifacts(id INTEGER PRIMARY KEY,name,attack,defense,image_url,cost);
        INSERT INTO artifacts VALUES(1,'Blade',120,25,'',500);
        CREATE TABLE hero_equipment(faction_name,hero_name,slot_type,artifact_id);
        INSERT INTO hero_equipment VALUES('Север','hero','0',1),('Эльфы','other','0',1);
        CREATE TABLE artifact_effects_log(hero_name,artifact_id,stat_name,value_change);
        INSERT INTO artifact_effects_log VALUES('hero',1,'attack',120),('other',1,'attack',120);''')
    ensure_schema(db)
    for tier in range(1,8):
        db.execute('INSERT INTO monster_sites(id,parent_city,tier,x,y,road,ready_turn) VALUES(?,?,?,?,?,?,0)',
                   (tier,1,tier,150+tier*10,160,json.dumps([(138,130),(150+tier*10,160)])))
    db.commit()
    return db


class HuntTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)

    def turn(self,t):
        self.db.execute('UPDATE turn SET turn_count=?',(t,))
        self.db.execute("UPDATE turn_check_move SET moves_left=2")
        self.db.commit()

    def test_exact_seven_reward_levels(self):
        for tier in range(1,8):
            p=reward(tier)
            self.assertEqual(p['duration'],(7,9,10,12,13,15,16)[tier-1])
            self.assertEqual(p['defense'],90_000_000+25_000_000*(tier-1))
            self.assertEqual(p['resources'],250_000+100_000*(tier-1))
        self.assertEqual(reward(7),dict(defense=240_000_000,duration=16,resources=850_000,legendary=True))

    def test_troops_leave_before_arrival_rewards_once_and_return_without_xp_loss(self):
        eid=begin_hunt(self.db,1,'Север')
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM garrisons WHERE city_name='Home'").fetchone()[0],0)
        self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE resource_type='Кроны'").fetchone()[0],100)
        first=resolve_hunt(self.db,eid)
        self.assertTrue(first['won'])
        self.assertEqual(resolve_hunt(self.db,eid),first)
        self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE resource_type='Кроны'").fetchone()[0],250100)
        finish_hunt(self.db,eid);finish_hunt(self.db,eid)
        self.assertEqual(self.db.execute("SELECT unit_count,experience FROM garrisons WHERE unit_name='troop'").fetchone(),(250,1))
        self.assertEqual(effective_experience(self.db,'Север',0),3)
        self.turn(6)
        self.assertEqual(effective_experience(self.db,'Север',0),3)
        self.turn(7)
        self.assertEqual(effective_experience(self.db,'Север',0),0)
        self.assertEqual(effective_experience(self.db,'Север',7),7)

    def test_training_changes_real_garrison_stats_then_expires(self):
        before=garrison_totals(self.db,'Home')
        self.db.execute("UPDATE garrisons SET experience=1 WHERE unit_name='troop'")
        earned=garrison_totals(self.db,'Home')
        self.db.execute("UPDATE garrisons SET experience=0 WHERE unit_name='troop'")
        eid=begin_hunt(self.db,1,'Север');resolve_hunt(self.db,eid);finish_hunt(self.db,eid)
        boosted=garrison_totals(self.db,'Home')
        self.assertGreater(boosted['attack'],before['attack'])
        self.assertGreater(boosted['defense'],before['defense'])
        self.turn(7)
        self.assertEqual(garrison_totals(self.db,'Home'),earned)

    def test_training_adds_new_duration_to_remaining_days_exactly_once(self):
        eid=begin_hunt(self.db,6,'Север');resolve_hunt(self.db,eid);finish_hunt(self.db,eid)
        self.turn(6)
        self.assertEqual(progress(self.db,'Север')['veteran_until']-6,9)
        eid=begin_hunt(self.db,7,'Север');result=resolve_hunt(self.db,eid)
        self.assertEqual(progress(self.db,'Север')['veteran_until']-6,25)
        self.assertEqual(resolve_hunt(self.db,eid),result)
        self.assertEqual(progress(self.db,'Север')['veteran_until']-6,25)
        self.assertEqual(self.db.execute('SELECT DISTINCT until_turn FROM monster_training_ranks').fetchall(),[(31,)])
        finish_hunt(self.db,eid)
        self.turn(40)
        eid=begin_hunt(self.db,1,'Север');resolve_hunt(self.db,eid)
        self.assertEqual(progress(self.db,'Север')['veteran_until'],47)

    def test_faction_cooldown_applies_across_all_lairs_exactly_five_turns(self):
        eid=begin_hunt(self.db,1,'Север');resolve_hunt(self.db,eid);finish_hunt(self.db,eid)
        for turn in (0,1,4):
            self.turn(turn)
            self.assertEqual(cooldown_left(self.db,'Север'),5-turn)
            with self.assertRaises(ValueError):begin_hunt(self.db,2,'Север')
        self.turn(5)
        self.assertTrue(begin_hunt(self.db,1,'Север'))

    def test_no_hero_no_foreign_city_no_repeat_during_active_march(self):
        with self.assertRaises(ValueError):begin_hunt(self.db,1,'Эльфы')
        self.db.execute("DELETE FROM garrisons WHERE unit_name='hero'")
        with self.assertRaises(ValueError):begin_hunt(self.db,1,'Север')

    def test_failure_retreats_without_reward_but_consumes_cooldown(self):
        self.db.execute("UPDATE units SET attack=1 WHERE unit_name='troop'")
        eid=begin_hunt(self.db,7,'Север')
        self.assertFalse(resolve_hunt(self.db,eid)['won'])
        finish_hunt(self.db,eid)
        self.assertEqual(progress(self.db,'Север')['veteran_until'],0)
        self.assertEqual(progress(self.db,'Север')['relic_earned'],0)
        self.assertEqual(cooldown_left(self.db,'Север'),5)

    def test_reload_recovery_is_idempotent_and_never_gives_troops_to_new_city_owner(self):
        eid=begin_hunt(self.db,7,'Север')
        self.db.execute("UPDATE cities SET faction='Эльфы' WHERE name='Home'")
        recover_hunts(self.db)
        self.assertIsNotNone(self.db.execute("SELECT 1 FROM garrisons WHERE city_name LIKE '@monster:%'").fetchone())
        self.assertIsNone(self.db.execute("SELECT 1 FROM garrisons WHERE city_name='Home'").fetchone())
        self.db.execute("UPDATE cities SET faction='Север' WHERE name='Away'")
        recover_hunts(self.db);recover_hunts(self.db)
        self.assertEqual(self.db.execute("SELECT unit_count FROM garrisons WHERE city_name='Away' AND unit_name='troop'").fetchone()[0],250)
        self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE resource_type='Кроны'").fetchone()[0],850100)

    def test_legendary_perk_once_per_faction_and_clones_only_owned_item(self):
        eid=begin_hunt(self.db,7,'Север')
        self.assertTrue(resolve_hunt(self.db,eid)['new_relic']);finish_hunt(self.db,eid)
        self.assertEqual(progress(self.db,'Север')['veteran_until'],16)
        data=upgrade_artifact(self.db,'Север','artifacts',1,'attack','hero','0')
        self.assertEqual(data['attack'],670)
        self.assertEqual(data['defense'],25)
        self.assertEqual(self.db.execute('SELECT attack FROM artifacts WHERE id=1').fetchone()[0],120)
        self.assertFalse(artifact_visible(self.db,'Эльфы',data['id']))
        self.assertEqual(self.db.execute("SELECT artifact_id FROM hero_equipment WHERE faction_name='Эльфы'").fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM artifact_effects_log WHERE hero_name='other'").fetchone()[0],1)
        with self.assertRaises(ValueError):upgrade_artifact(self.db,'Север','artifacts',data['id'],'defense','hero','0')
        self.turn(5)
        eid=begin_hunt(self.db,7,'Север')
        self.assertFalse(resolve_hunt(self.db,eid)['new_relic'])

    def test_relic_waits_for_existing_owned_artifact_and_invalid_choice_does_not_spend_it(self):
        eid=begin_hunt(self.db,7,'Север');resolve_hunt(self.db,eid);finish_hunt(self.db,eid)
        self.db.execute("DELETE FROM hero_equipment WHERE faction_name='Север'")
        with self.assertRaises(ValueError):upgrade_artifact(self.db,'Север','artifacts',1,'attack','hero','0')
        self.assertEqual(progress(self.db,'Север')['relic_used'],0)

    def test_ai_chooses_strongest_beatable_lair_and_cannot_repeat_same_turn(self):
        from monster_ai import try_hunt
        self.assertTrue(try_hunt(self.db,'Север'))
        self.assertEqual(progress(self.db,'Север')['veteran_until'],16)
        self.assertEqual(progress(self.db,'Север')['relic_used'],1)
        self.assertFalse(try_hunt(self.db,'Север'))

    def test_respawn_gives_only_training_and_natural_xp_even_for_another_faction(self):
        eid=begin_hunt(self.db,7,'Север');resolve_hunt(self.db,eid);finish_hunt(self.db,eid)
        original=list(self.db.execute('SELECT * FROM resources ORDER BY faction,resource_type'))
        self.turn(5)
        self.db.execute("UPDATE cities SET faction='Эльфы' WHERE name='Home'")
        eid=begin_hunt(self.db,7,'Эльфы')
        result=resolve_hunt(self.db,eid)
        self.assertTrue(result['won'])
        self.assertEqual(result['resources'],0)
        self.assertFalse(result['new_relic'])
        self.assertFalse(result['legendary'])
        self.assertEqual(progress(self.db,'Эльфы')['relic_earned'],0)
        self.assertEqual(progress(self.db,'Эльфы')['veteran_until'],21)
        self.assertEqual(list(self.db.execute('SELECT * FROM resources ORDER BY faction,resource_type')),original)
        resolve_hunt(self.db,eid);finish_hunt(self.db,eid)
        self.assertEqual(self.db.execute("SELECT experience FROM garrisons WHERE unit_name='troop'").fetchone()[0],2)
        self.assertEqual(sites(self.db)[-1]['defeats'],2)

    def test_warrior_veteran_elite_thresholds_use_earned_victories_without_training_other_stacks(self):
        for initial,expected in ((0,1),(2,3),(6,7)):
            self.turn(initial*5)
            self.db.execute("UPDATE garrisons SET experience=? WHERE city_name='Home' AND unit_name='troop'",(initial,))
            self.db.execute("INSERT OR REPLACE INTO garrisons VALUES('Away','troop',100,'',0)")
            eid=begin_hunt(self.db,1,'Север');result=resolve_hunt(self.db,eid);finish_hunt(self.db,eid)
            self.assertEqual(result['experience'],1)
            self.assertEqual(self.db.execute("SELECT experience FROM garrisons WHERE city_name='Home' AND unit_name='troop'").fetchone()[0],expected)
            self.assertEqual(self.db.execute("SELECT experience FROM garrisons WHERE city_name='Home' AND unit_name='hero'").fetchone()[0],0)
            self.assertEqual(self.db.execute("SELECT experience FROM garrisons WHERE city_name='Away'").fetchone()[0],0)

    def test_legacy_defeated_lair_keeps_its_empty_loot_after_schema_migration_and_reload(self):
        self.db.execute('ALTER TABLE monster_sites DROP COLUMN defeats')
        self.db.execute('UPDATE monster_sites SET ready_turn=5 WHERE id=7')
        ensure_schema(self.db)
        ensure_schema(self.db)
        self.assertEqual(sites(self.db)[-1]['defeats'],1)
        self.turn(5)
        eid=begin_hunt(self.db,7,'Север');result=resolve_hunt(self.db,eid);finish_hunt(self.db,eid)
        self.assertEqual(result['resources'],0)
        self.assertEqual(progress(self.db,'Север')['relic_earned'],0)

    def test_training_uses_rank_before_victory_and_elite_gets_an_extra_fifteen_percent(self):
        from monster_sites import experience_multiplier
        for xp,target,mult in ((0,3,1.15),(1,7,1.25),(3,7,1.25),(7,8,1.25*1.15)):
            with self.subTest(experience=xp):
                db=fixture()
                try:
                    db.execute("UPDATE garrisons SET experience=? WHERE unit_name='troop'",(xp,))
                    eid=begin_hunt(db,1,'Север');resolve_hunt(db,eid);finish_hunt(db,eid)
                    natural=db.execute("SELECT experience FROM garrisons WHERE unit_name='troop'").fetchone()[0]
                    self.assertEqual(natural,xp+1)
                    self.assertEqual(effective_experience(db,'Север',natural,'Home','troop'),target)
                    self.assertAlmostEqual(experience_multiplier(db,'Север',natural,'Home','troop'),mult)
                    db.execute('UPDATE turn SET turn_count=7')
                    expected=1.25 if natural>=7 else 1.15 if natural>=3 else 1.05
                    self.assertAlmostEqual(experience_multiplier(db,'Север',natural,'Home','troop'),expected)
                finally:db.close()

    def test_training_rank_survives_terrain_credit_and_does_not_stack_elite_bonus(self):
        from monster_sites import experience_multiplier
        from terrain_journeys import _credit
        self.db.execute("UPDATE garrisons SET experience=7 WHERE unit_name='troop'")
        eid=begin_hunt(self.db,1,'Север');resolve_hunt(self.db,eid);finish_hunt(self.db,eid)
        _credit(self.db,'@terrain:test','troop',10,'',8,training_source='Home')
        self.assertAlmostEqual(experience_multiplier(self.db,'Север',8,'@terrain:test','troop'),1.25*1.15)
        self.turn(5)
        eid=begin_hunt(self.db,1,'Север');resolve_hunt(self.db,eid);finish_hunt(self.db,eid)
        self.assertAlmostEqual(experience_multiplier(self.db,'Север',9,'Home','troop'),1.25*1.15)


if __name__=='__main__':unittest.main()
