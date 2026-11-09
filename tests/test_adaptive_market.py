"""Current policy, supply, and real player/AI production before upkeep."""
import ast
import contextlib
import io
from pathlib import Path
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from city_construction import building_description,FACTORY_YIELD,AI_FACTORY_YIELD
from utils.market_income import market_profile,market_policy,additional_income


def production(filename,faction,policy,markets=1,population=100,consumption=50,season=-1,full=False):
    db=sqlite3.connect(':memory:')
    db.executescript('''CREATE TABLE cities(id,name,faction,kf_crystal);
        CREATE TABLE buildings(city_name,faction,building_type,count);
        CREATE TABLE roads(city1,city2); CREATE TABLE season(season_index);
        CREATE TABLE political_systems(faction,system);''')
    db.execute('INSERT INTO cities VALUES(1,?,?,0)',('Home',faction))
    db.execute('INSERT INTO political_systems VALUES(?,?)',(faction,policy))
    db.execute('INSERT INTO season VALUES(?)',(season,))
    for i in range(markets):
        if i:
            db.execute('INSERT INTO cities VALUES(?,?,?,0)',(i+1,'Town'+str(i),faction))
            db.execute('INSERT INTO roads VALUES(1,?)',(i+1,))
        db.execute('INSERT INTO buildings VALUES(?,?,?,1)',('Home' if not i else 'Town'+str(i),faction,'Рынок'))
    host=SimpleNamespace(conn=db,db_connection=db,cursor=db.cursor(),faction=faction,turn=0,
        money=0,raw_material=0,free_peoples=0,population=population,hospitals=0,factories=1,markets=markets,
        current_consumption=consumption,tax_effects=0,city_count=max(1,markets))
    for name in ('load_buildings','auto_build','load_resources_from_db','generate_raw_material_price',
                 'update_trade_resources_from_db','process_trade_agreements','update_buildings_from_db'):
        setattr(host,name,lambda:None)
    host.calculate_tax_income=lambda:1000;host._get_supplied_cities=lambda:{'Home'}
    tree=ast.parse(Path(filename).read_text(encoding='utf-8'))
    method=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='update_resources')
    body=method.body if filename=='economic.py' else next(n for n in method.body if isinstance(n,ast.Try)).body
    if full:
        host.resources={};host.current_tax_rate='0%';host.tax_effect=lambda _:0;host.max_army_limit=10000
        host.update_average_net_profit=lambda *args:None
        host._apply_supply_line_losses=lambda:None;host._sync_resources=lambda:None;host.save_resources_to_db=lambda:None
        host.bills=0
        def bill():
            host.bills+=1;host.raw_material-=consumption
        host.calculate_and_deduct_consumption=bill
    stop=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and any(
        isinstance(t,ast.Attribute) and t.attr=='food_peoples' for t in n.targets))
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            if full:
                namespace={'sqlite3':sqlite3}
                exec(compile(ast.Module(body=[method],type_ignores=[]),filename,'exec'),namespace)
                limits={'Кроны':10000000,'Кристаллы':10000000,'Рабочие':500000,'Население':100000000}
                with patch('utils.resource_caps.caps',return_value=limits):namespace['update_resources'](host)
            else:
                exec(compile(ast.Module(body=body[:stop+1],type_ignores=[]),filename,'exec'),{'self':host,'sqlite3':sqlite3})
        if full:return host.raw_material,host.bills
        return host.money_up,host.food_info,host.raw_material
    finally:db.close()


class AdaptiveMarketTests(unittest.TestCase):
    def test_real_player_and_ai_get_only_the_income_selected_by_policy(self):
        for source,yield_ in (('economic.py',FACTORY_YIELD),('ii.py',AI_FACTORY_YIELD)):
            for faction in ('Север','Адепты','Вампиры','Эльфы','Элины'):
                for policy in ('Смирение','Борьба'):
                    with self.subTest(source=source,faction=faction,policy=policy):
                        base=production(source,faction,policy,markets=0)
                        actual=production(source,faction,policy)
                        expected=int(yield_*(5 if faction=='Элины' else 65)/100) if policy=='Борьба' else 0
                        self.assertEqual(actual[0]-base[0],100 if policy=='Смирение' else 0)
                        self.assertEqual(actual[1]-base[1],expected)
                        self.assertEqual(actual[2]-base[2],expected)

    def test_crystal_bonus_uses_seasonal_production_and_not_upkeep(self):
        no_market=production('economic.py','Север','Борьба',markets=0,season=2)
        actual=production('economic.py','Север','Борьба',season=2)
        self.assertEqual(actual[2]-no_market[2],int(FACTORY_YIELD*1.25*.65))
        empty=production('economic.py','Север','Борьба',population=0,consumption=0)
        expensive=production('economic.py','Север','Борьба',population=100,consumption=500)
        self.assertEqual(empty[2]-expensive[2],30)
        two=production('economic.py','Север','Борьба',markets=2)
        one=production('economic.py','Север','Борьба')
        self.assertEqual(two[2]-one[2],int(FACTORY_YIELD*2*.65)-int(FACTORY_YIELD*.65))

    def test_full_player_turn_charges_upkeep_once(self):
        without,bills=production('economic.py','Север','Борьба',consumption=0,full=True)
        charged,charged_bills=production('economic.py','Север','Борьба',consumption=50,full=True)
        self.assertEqual((bills,charged_bills),(1,1))
        self.assertEqual(without-charged,50)

    def test_policy_switch_descriptions_supply_and_duplicate_legacy_rows(self):
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.executescript('''CREATE TABLE cities(id,name,faction);
            CREATE TABLE roads(city1,city2); CREATE TABLE buildings(city_name,faction,building_type,count);
            CREATE TABLE political_systems(faction,system);
            INSERT INTO cities VALUES(1,'Capital','Север'),(2,'Port','Север'),(3,'Island','Север'),(4,'Foreign','Эльфы');
            INSERT INTO roads VALUES(1,2);
            INSERT INTO buildings VALUES('Capital','Север','Рынок',1),('Capital','Север','Рынок',5),
                ('Island','Север','Рынок',1),('Foreign','Север','Рынок',1);
            INSERT INTO political_systems VALUES('Север','Смирение');''')
        self.assertEqual(market_profile(db,'Север'),(1,10,0))
        self.assertIn('+10%',building_description(db,'Север','Рынок'))
        db.execute("UPDATE political_systems SET system='Борьба'")
        self.assertEqual(market_profile(db,'Север'),(1,0,65))
        self.assertIn('+65%',building_description(db,'Север','Рынок'))
        self.assertIn('кристаллов',building_description(db,'Север','Рынок'))
        db.execute("INSERT INTO political_systems VALUES('Элины','Борьба')")
        self.assertEqual(market_policy(db,'Элины'),('Кристаллы',5))
        db.execute("DELETE FROM buildings WHERE city_name='Capital'")
        self.assertEqual(market_profile(db,'Север'),(0,0,65))

    def test_bonus_does_not_multiply_losses_and_rounds_to_whole_resources(self):
        self.assertEqual(additional_income(-100,3,65),0)
        self.assertEqual(additional_income(819,1,5),40)
        self.assertEqual(additional_income(819,0,65),0)


if __name__=='__main__':unittest.main()
