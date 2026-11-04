"""One unique economic building provides the output of twelve legacy buildings."""
import ast
import contextlib
import io
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest
from city_construction import CATALOG


def income(filename,season):
    db=sqlite3.connect(':memory:')
    db.executescript('''CREATE TABLE cities(id,name,faction,kf_crystal);
        INSERT INTO cities VALUES(1,'Home','Север',0);
        CREATE TABLE buildings(city_name,faction,building_type,count);
        INSERT INTO buildings VALUES('Home','Север','Фабрика',1),('Home','Север','Больница',1);
        CREATE TABLE roads(city1,city2);
        CREATE TABLE season(season_index);''')
    db.execute('INSERT INTO season VALUES(?)',(season,))
    host=SimpleNamespace(conn=db,db_connection=db,cursor=db.cursor(),faction='Север',turn=0,
        money=0,raw_material=0,free_peoples=0,population=0,hospitals=1,factories=1,markets=0,
        current_consumption=0,tax_effects=0,city_count=1)
    for name in ('load_buildings','auto_build','load_resources_from_db','generate_raw_material_price',
                 'update_trade_resources_from_db','process_trade_agreements','update_buildings_from_db'):
        setattr(host,name,lambda:None)
    host.calculate_tax_income=lambda:0;host._get_supplied_cities=lambda:{'Home'}
    tree=ast.parse(Path(filename).read_text(encoding='utf-8'))
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='update_resources')
    body=method.body
    if filename=='ii.py':body=next(n for n in body if isinstance(n,ast.Try)).body
    stop=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and any(
        isinstance(t,ast.Attribute) and t.attr=='food_peoples' for t in n.targets))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            exec(compile(ast.Module(body=body[:stop+1],type_ignores=[]),filename,'exec'),{'self':host,'sqlite3':sqlite3})
        return host.born_peoples,host.raw_material
    finally:db.close()


class ProductionTests(unittest.TestCase):
    def test_player_base_and_all_seasons_match_twelve_old_buildings(self):
        for season,population,crystals in ((-1,600,1260),(0,720,1071),(1,780,1386),(2,660,1575),(3,690,1512)):
            with self.subTest(season=season):self.assertEqual(income('economic.py',season),(population,crystals))

    def test_ai_preserves_its_old_production_coefficients_at_twelve_times_output(self):
        for season in range(4):self.assertEqual(income('ii.py',season),(600,1200))

    def test_construction_cards_describe_actual_base_production(self):
        self.assertIn('600',CATALOG['Больница']['desc'])
        self.assertIn('1260',CATALOG['Фабрика']['desc'])
