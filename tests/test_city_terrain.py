"""Geography affects the owning city, actual casualties and supplied production."""
import ast
import contextlib
import io
import random
import sqlite3
import unittest
from pathlib import Path
from types import SimpleNamespace

from map_terrain import TerrainMap, LAND, WATER, MOUNTAIN, SNOW, VOID
from utils.city_terrain import classify_city, ensure_schema, economic_bonuses, defense_multiplier


def terrain(fill=LAND, water=False):
    grid=[[fill]*120 for _ in range(80)]
    if water:
        for row in grid:
            row[:12]=[WATER]*12
    return TerrainMap(dict(version=1,row_origin='top-left',grid_size=[120,80],
        world_size=[1200,800],rows=[[[v,1] for v in row] for row in grid]))


class ReliefTests(unittest.TestCase):
    def test_footprint_mountains_have_defense_but_snow_plains_do_not(self):
        high=classify_city(terrain(MOUNTAIN),'peak',200,300)
        self.assertEqual((high.landform,high.elevation,high.defense_multiplier),('highland',2,1.3))
        self.assertEqual(classify_city(terrain(SNOW),'snow plain',200,300).defense_multiplier,1)

    def test_real_water_gives_coast_and_lowland_frame_does_not(self):
        coast=classify_city(terrain(water=True),'port',140,300)
        self.assertTrue(coast.waterside)
        self.assertEqual(coast.landform,'lowland')
        self.assertEqual(coast.defense_multiplier,.8)
        self.assertIn('−20%',coast.description)
        self.assertIn('−20%', ' '.join(coast.badges))
        inland=classify_city(terrain(water=True),'inland',500,300)
        self.assertFalse(inland.waterside)
        self.assertEqual(inland.landform,'plains')
        frame=classify_city(terrain(VOID),'frame',140,300)
        self.assertFalse(frame.waterside)
        self.assertEqual(frame.landform,'plains')

    def test_economy_is_local_supplied_and_changes_owner_without_changing_geography(self):
        db=sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        db.executescript('''CREATE TABLE cities(id,name,faction);
            INSERT INTO cities VALUES(1,'A','one'),(2,'B','one'),(3,'C','one');
            CREATE TABLE roads(city1,city2); INSERT INTO roads VALUES(1,2);
            CREATE TABLE buildings(city_name,faction,building_type,count);
            INSERT INTO buildings VALUES('A','one','Фабрика',2),('C','one','Фабрика',10);''')
        ensure_schema(db)
        db.executemany('INSERT INTO city_terrain VALUES(?,?,?,?,?)',
                       [('A','lowland',0,1,30),('B','highland',2,0,300),('C','lowland',0,1,20)])
        # One of three towns contributes its equal share. Disconnected C adds nothing.
        self.assertEqual(economic_bonuses(db,'one',3000,105),
                         dict(crowns=150,crystals=42,lowlands=1,waterside=1))
        self.assertEqual(economic_bonuses(db,'one',-3000,105)['crowns'],0)
        self.assertEqual(defense_multiplier(db,'B'),1.3)
        db.execute("UPDATE cities SET faction='two' WHERE name='A'")
        db.execute("UPDATE buildings SET faction='two' WHERE city_name='A'")
        self.assertEqual(economic_bonuses(db,'two',1000,105)['crystals'],42)
        self.assertEqual(economic_bonuses(db,'two',1000,105)['crowns'],150)
        self.assertEqual(defense_multiplier(db,'B'),1.3)

    def test_legacy_save_is_neutral(self):
        db=sqlite3.connect(':memory:')
        self.addCleanup(db.close)
        self.assertEqual(defense_multiplier(db,'old'),1)
        self.assertEqual(economic_bonuses(db,'one',1000,105)['crystals'],0)


