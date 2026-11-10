"""Active-export comparison: real income/trade, equal territory and starting funds.

Only current net production is sold, at most once per turn. Purchased reserves
are never immediately resold; no buy/sell arbitrage loop is used.
"""
import ast
from contextlib import redirect_stdout
import io
import json
import math
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.economy_balance_audit import make_player,FACTIONS,CLASS
from city_construction import CATALOG,FACTORY_YIELD
from utils.market_income import additional_income,market_policy
from utils.crystal_trade import crystal_quotes,affordable_lots

UPDATE=next(n for n in CLASS.body if isinstance(n,ast.FunctionDef) and n.name=='update_resources')
COEFF=next(ast.literal_eval(n.value) for n in ast.walk(UPDATE) if isinstance(n,ast.Assign)
           and any(isinstance(t,ast.Name) and t.id=='faction_coefficients' for t in n.targets))


def simulate_exports(faction,policy,rates,cities=1,start_season=0,build_order='production',upkeep=100,quote=100):
    p=make_player(faction,policy,upkeep);db=p.conn;history=[]
    towns=['Город']+['Город '+str(i) for i in range(2,cities+1)]
    for i,town in enumerate(towns[1:],2):
        db.execute('INSERT INTO cities VALUES(?,?,?,0)',(i,town,faction));db.execute('INSERT INTO roads VALUES(1,?)',(i,))
    p.city_count=cities;p.current_raw_material_price=quote;p._get_supplied_cities=lambda:set(towns)
    def load_buildings():
        counts=dict(db.execute('SELECT building_type,SUM(count) FROM buildings GROUP BY building_type'))
        p.hospitals=counts.get('Больница',0);p.factories=counts.get('Фабрика',0);p.markets=counts.get('Рынок',0)
    p.load_buildings=load_buildings
    preferred=('Фабрика','Больница','Рынок') if build_order=='production' else ('Рынок','Фабрика','Больница')
    def develop():
        for kind in preferred:
            for town in towns:
                if db.execute('SELECT 1 FROM buildings WHERE city_name=? AND building_type=?',(town,kind)).fetchone():continue
                cost=CATALOG[kind]['cost']
                if p.money<cost:continue
                p.money-=cost;db.execute('INSERT INTO buildings VALUES(?,?,?,1)',(town,faction,kind))
        load_buildings();p._sync_resources();p.save_resources_to_db()
    def net_before_bonus(season):
        gross=p.factories*FACTORY_YIELD*(.85,1.10,1.25,1.20)[season]
        resource,percent=market_policy(db,faction)
        return int(gross-p.population*COEFF[faction]['food_loss'])+additional_income(gross,p.markets,percent if resource=='Кристаллы' else 0)-upkeep
    try:
        with redirect_stdout(io.StringIO()):
            for i,rate in enumerate(rates,1):
                if callable(rate):rate=rate(p,i)
                season=(start_season+(i-1)//4)%4;db.execute('UPDATE season SET season_index=?',(season,))
                develop()
                p.current_tax_rate=str(rate)+'%';p.set_taxes(rate)
                missing=max(0,1-p.raw_material-net_before_bonus(season))
                purchased=0
                if missing:
                    need=math.ceil(missing/100)
                    buy,_=crystal_quotes(quote,p._get_trade_bonus())
                    lots=min(need,affordable_lots(p.money,buy))
                    if lots>0:
                        before=p.raw_material;p.trade_raw_material('buy',lots);purchased=p.raw_material-before
                opening=p.raw_material
                p._sync_resources();p.save_resources_to_db()
                p.update_resources();p.apply_player_bonuses()
                net_produced=max(0,p.raw_material-opening)
                next_season=(start_season+i//4)%4
                reserve=max(0,1-net_before_bonus(next_season))
                lots=int(max(0,min(net_produced,p.raw_material-reserve))//100)
                before=p.money
                if lots>0:p.trade_raw_material('sell',lots)
                p._sync_resources();p.save_resources_to_db()
                history.append(dict(turn=i,tax=rate,season=season,crowns=round(p.money,2),crystals=p.raw_material,
                    population=p.population,markets=p.markets,factories=p.factories,hospitals=p.hospitals,
                    purchased=purchased,net_produced=net_produced,sold=lots*100,sale_income=round(p.money-before,2)))
        end=history[-1];sale=crystal_quotes(quote,p._get_trade_bonus())[1]/100
        return dict(faction=faction,policy=policy,cities=cities,build_order=build_order,start_season=start_season,
                    upkeep=upkeep,quote_per_lot=quote,final=end,
                    wealth=round(p.money+p.raw_material*sale,2),history=history)
    finally:db.close()


def run(turns=14):
    plans={'tax0':[0]*turns,'tax9':[9]*turns,'tax24':[24]*turns,'tax34':[34]*turns,
           'grow_then_tax':[0]*(turns-1)+[100],
           'grow_then_34':[0]*(turns//2)+[34]*(turns-turns//2)}
    results=[]
    for cities in (1,3,6):
        for faction in FACTIONS:
            for policy in ('Смирение','Борьба'):
                for season in range(4):
                    for order in ('production','market'):
                        for plan,rates in plans.items():
                            row=simulate_exports(faction,policy,rates,cities,season,order)
                            row['plan']=plan;results.append(row)
    return dict(turns=turns,initial_crowns=2500,initial_population=10,initial_crystals=0,
        upkeep=100,results=results,limits='Same owned cities; no conquest costs, wars, quests, advisors or terrain bonuses. Fixed common quote 1 crown/crystal. No immediate resale of purchases. Best observed among tested plans, not an exhaustive optimum.')


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=run();args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for cities in (1,3,6):
        print('Cities:',cities,'winter start; best observed plans')
        for faction in FACTIONS:
            best=max((r for r in result['results'] if r['cities']==cities and r['faction']==faction and r['start_season']==0),key=lambda r:r['wealth'])
            print(faction,best['wealth'],best['policy'],best['plan'],best['build_order'],best['final'])
