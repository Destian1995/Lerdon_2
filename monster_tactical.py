"""Prepare PvE stacks without changing campaign state while the player fights."""
from pathlib import Path
import sqlite3


def armies(conn,row,site):
    from utils.garrison_stats import garrison_profiles
    from monster_sites import encounter_reward,monster_name,art_path
    profiles=garrison_profiles(conn,row['camp'],row['faction'])
    cur=conn.execute('SELECT * FROM units');columns=[c[0] for c in cur.description]
    templates={u['unit_name']:u for u in (dict(zip(columns,r)) for r in cur.fetchall())}
    attackers=[]
    for name,count,image in conn.execute('SELECT unit_name,unit_count,unit_image FROM garrisons WHERE city_name=? AND unit_count>0 ORDER BY unit_name',(row['camp'],)):
        template=templates[name];power=profiles[name]
        stats={'Урон':power['attack'],'Защита':power['defense'],'Живучесть':0,
               'Класс юнита':str(template['unit_class']),'Тип':template.get('unit_type') or 'infantry',
               'Инициатива':template.get('initiative',50),'Мораль':template.get('morale',100),
               'Крит':template.get('crit_chance') or 0}
        attackers.append(dict(unit_name=name,unit_count=count,initial_count=count,
            unit_image=image or template.get('image_path') or '',units_stats=stats,
            consumption=template.get('consumption') or 0,
            _quick_combat_power=(power['attack'],power['defense'])))
    defense=encounter_reward(site)['defense']
    defenders=[dict(unit_name=monster_name(site),unit_count=1,initial_count=1,
        unit_image=str(art_path(site['tier'],site.get('variant',1))),
        units_stats={'Урон':defense,'Защита':defense,'Живучесть':0,
                     'Класс юнита':'1','Тип':'beast','Инициатива':50,'Мораль':100,'Крит':0},
        _battle_morale=100)]
    return attackers,defenders


def context(conn,row,site):
    from tactical_battle_bridge import battle_context
    result=battle_context(conn,row['source'],row['faction'])
    result['seed']+=int(site['id'])
    try:
        saved=conn.execute('SELECT image_path FROM campaign_map_context WHERE id=1').fetchone()
        if saved:
            from map_terrain import load_terrain
            from tactical_geography import local_field
            path=Path(saved[0])
            if not path.is_absolute():path=Path(__file__).resolve().parent/path
            terrain=load_terrain(path)
            if terrain:result['biome'],result['terrain']=local_field(terrain,site['x'],site['y'])
    except (sqlite3.OperationalError,OSError,ValueError,TypeError):pass
    return result


def choose_battle(conn,row,site):
    from tactical_battle_bridge import request_battle
    from monster_sites import monster_name
    attackers,defenders=armies(conn,row,site)
    model=request_battle(attackers,defenders,'attacker',monster_name(site),
                         context(conn,row,site),factions=(row['faction'],''))
    if model is not None:model.apply_to(attackers,defenders)
    return model,attackers