class ReliefCombatTests(unittest.TestCase):
    def test_real_skirmish_losses_and_initiative_reversal(self):
        tree=ast.parse(Path('fight.py').read_text(encoding='utf-8'))
        chain=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='battle_chain')
        rng=random.Random(1)
        namespace=dict(calculate_unit_power=lambda u,is_attacking:100 if is_attacking else 100,
            get_unit_class=lambda u:1,get_unit_type=lambda u:'same',get_crit_chance=lambda u:0,
            NORTH_MULTIPLIER=1.8,ADEPT_MULTIPLIER=1.55,TYPE_MOD={},COUNTER_ATTACK_RATIO=1,
            RANDOM_MIN=1,RANDOM_MAX=1,CRIT_MULTIPLIER=2,BASE_LETHALITY=10,random=rng,
            damage_to_infrastructure=lambda *args:None)
        exec(compile(ast.Module(body=[chain],type_ignores=[]),'fight.py','exec'),namespace)
        battle=namespace['battle_chain']
        def run(reverse=False,bonus=1):
            away=dict(unit_name='away',unit_count=1000)
            home=dict(unit_name='home',unit_count=1000,_terrain_defense_multiplier=bonus)
            first,second=(home,away) if reverse else (away,home)
            battle(first,second,'peak','one',None)
            return away['unit_count'],home['unit_count']
        self.assertEqual(run(),(900,900))
        self.assertEqual(run(bonus=1.3),(900,924))
        self.assertEqual(run(reverse=True,bonus=1.3),(900,924))
        self.assertEqual(run(bonus=.8),(900,875))
        self.assertEqual(run(reverse=True,bonus=.8),(900,875))


class ReliefResourceIntegrationTests(unittest.TestCase):
    def test_player_and_ai_income_apply_local_perks_once_before_upkeep(self):
        # Execute each real resource method through its income calculation,
        # before UI, diplomacy and persistence side effects later in the turn.
        for filename,expected_raw in (('economic.py',1830),('ii.py',1400)):
            with self.subTest(controller=filename):
                db=sqlite3.connect(':memory:')
                self.addCleanup(db.close)
                db.executescript('''CREATE TABLE cities(id,name,faction,kf_crystal);
                    INSERT INTO cities VALUES(1,'port','Север',0);
                    CREATE TABLE buildings(city_name,faction,building_type,count);
                    INSERT INTO buildings VALUES('port','Север','Фабрика',1);
                    CREATE TABLE roads(city1,city2);
                    CREATE TABLE season(season_index); INSERT INTO season VALUES(2);''')
                ensure_schema(db)
                db.execute("INSERT INTO city_terrain VALUES('port','lowland',0,1,30)")
                host=SimpleNamespace(conn=db,db_connection=db,cursor=db.cursor(),faction='Север',
                    turn=0,money=0,raw_material=0,free_peoples=0,population=100,
                    hospitals=0,factories=1,markets=0,current_consumption=30,tax_effects=0,city_count=1)
                for name in ('load_buildings','auto_build','load_resources_from_db',
                             'generate_raw_material_price','update_trade_resources_from_db',
                             'process_trade_agreements','update_buildings_from_db'):
                    setattr(host,name,lambda:None)
                host.calculate_tax_income=lambda:1000
                host._get_supplied_cities=lambda:{'port'}
                tree=ast.parse(Path(filename).read_text(encoding='utf-8'))
                method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='update_resources')
                body=method.body
                if filename=='ii.py':
                    body=next(n for n in body if isinstance(n,ast.Try)).body
                stop=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and any(
                    isinstance(t,ast.Attribute) and t.attr=='food_peoples' for t in n.targets))
                with contextlib.redirect_stdout(io.StringIO()):
                    exec(compile(ast.Module(body=body[:stop+1],type_ignores=[]),filename,'exec'),
                         dict(self=host,sqlite3=sqlite3))
                self.assertEqual(host.money,1150)
                self.assertEqual(host.money_up,1150)
                self.assertEqual(host.raw_material,expected_raw)


if __name__=='__main__':
    unittest.main()
