"""Real SQLite transactions: travelling armies, foreign ownership and markets."""
import random
import ast
from pathlib import Path
import sqlite3
import tempfile
import unittest

import otherworlds as w


def fixture():
    db=sqlite3.connect(':memory:')
    db.executescript('''
        CREATE TABLE cities(id INTEGER,name TEXT,faction TEXT,coordinates TEXT);
        INSERT INTO cities VALUES(1,'Home','Север','[100,100]'),(2,'Safe','Север','[300,300]');
        CREATE TABLE units(id INTEGER PRIMARY KEY,faction TEXT,unit_name TEXT UNIQUE,
            cost_money INTEGER,cost_time INTEGER,image_path TEXT,attack INTEGER,defense INTEGER,
            durability INTEGER,unit_class TEXT,consumption REAL);
        CREATE TABLE garrisons(city_name TEXT,unit_name TEXT,unit_count INTEGER,unit_image TEXT,
            experience INTEGER DEFAULT 0,UNIQUE(city_name,unit_name));
        CREATE TABLE resources(faction TEXT,resource_type TEXT,amount INTEGER);
        INSERT INTO resources VALUES('Север','Кроны',1000000),('Север','Кристаллы',100000);
        CREATE TABLE buildings(city_name,faction,building_type,count);
        CREATE TABLE turn(turn_count); INSERT INTO turn VALUES(0);
        CREATE TABLE turn_check_move(faction,moves_left); INSERT INTO turn_check_move VALUES('Север',20);
        CREATE TABLE artifacts(id INTEGER PRIMARY KEY,attack,defense,season_name,image_url,name,cost,artifact_type,is_created);
        INSERT INTO artifacts VALUES(1,50,20,'','files/pict/hire/sword.png','Blade',10000,0,0);
        CREATE TABLE hero_equipment(faction_name,hero_name,slot_type,artifact_id,image_url,
            PRIMARY KEY(faction_name,hero_name,slot_type));
    ''')
    for i,faction in enumerate(['Север','Эльфы','Адепты','Вампиры','Элины'],1):
        db.execute('INSERT INTO units VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                   (i,faction,'troop'+str(i),40+i,1,'files/status/army.png',500+i,100,10,'1',1))
    db.execute("INSERT INTO units VALUES(6,'Север','Hero',100,1,'files/status/army.png',100,300,10,'3',10)")
    db.execute("INSERT INTO garrisons VALUES('Home','troop1',1000,'files/status/army.png',3)")
    db.execute("INSERT INTO garrisons VALUES('Home','Hero',1,'files/status/army.png',0)")
    db.execute("ALTER TABLE units ADD COLUMN unit_type TEXT DEFAULT 'infantry'")
    w.create_world(db,random.Random(2))
    db.commit()
    return db


class PortalTests(unittest.TestCase):
    def setUp(self):
        self.db=fixture();self.addCleanup(self.db.close)

    def enter(self):
        return w.enter(self.db,'Север','Home')

    def test_world_is_persistent_connected_and_has_no_capturable_cities(self):
        before=w.cities(self.db)
        self.assertEqual(w.create_world(self.db,random.Random(9))['id'],1)
        self.assertEqual(before,w.cities(self.db))
        reached={1}
        for _ in range(7):
            for a,b in self.db.execute('SELECT * FROM portal_roads'):
                if a in reached or b in reached: reached.update((a,b))
        self.assertEqual(reached,set(range(1,8)))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM cities').fetchone()[0],2)

    def test_existing_world_restyled_without_losing_expedition_or_progress(self):
        self.enter()
        self.db.execute('DELETE FROM portal_presentation')
        self.db.execute("UPDATE portal_worlds SET background='files/map/generate/map_1.png'")
        self.db.execute('UPDATE portal_cities SET x=100,y=100')
        self.db.execute("INSERT INTO portal_battles VALUES(1,'Север',5)")
        self.db.commit()
        before=w.party(self.db,'Север')
        w.upgrade_world(self.db)
        from otherworld_content import BACKGROUND,CITY_POSITIONS
        self.assertEqual(w.world(self.db)['background'],BACKGROUND)
        self.assertEqual([(c['x'],c['y']) for c in w.cities(self.db)],list(CITY_POSITIONS))
        self.assertEqual(w.party(self.db,'Север'),before)
        self.assertEqual(w.battle_ready(self.db,'Север'),5)
        self.assertEqual(self.db.execute('SELECT SUM(unit_count) FROM garrisons').fetchone()[0],1001)

    def test_local_catalogs_are_independent_and_units_keep_their_own_type(self):
        before=list(self.db.execute('SELECT * FROM units'))
        units=w.unit_offers(self.db);artifacts=w.artifact_offers(self.db)
        self.assertEqual(len(units),5);self.assertEqual(len(artifacts),5)
        self.assertEqual(len({u['image_path'] for u in units}),5)
        self.assertTrue(all(u['image_path'].startswith('files/otherworld/') for u in units))
        self.assertTrue(all(a['image_url'].startswith('files/otherworld/') for a in artifacts))
        self.assertEqual(list(self.db.execute('SELECT * FROM units')),before)
        p=self.enter();w.recruit(self.db,'Север',4)
        self.assertEqual(self.db.execute("SELECT unit_type FROM units WHERE unit_name LIKE 'Странник:%'").fetchone()[0],'mage')
        from test_battle_ui import combat_namespace
        battle=w.fight_guards(self.db,'Север',combat_namespace()['battle_chain'])
        mage=next(u for u in battle['army'] if u['unit_name'].startswith('Странник:'))
        self.assertEqual(mage['units_stats']['Тип'],'mage')
        # The ordinary recruitment UI must not offer imported portal troops.
        node=next(n for n in ast.parse(Path('army.py').read_text(encoding='utf-8')).body
                  if isinstance(n,ast.FunctionDef) and n.name=='load_unit_data')
        namespace={}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'army.py','exec'),namespace)
        roster=namespace['load_unit_data']('Север',self.db)
        self.assertIn('troop1',roster)
        self.assertFalse(any(name.startswith('Странник:') for name in roster))

    def test_real_army_leaves_and_returns_with_experience_and_purchases(self):
        p=self.enter()
        self.assertFalse(self.db.execute("SELECT 1 FROM garrisons WHERE city_name='Home'").fetchone())
        w.recruit(self.db,'Север',2)
        home=w.return_home(self.db,'Север')
        self.assertEqual(home,'Home')
        self.assertIsNone(w.party(self.db,'Север'))
        self.assertEqual(self.db.execute("SELECT unit_count,experience FROM garrisons WHERE city_name='Home' AND unit_name='troop1'").fetchone(),(1000,3))
        merc=self.db.execute("SELECT g.unit_count,u.faction,u.consumption FROM garrisons g JOIN units u USING(unit_name) WHERE g.unit_name LIKE 'Странник:%'").fetchone()
        self.assertEqual(merc,(100,'Север',1.61))
        self.assertFalse(self.db.execute('SELECT 1 FROM garrisons WHERE city_name=?',(p['camp'],)).fetchone())

    def test_hero_and_actions_required_atomic_enter(self):
        self.db.execute("DELETE FROM garrisons WHERE unit_name='Hero'");self.db.commit()
        with self.assertRaises(ValueError): self.enter()
        self.assertIsNone(w.party(self.db,'Север'))
        self.assertEqual(self.db.execute('SELECT moves_left FROM turn_check_move').fetchone()[0],20)
        self.assertEqual(self.db.execute('SELECT SUM(unit_count) FROM garrisons').fetchone()[0],1000)

    def test_expedition_and_stock_survive_database_reopen(self):
        self.enter();w.recruit(self.db,'Север',2)
        with tempfile.TemporaryDirectory(dir='.release') as folder:
            path=folder+'/portal-save.db'
            disk=sqlite3.connect(path);self.db.backup(disk);disk.close()
            saved=sqlite3.connect(path)
            try:
                self.assertEqual(w.party(saved,'Север'),w.party(self.db,'Север'))
                self.assertEqual(w.cities(saved),w.cities(self.db))
                self.assertEqual(saved.execute('SELECT stock FROM portal_market').fetchone()[0],900)
                self.assertEqual(w.return_home(saved,'Север'),'Home')
            finally:
                saved.close()

    def test_no_actions_cannot_move_or_lose_expedition(self):
        self.enter();self.db.execute('UPDATE turn_check_move SET moves_left=0');self.db.commit()
        before=list(self.db.execute('SELECT * FROM garrisons'))
        with self.assertRaises(ValueError): w.return_home(self.db,'Север')
        self.assertIsNotNone(w.party(self.db,'Север'))
        self.assertEqual(list(self.db.execute('SELECT * FROM garrisons')),before)

    def test_reenter_does_not_duplicate_army(self):
        p=self.enter()
        with self.assertRaises(ValueError): self.enter()
        self.assertEqual(self.db.execute('SELECT SUM(unit_count) FROM garrisons WHERE city_name=?',(p['camp'],)).fetchone()[0],1001)

    def test_temporary_training_returns_home_without_stale_camp_ranks(self):
        from monster_sites import ensure_schema
        ensure_schema(self.db)
        self.db.execute("INSERT INTO monster_training_ranks VALUES('Север','Home','troop1',7,1,5)")
        self.db.commit()
        p=self.enter()
        self.assertEqual(self.db.execute('SELECT rank,elite_extra,until_turn FROM monster_training_ranks WHERE city_name=?',(p['camp'],)).fetchone(),(7,1,5))
        w.return_home(self.db,'Север')
        self.assertFalse(self.db.execute('SELECT 1 FROM monster_training_ranks WHERE city_name=?',(p['camp'],)).fetchone())
        self.assertEqual(self.db.execute("SELECT rank,elite_extra,until_turn FROM monster_training_ranks WHERE city_name='Home'").fetchone(),(7,1,5))

    def test_travel_checks_road_and_does_not_capture(self):
        self.enter()
        neighbor=self.db.execute('SELECT CASE WHEN city1=1 THEN city2 ELSE city1 END FROM portal_roads WHERE city1=1 OR city2=1 LIMIT 1').fetchone()[0]
        before=list(self.db.execute('SELECT * FROM cities'))
        w.travel(self.db,'Север',neighbor)
        self.assertEqual(w.party(self.db,'Север')['city_id'],neighbor)
        with self.assertRaises(ValueError): w.return_home(self.db,'Север')
        w.travel(self.db,'Север',1)
        self.assertEqual(list(self.db.execute('SELECT * FROM cities')),before)

    def test_home_fallback_if_departure_city_lost(self):
        self.enter();self.db.execute("UPDATE cities SET faction='Эльфы' WHERE name='Home'");self.db.commit()
        self.assertEqual(w.return_home(self.db,'Север'),'Safe')

    def test_markets_have_five_unit_types_and_atomic_finite_stock(self):
        self.enter();self.assertEqual(len(w.unit_offers(self.db)),5)
        w.recruit(self.db,'Север',1,1000)
        money=self.money()
        with self.assertRaises(ValueError): w.recruit(self.db,'Север',1)
        self.assertEqual(self.money(),money)
        self.db.execute('UPDATE turn SET turn_count=1');self.db.commit()
        w.recruit(self.db,'Север',1)

    def money(self):
        return self.db.execute("SELECT amount FROM resources WHERE resource_type='Кроны'").fetchone()[0]

    def test_failed_payment_rolls_back_stock_and_units(self):
        self.enter();self.db.execute('UPDATE resources SET amount=0');self.db.commit()
        before=list(self.db.execute('SELECT * FROM garrisons'))
        with self.assertRaises(ValueError): w.recruit(self.db,'Север',1)
        self.assertEqual(list(self.db.execute('SELECT * FROM garrisons')),before)
        self.assertFalse(self.db.execute('SELECT 1 FROM portal_market').fetchone())

    def test_resources_use_local_prices_and_spread(self):
        self.enter();money=self.money()
        paid=w.trade_crystals(self.db,'Север')
        got=w.trade_crystals(self.db,'Север',False)
        self.assertGreater(paid,got)
        self.assertEqual(self.money(),money-paid+got)
        self.assertEqual(self.db.execute("SELECT amount FROM resources WHERE resource_type='Кристаллы'").fetchone()[0],100000)

    def test_artifact_purchase_equips_normal_slot_once(self):
        self.enter();w.buy_artifact(self.db,'Север',1)
        self.assertEqual(self.db.execute('SELECT faction_name,hero_name,slot_type,artifact_id FROM hero_equipment').fetchone(),('Север','Hero','0',2))
        self.assertEqual(self.db.execute('SELECT name FROM artifacts WHERE id=2').fetchone()[0],w.artifact_offers(self.db,'Север')[0]['name'])
        self.assertEqual(self.db.execute('SELECT name FROM artifacts WHERE id=1').fetchone()[0],'Blade')
        money=self.money()
        with self.assertRaises(ValueError): w.buy_artifact(self.db,'Север',1)
        self.assertEqual(self.money(),money)

    def test_portal_artifacts_have_personal_ids_and_are_not_resold_at_home(self):
        from monster_sites import artifact_visible,owned_artifacts
        self.enter();w.buy_artifact(self.db,'Север',1)
        self.db.execute("UPDATE cities SET faction='Эльфы' WHERE name='Safe'")
        self.db.execute("INSERT INTO units VALUES(7,'Эльфы','ElfHero',100,1,'files/status/army.png',100,300,10,'3',10,'infantry')")
        self.db.execute("INSERT INTO garrisons VALUES('Safe','troop2',100,'',0)")
        self.db.execute("INSERT INTO garrisons VALUES('Safe','ElfHero',1,'',0)")
        self.db.execute("INSERT INTO resources VALUES('Эльфы','Кроны',1000000)")
        self.db.execute("INSERT INTO turn_check_move VALUES('Эльфы',20)")
        self.db.commit()
        w.enter(self.db,'Эльфы','Safe')
        # The other faction visits its own themed world and has its own stock.
        w.buy_artifact(self.db,'Эльфы',1)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM portal_market WHERE kind='artifact'").fetchone()[0],2)
        north=owned_artifacts(self.db,'Север')[0]
        elf=owned_artifacts(self.db,'Эльфы')[0]
        self.assertNotEqual(north['id'],elf['id'])
        self.assertTrue(artifact_visible(self.db,'Север',north['id']))
        self.assertFalse(artifact_visible(self.db,'Эльфы',north['id']))
        self.assertEqual(self.db.execute('SELECT name FROM artifacts WHERE id=1').fetchone()[0],'Blade')
        # Equipment and its details must still find the owned illustration.
        from types import SimpleNamespace
        node=next(n for n in ast.parse(Path('heroes.py').read_text(encoding='utf-8')).body
                  if isinstance(n,ast.FunctionDef) and n.name=='load_artifacts_from_db')
        namespace={'sqlite3':sqlite3}
        exec(compile(ast.Module(body=[node],type_ignores=[]),'heroes.py','exec'),namespace)
        gear=namespace['load_artifacts_from_db'](SimpleNamespace(conn=self.db,faction='Север'))
        self.assertIn(north['id'],[item['id'] for item in gear])
        self.assertNotIn(elf['id'],[item['id'] for item in gear])

    def test_battle_real_losses_rewards_and_no_capture(self):
        from test_battle_ui import combat_namespace
        self.enter();before=list(self.db.execute('SELECT * FROM cities'));money=self.money()
        result=w.fight_guards(self.db,'Север',combat_namespace()['battle_chain'])
        self.assertTrue(result['won'])
        self.assertGreater(result['coins'],0)
        self.assertEqual(self.money(),money+result['coins'])
        self.assertEqual(list(self.db.execute('SELECT * FROM cities')),before)
        self.assertEqual(self.db.execute("SELECT experience FROM garrisons WHERE unit_name='troop1'").fetchone()[0],4)
        self.assertEqual(w.battle_ready(self.db,'Север'),5)
        with self.assertRaises(ValueError): w.fight_guards(self.db,'Север',combat_namespace()['battle_chain'])

    def test_defeat_removes_losses_and_keeps_hero_for_retreat(self):
        p=self.enter()
        def lose(unit,guard,*args,**kwargs): unit['unit_count']=0
        result=w.fight_guards(self.db,'Север',lose)
        self.assertFalse(result['won']);self.assertEqual(result['coins'],0)
        self.assertEqual(self.db.execute('SELECT unit_name FROM garrisons WHERE city_name=?',(p['camp'],)).fetchall(),[('Hero',)])
        self.assertEqual(w.return_home(self.db,'Север'),'Home')


if __name__=='__main__':
    unittest.main()
