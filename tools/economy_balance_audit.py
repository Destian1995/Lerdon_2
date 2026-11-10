"""Reproducible faction comparison using real Faction methods, isolated SQLite.

No import of economic.py or main.py: their application bootstrap writes saves.
Wars, events, advisors, resource trading and recruitment are disabled equally.
"""
import ast
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import sys
from types import MethodType,SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from city_construction import CATALOG
from utils.market_income import market_policy
from utils.crystal_trade import crystal_quotes,affordable_lots

FACTIONS=('Север','Эльфы','Вампиры','Адепты','Элины')
TREE=ast.parse((ROOT/'economic.py').read_text(encoding='utf-8'))
CLASS=next(n for n in TREE.body if isinstance(n,ast.ClassDef) and n.name=='Faction')
NAMES={'update_resources','apply_player_bonuses','get_base_tax_rate','set_taxes',
       'calculate_tax_income','tax_effect','_sync_resources','load_resources_from_db',
       'save_resources_to_db','_get_trade_bonus','trade_raw_material'}
METHODS=[n for n in CLASS.body if isinstance(n,ast.FunctionDef) and n.name in NAMES]
NS={'sqlite3':sqlite3}
exec(compile(ast.Module(body=METHODS,type_ignores=[]),'economic.py','exec'),NS)
PARAMS=next(ast.literal_eval(n.value) for n in ast.walk(CLASS) if isinstance(n,ast.Assign)
            and any(isinstance(t,ast.Attribute) and t.attr=='economic_params' for t in n.targets))


def make_player(faction,policy='Смирение',upkeep=0,developed=False):
    db=sqlite3.connect(':memory:')
    db.executescript('''CREATE TABLE cities(id,name,faction,kf_crystal);
        CREATE TABLE roads(city1,city2); CREATE TABLE buildings(city_name,faction,building_type,count);
        CREATE TABLE season(season_index); INSERT INTO season VALUES(0);
        CREATE TABLE political_systems(faction,system); CREATE TABLE resources(faction,resource_type,amount);''')
    db.execute('INSERT INTO cities VALUES(1,?,?,0)',('Город',faction))
    db.execute('INSERT INTO political_systems VALUES(?,?)',(faction,policy))
    p=SimpleNamespace(conn=db,cursor=db.cursor(),faction=faction,turn=0,money=2500,
        raw_material=0,population=10,free_peoples=0,current_consumption=upkeep,
        tax_set=False,custom_tax_rate=0,current_tax_rate='0%',economic_params=PARAMS,
        city_count=1,tax_effects=0,max_army_limit=5000,_on_resources_changed=None,
        resources={},current_raw_material_price=100,market_turn=None,hospitals=0,factories=0,markets=0)
    for method in METHODS:setattr(p,method.name,MethodType(NS[method.name],p))
    for name in ('auto_build','generate_raw_material_price','update_trade_resources_from_db',
                 'update_average_net_profit','_apply_supply_line_losses','_apply_council_relation_bonuses',
                 'update_relations_based_on_political_system'):
        setattr(p,name,lambda *args:None)
    p._get_council_bonuses=lambda:(0,0)
    p.load_political_system=lambda:policy
    p._get_supplied_cities=lambda:{'Город'}
    def buildings():
        counts=dict(db.execute('SELECT building_type,count FROM buildings'))
        p.hospitals=counts.get('Больница',0);p.factories=counts.get('Фабрика',0);p.markets=counts.get('Рынок',0)
    p.load_buildings=buildings
    def bill():p.raw_material-=upkeep
    p.calculate_and_deduct_consumption=bill
    def build(name,free=False):
        if not free:p.money-=CATALOG[name]['cost']
        db.execute('INSERT INTO buildings VALUES(?,?,?,1)',('Город',faction,name))
        buildings()
    p.build=build
    build('Больница');build('Фабрика')
    if developed:build('Рынок',True);p.market_turn=0
    p._sync_resources()
    db.executemany('INSERT INTO resources VALUES(?,?,?)',[(faction,k,v) for k,v in p.resources.items()]);db.commit()
    return p


def simulate(faction,policy,rates,start_season=0,upkeep=0,developed=False):
    p=make_player(faction,policy,upkeep,developed);rows=[]
    try:
        with redirect_stdout(io.StringIO()):
            for i,rate in enumerate(rates,1):
                season=(start_season+(i-1)//4)%4
                p.conn.execute('UPDATE season SET season_index=?',(season,))
                if not p.markets and p.money>=CATALOG['Рынок']['cost']:
                    p.build('Рынок');p.market_turn=i;p._sync_resources();p.save_resources_to_db()
                p.current_tax_rate=str(rate)+'%';p.set_taxes(rate)
                p.update_resources();p.apply_player_bonuses();p.save_resources_to_db()
                rows.append(dict(turn=i,tax=rate,season=season,crowns=round(p.money,2),
                    crystals=round(p.raw_material,2),population=round(p.population,2),workers=round(p.free_peoples,2),markets=p.markets))
        sell=crystal_quotes(p.current_raw_material_price,p._get_trade_bonus())[1]/100
        return dict(faction=faction,policy=policy,start_season=start_season,upkeep=upkeep,
                    developed=developed,market_turn=p.market_turn,final=rows[-1],turns=rows,
                    final_sell_multiplier=sell,wealth_at_crystal_quote_1=round(p.money+p.raw_material*sell,2))
    finally:p.conn.close()


def trade_cycle(faction,summer=False,markets=1):
    p=make_player(faction,developed=bool(markets));p.money=10000;p.raw_material=0
    p.conn.execute('UPDATE season SET season_index=?',(2 if summer else 0,));p._sync_resources()
    try:
        with redirect_stdout(io.StringIO()):
            buy,_=crystal_quotes(p.current_raw_material_price,p._get_trade_bonus())
            p.trade_raw_material('buy',min(100,affordable_lots(p.money,buy)))
            lots=int(p.raw_material//100)
            p.trade_raw_material('sell',lots)
        return dict(faction=faction,summer=summer,markets=p.markets,crowns_before=10000,
                    crowns_after=round(p.money,2),crystals_left=p.raw_material,trade_multiplier=p._get_trade_bonus())
    finally:p.conn.close()


def run(turns=15):
    plans={'tax_24':[24]*turns,'tax_34':[34]*turns,
           'growth_then_tax_100':[0]*(turns-1)+[100],
           'tax_9_then_100':[9]*(turns-1)+[100]}
    results=[]
    for policy in ('Смирение','Борьба'):
        for faction in FACTIONS:
            for season in range(4):
                for upkeep in (0,100):
                    for plan,rates in plans.items():
                        result=simulate(faction,policy,rates,season,upkeep)
                        result['plan']=plan;results.append(result)
    return dict(turns=turns,initial=dict(crowns=2500,population=10,crystals=0,workers=0,
        hospital=1,factory=1,crowns_after_building=0),tax_base=PARAMS,
        results=results,trade_cycles=[trade_cycle(f,summer) for f in FACTIONS for summer in (False,True)],
        limits='Identical isolated city and upkeep. No wars, events, advisors, quests, terrain perks or trading during turn simulation. Tax plans are examples, not an exhaustive optimal-policy proof.')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--turns',type=int,default=15)
    args=parser.parse_args();report=run(args.turns);args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for row in report['results']:
        if row['plan']=='tax_34' and row['start_season']==0 and row['upkeep']==0:
            print(row['policy'],row['faction'],row['final'],'market turn',row['market_turn'])
    print('Trade cycles:',report['trade_cycles'])
