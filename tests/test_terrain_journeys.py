import ast
import contextlib
import io
import math
import os
from pathlib import Path
import random
import sqlite3
import unittest

from terrain_journeys import (ensure_schema,start_journey,advance_journeys,waiting_armies,
                              generate_features,available_attack_units,route_stops)
from map_terrain import load_terrain, WATER, VOID
from utils.garrison_stats import garrison_totals


class JourneyTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.addCleanup(self.db.close)
        self.db.executescript('''
            CREATE TABLE cities(id,name,faction,coordinates);
            INSERT INTO cities VALUES(1,'A','Север','[100,300]'),(2,'B','Север','[300,300]'),(3,'C','Север','[500,300]');
            CREATE TABLE roads(city1,city2); INSERT INTO roads VALUES(1,2),(2,3);
            CREATE TABLE turn(turn_count); INSERT INTO turn VALUES(0);
            CREATE TABLE season(season_index); INSERT INTO season VALUES(1);
            CREATE TABLE buildings(city_name,faction,building_type,count);
            CREATE TABLE diplomacies(faction1,faction2,relationship);
            CREATE TABLE units(unit_name,faction,unit_class,attack,defense,durability,consumption,image_path);
            INSERT INTO units VALUES('soldier','Север','1',10,5,10,2,'');
            CREATE TABLE garrisons(city_name,unit_name,unit_count,unit_image,experience,UNIQUE(city_name,unit_name));
            INSERT INTO garrisons VALUES('A','soldier',100,'',3);
        ''')
        ensure_schema(self.db)
        self.db.executescript('''INSERT INTO map_features VALUES(1,'forest',1,2,.5,238,330,2,1);
            INSERT INTO map_features VALUES(2,'swamp',2,3,.5,438,330,3,1);''')
        self.db.commit()

    def send(self, target='C', count=50):
        return start_journey(self.db,'Север','A',target,[dict(unit_name='soldier',unit_count=count)])

    def advance(self, turn):
        self.db.execute('UPDATE turn SET turn_count=?',(turn,))
        advance_journeys(self.db,turn)

    def count(self, city):
        return self.db.execute('SELECT COALESCE(SUM(unit_count),0) FROM garrisons WHERE city_name=?',(city,)).fetchone()[0]

    def test_two_then_three_turns_wait_independently_without_duplication(self):
        self.send()
        self.assertEqual(self.count('A'),50)
        self.assertEqual(self.count('C'),0)
        self.assertEqual(waiting_armies(self.db)[0]['remaining'],2)
        self.advance(1)
        self.assertEqual(waiting_armies(self.db)[0]['remaining'],1)
        self.advance(2)
        self.assertEqual(waiting_armies(self.db)[0]['feature']['kind'],'swamp')
        self.assertEqual(waiting_armies(self.db)[0]['remaining'],3)
        self.advance(2)
        self.assertEqual(waiting_armies(self.db)[0]['remaining'],3)
        self.advance(4)
        self.assertEqual(self.count('C'),0)
        self.advance(5)
        self.assertEqual((self.count('A'),self.count('C')),(50,50))
        self.assertEqual(waiting_armies(self.db),[])
        self.assertEqual(self.db.execute("SELECT experience FROM garrisons WHERE city_name='C'").fetchone()[0],3)
        self.advance(5)
        self.assertEqual(self.count('C'),50)

    def test_waiting_units_pay_upkeep_and_cannot_be_selected_at_staging_city(self):
        self.send()
        consumption = self.db.execute('SELECT SUM(g.unit_count*u.consumption) FROM garrisons g JOIN units u USING(unit_name)').fetchone()[0]
        self.assertEqual(consumption,200)
        self.assertEqual(available_attack_units(self.db,'A',[dict(unit_name='soldier',unit_count=100)])[0]['unit_count'],50)
        with self.assertRaises(ValueError):
            self.send(count=60)
        self.assertEqual(self.db.execute('SELECT SUM(unit_count) FROM garrisons').fetchone()[0],100)

    def test_database_reload_keeps_camp_and_release_turn(self):
        self.send()
        loaded = sqlite3.connect(':memory:')
        self.addCleanup(loaded.close)
        self.db.backup(loaded)
        self.assertEqual(waiting_armies(loaded),waiting_armies(self.db))
        loaded.execute('UPDATE turn SET turn_count=2')
        advance_journeys(loaded,2)
        self.assertEqual(waiting_armies(loaded)[0]['feature']['kind'],'swamp')

    def test_enemy_city_is_captured_only_after_wait_and_exactly_once(self):
        self.db.execute("UPDATE cities SET faction='Вампиры' WHERE name='B'")
        self.db.execute("INSERT INTO diplomacies VALUES('Север','Вампиры','война')")
        self.send('B')
        self.advance(1)
        self.assertEqual(self.db.execute("SELECT faction FROM cities WHERE name='B'").fetchone()[0],'Вампиры')
        self.advance(2)
        self.assertEqual(self.db.execute("SELECT faction FROM cities WHERE name='B'").fetchone()[0],'Север')
        self.assertEqual(self.count('B'),50)
        self.advance(3)
        self.assertEqual(self.db.execute("SELECT revision FROM city_war_state WHERE city_name='B'").fetchone()[0],1)

    def test_peace_during_wait_returns_troops_instead_of_attacking(self):
        self.db.execute("UPDATE cities SET faction='Вампиры' WHERE name='B'")
        self.db.execute("INSERT INTO diplomacies VALUES('Север','Вампиры','война')")
        self.send('B')
        self.db.execute("UPDATE diplomacies SET relationship='мир'")
        self.advance(2)
        self.assertEqual(self.count('A'),100)
        self.assertEqual(self.count('B'),0)

    def test_ordinary_road_still_moves_without_creating_a_journey(self):
        self.db.execute('DELETE FROM map_features')
        self.assertIsNone(self.send())
        self.assertEqual(self.count('A'),100)

    def test_reverse_route_visits_swamp_before_forest(self):
        stops = route_stops(self.db,[3,2,1])
        self.assertEqual([s['kind'] for s in stops],['swamp','forest'])

    def test_garrison_totals_exclude_departed_units_and_include_hero_buffs(self):
        self.db.execute("INSERT INTO units VALUES('hero','Север','2',190,95,0,1,'')")
        self.db.execute("INSERT INTO garrisons VALUES('A','hero',1,'',0)")
        before = garrison_totals(self.db,'A')
        self.assertEqual(before['count'],101)
        self.assertEqual(before['attack'],41590)  # (10+190)*1.8*1.15*100 + hero.
        self.send()
        after = garrison_totals(self.db,'A')
        self.assertLess(after['attack'],before['attack'])
        self.assertEqual(after['count'],51)

    def test_mountain_total_includes_entire_garrison_without_boosting_attack(self):
        from utils.city_terrain import ensure_schema as relief_schema
        before=garrison_totals(self.db,'A')
        relief_schema(self.db)
        self.db.execute("INSERT INTO city_terrain VALUES('A','highland',2,0,NULL)")
        after=garrison_totals(self.db,'A')
        self.assertEqual(after['attack'],before['attack'])
        self.assertEqual(after['defense'],int(before['defense']*1.3))

    def test_lowland_reduces_total_defense_including_hero_without_reducing_attack(self):
        from utils.city_terrain import ensure_schema as relief_schema
        self.db.execute("INSERT INTO units VALUES('hero','Север','2',190,95,0,1,'')")
        self.db.execute("INSERT INTO garrisons VALUES('A','hero',1,'',0)")
        before=garrison_totals(self.db,'A')
        relief_schema(self.db)
        self.db.execute("INSERT INTO city_terrain VALUES('A','lowland',0,0,NULL)")
        after=garrison_totals(self.db,'A')
        self.assertEqual(after['attack'],before['attack'])
        self.assertEqual(after['defense'],int(before['defense']*.8))


