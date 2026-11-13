"""Run real AI economics/recruitment in disposable SQLite snapshots, without UI.

No battles or territorial expansion: identical three-city starts test development.
The live campaign is opened read-only and is never changed.
"""
import ast
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import random
import sqlite3

from ai_strategy import apply_ai_improvements
from ai_economy import secure_supply
from utils.helpers import format_number

ROOT=Path(__file__).resolve().parents[1]


def extracted(filename,name,source=None):
    source=source if source is not None else (ROOT/filename).read_text(encoding='utf-8-sig')
    node=next(n for n in ast.parse(source).body
              if isinstance(n,ast.ClassDef) and n.name==name)
    ns=dict(sqlite3=sqlite3,random=random,format_number=format_number)
    exec(compile(ast.Module(body=[node],type_ignores=[]),filename,'exec'),ns)
    return ns[name]


def snapshot():
    db=sqlite3.connect(':memory:')
    with sqlite3.connect('file:'+str(ROOT/'game_data.db')+'?mode=ro',uri=True) as source:source.backup(db)
    return db


def army_summary(db,faction):
    rows=list(db.execute('''SELECT u.unit_name,u.unit_class,SUM(g.unit_count),u.attack,u.defense,u.durability
        FROM garrisons g JOIN cities c ON c.name=g.city_name JOIN units u ON u.unit_name=g.unit_name
        WHERE c.faction=? GROUP BY u.unit_name''',(faction,)))
    heroes=[r for r in rows if str(r[1]) in ('2','3','4') and r[2]>0]
    attack=sum(r[3]*r[2] for r in heroes if str(r[1]) in ('2','3'))
    defense=sum((r[4]+r[5]/2)*r[2] for r in heroes if str(r[1]) in ('2','3'))
    soldiers=[r for r in rows if str(r[1])=='1']
    # Same rating function as the main-map army table, extracted without UI.
    source=(ROOT/'politic.py').read_text(encoding='utf-8-sig')
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='calculate_total_faction_power')
    from utils.faction_bonuses import combat_multiplier
    ns=dict(combat_multiplier=combat_multiplier)
    exec(compile(ast.Module(body=[node],type_ignores=[]),'politic.py','exec'),ns)
    return dict(power=ns[node.name](db,faction),soldiers=sum(r[2] for r in soldiers),heroes=[r[0] for r in heroes],
        attack=sum((r[3]+attack)*r[2] for r in soldiers),
        defense=sum((r[4]+r[5]/2+defense)*r[2] for r in soldiers),
        artifacts=db.execute('SELECT COUNT(*) FROM ai_hero_equipment WHERE faction_name=? AND artifact_id IS NOT NULL',(faction,)).fetchone()[0])


def simulate(faction,system='Смирение',turns=15,existing=False):
    db=snapshot()
    try:
        if system=='campaign':
            row=db.execute('SELECT system FROM political_systems WHERE faction=?',(faction,)).fetchone()
            system=row[0] if row else 'Смирение'
        if not existing:
            db.execute('DELETE FROM buildings');db.execute('DELETE FROM garrisons')
            db.execute('DELETE FROM ai_hero_equipment');db.execute('DELETE FROM artifacts_ai')
            db.execute('DELETE FROM artifact_effects_log')
            db.execute('DELETE FROM units');db.execute('INSERT INTO units SELECT * FROM units_default')
            db.execute('DELETE FROM cities WHERE rowid NOT IN (SELECT rowid FROM cities LIMIT 3)')
            db.execute('UPDATE cities SET faction=?,kf_crystal=0',(faction,))
            names=[r[0] for r in db.execute('SELECT name FROM cities')]
            ids=[r[0] for r in db.execute('SELECT id FROM cities')]
            db.execute('DELETE FROM roads')
            db.executemany('INSERT INTO roads(city1,city2) VALUES(?,?)',list(zip(ids,ids[1:])))
            db.execute('DELETE FROM resources WHERE faction=?',(faction,))
            db.executemany('INSERT INTO resources(faction,resource_type,amount) VALUES(?,?,?)',
                [(faction,k,v) for k,v in {'Кроны':2500,'Кристаллы':1000,'Население':200,'Рабочие':200}.items()])
            db.execute('UPDATE political_systems SET system=? WHERE faction=?',(system,faction))
        ai_type=extracted('ii.py','AIController');apply_ai_improvements(ai_type)
        season=extracted('seasons.py','SeasonManager')()
        ai=ai_type(faction,db,season_manager=season)
        ai.turn=13 if existing else 0
        for name in ('update_trade_resources_from_db','process_trade_agreements','_apply_supply_line_losses'):
            setattr(ai,name,lambda:None)
        ai.get_factions_at_war=lambda:[]
        before=army_summary(db,faction)
        history=[]
        for step in range(turns):
            db.execute('UPDATE season SET season_index=?',((step//3)%4,))
            season.last_idx=(step//3)%4
            season.apply_artifact_bonuses(db)
            ai.cities=ai.load_cities();ai.garrison=ai.load_garrison()
            ai.army=ai.load_army();ai.army_limit=ai.calculate_army_limit()
            ai.calculate_current_consumption();ai.update_resources();ai.raw_material_price=110
            ai.apply_political_system_bonus()
            ai.manage_buildings();ai.emergency_sell_crystals();ai.sell_resources()
            ai.manage_buildings()
            if ai.turn>0:ai.hire_army()
            secure_supply(ai);ai.save_resources_to_db()
            season.apply_artifact_bonuses(db)
            ai.turn+=1
            row=army_summary(db,faction);row.update(turn=ai.turn,crowns=ai.resources['Кроны'],population=ai.resources['Население'])
            history.append(row)
        return dict(faction=faction,system=system,before=before,history=history)
    finally:db.close()


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--output',default='.release/ai-army-audit.json')
    p.add_argument('--existing',action='store_true');p.add_argument('--turns',type=int,default=15)
    p.add_argument('--baseline',action='store_true')
    p.add_argument('--system',default='campaign',choices=('campaign','Смирение','Борьба'))
    args=p.parse_args();random.seed(23)
    if args.baseline:
        import subprocess
        import ai_economy
        old_source=subprocess.check_output(['git','show','edc1190:ai_economy.py'],cwd=ROOT).decode('utf-8-sig')
        old={'__name__':'ai_economy_baseline'}
        exec(compile(old_source,'ai_economy.py','exec'),old)
        for key,value in old.items():
            if callable(value) and getattr(value,'__module__',None)=='ai_economy_baseline':setattr(ai_economy,key,value)
        old_ii=subprocess.check_output(['git','show','edc1190:ii.py'],cwd=ROOT).decode('utf-8-sig')
        original=extracted
        def extracted(filename,name):
            return original(filename,name,source=old_ii if filename=='ii.py' else None)
    log=io.StringIO()
    with redirect_stdout(log):
        result=[simulate(f,system=args.system,turns=args.turns,existing=args.existing) for f in ('Север','Эльфы','Вампиры','Адепты','Элины')]
    Path(args.output).parent.mkdir(parents=True,exist_ok=True)
    Path(args.output).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    Path(args.output).with_suffix('.log').write_text(log.getvalue(),encoding='utf-8')
    for row in result:print(row['faction'],row['history'][-1])