class TerrainGenerationTests(unittest.TestCase):
    def test_legacy_icons_migrate_to_unique_persistent_variants(self):
        from terrain_journeys import features
        db=sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript('''CREATE TABLE map_features(id,kind,city1,city2,fraction,x,y,delay);
            INSERT INTO map_features VALUES(1,'forest',1,2,.5,100,200,2),
            (2,'forest',2,3,.5,200,300,2),(3,'swamp',3,4,.5,300,400,3);''')
        ensure_schema(db)
        before=features(db)
        self.assertEqual(len({r['icon_variant'] for r in before if r['kind']=='forest'}),2)
        ensure_schema(db)
        self.assertEqual(features(db),before)

    def test_generation_counts_land_sites_and_city_clearance_on_new_maps(self):
        tree = ast.parse(Path('generate_map.py').read_text(encoding='utf-8'))
        nodes = [n for n in tree.body if isinstance(n,(ast.Assign,ast.FunctionDef))]
        for number in range(1,11):
            with self.subTest(map=number), contextlib.redirect_stdout(io.StringIO()):
                terrain = load_terrain(f'files/map/generate/map_{number}.png')
                self.assertIsNotNone(terrain)
                ns = dict(os=os,math=math,random=random.Random(number),sqlite3=sqlite3,MANHATTAN_MOVE_LIMIT=280)
                exec(compile(ast.Module(body=nodes,type_ignores=[]),'generate_map.py','exec'),ns)
                conn = sqlite3.connect(':memory:')
                try:
                    conn.executescript('CREATE TABLE cities(id,name,coordinates,faction,icon_coordinates,label_coordinates,color_faction,is_undead,kf_crystal);'
                                       'CREATE TABLE roads(id,city1,city2);'
                                       'CREATE TABLE garrisons(city_name,unit_name,unit_count,unit_image);')
                    ns['generate_map_and_cities'](conn,terrain)
                    from monster_sites import sites as monster_sites,reward
                    lairs=monster_sites(conn)
                    self.assertIn(len(lairs),(6,7))
                    self.assertIn(7,{s['tier'] for s in lairs})
                    self.assertEqual(len(lairs),len({s['tier'] for s in lairs}))
                    self.assertTrue(all(1<=s['variant']<=5 for s in lairs))
                    roads_before=list(conn.execute('SELECT city1,city2 FROM roads'))
                    from map_terrain import TerrainView
                    view=TerrainView(terrain)
                    import json
                    for lair in lairs:
                        self.assertTrue(view.path_clear(json.loads(lair['road']),'land'))
                        self.assertEqual(reward(lair['tier'])['duration'],lair['tier']+2)
                    self.assertEqual(list(conn.execute('SELECT city1,city2 FROM roads')),roads_before)
                    self.assertEqual(conn.execute('SELECT COUNT(*) FROM cities').fetchone()[0],26)
                    from utils.city_terrain import read_all
                    geography=read_all(conn)
                    self.assertEqual(len(geography),26)
                    self.assertEqual(read_all(conn),geography)
                    from terrain_journeys import features
                    sites = features(conn)
                    self.assertIn(sum(s['kind']=='forest' for s in sites),(3,4,5))
                    self.assertIn(sum(s['kind']=='swamp' for s in sites),(1,2))
                    for kind in ('forest','swamp'):
                        variants=[s['icon_variant'] for s in sites if s['kind']==kind]
                        self.assertEqual(len(variants),len(set(variants)))
                    self.assertEqual(len(sites),len({(s['city1'],s['city2']) for s in sites}))
                    for s in sites:
                        self.assertEqual(s['fraction'],.5)
                        self.assertNotIn(terrain.kind_at(s['x'],s['y']),(WATER,VOID))
                finally:
                    conn.close()


if __name__ == '__main__':
    unittest.main()
