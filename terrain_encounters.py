"""Road encounters use ordinary skirmishes without any city-capture side effects."""
import json
from city_war import current_turn

ARRIVAL_MULTIPLIER=.85


def ensure_schema(conn):
    columns={r[1] for r in conn.execute('PRAGMA table_info(terrain_journeys)')}
    if 'arrival_order' not in columns:
        conn.execute('ALTER TABLE terrain_journeys ADD COLUMN arrival_order INTEGER NOT NULL DEFAULT 0')
    conn.execute('CREATE TABLE IF NOT EXISTS terrain_arrival_clock(id INTEGER PRIMARY KEY,value INTEGER NOT NULL)')
    conn.execute('INSERT OR IGNORE INTO terrain_arrival_clock VALUES(1,0)')
    conn.execute('''CREATE TABLE IF NOT EXISTS terrain_battles(
        id INTEGER PRIMARY KEY,attacker_order INTEGER,defender_order INTEGER,
        attacker TEXT,defender TEXT,result TEXT NOT NULL,seen INTEGER NOT NULL DEFAULT 0,
        UNIQUE(attacker_order,defender_order))''')
    # Old saves have no arrival sequence. Their wait deadlines retain the entry turn.
    pending=[]
    for jid,stops,stage,ready in conn.execute('SELECT id,stops,stage,ready_turn FROM terrain_journeys WHERE arrival_order=0'):
        pending.append((ready-json.loads(stops)[stage]['delay'],jid))
    for _,jid in sorted(pending):mark_arrival(conn,jid)


def mark_arrival(conn,jid):
    conn.execute('UPDATE terrain_arrival_clock SET value=value+1 WHERE id=1')
    conn.execute('UPDATE terrain_journeys SET arrival_order=(SELECT value FROM terrain_arrival_clock WHERE id=1) WHERE id=?',(jid,))


def _journeys(conn):
    names=[r[1] for r in conn.execute('PRAGMA table_info(terrain_journeys)')]
    return [dict(zip(names,r)) for r in conn.execute('SELECT * FROM terrain_journeys ORDER BY arrival_order,id')]


def _stop(row):return json.loads(row['stops'])[row['stage']]


def _hostile(conn,a,b):
    return a!=b and bool(conn.execute('''SELECT 1 FROM diplomacies WHERE relationship='война'
        AND ((faction1=? AND faction2=?) OR (faction1=? AND faction2=?))''',(a,b,b,a)).fetchone())


def _army(conn,row,late):
    from terrain_journeys import _camp_units
    from monster_sites import experience_multiplier
    army=[]
    for name,count,image,exp,attack,defense,hp,cls in _camp_units(conn,row['camp']):
        columns=[c[1] for c in conn.execute('PRAGMA table_info(units)')]
        template=dict(zip(columns,conn.execute('SELECT * FROM units WHERE unit_name=?',(name,)).fetchone()))
        cls=str(cls).split()[0]
        army.append(dict(unit_name=name,unit_count=count,initial_count=count,unit_image=image,
            hero_candidate=int(cls)>=2,experience=exp,
            units_stats={'Урон':attack,'Защита':defense,'Живучесть':hp,'Класс юнита':cls,
                         'Тип':template.get('unit_type') or 'infantry',
                         'Инициатива':template.get('initiative') or 50,'Крит':template.get('crit_chance') or 5},
            _experience_multiplier=experience_multiplier(conn,row['faction'],exp,row['camp'],name) if cls=='1' else 1,
            _encounter_attack_multiplier=ARRIVAL_MULTIPLIER if late else 1,
            _encounter_defense_multiplier=ARRIVAL_MULTIPLIER if late else 1))
    return army


def resolve_battle(conn,newcomer,resident,skirmish=None):
    if skirmish is None:
        from fight import battle_chain
        skirmish=battle_chain
    from terrain_journeys import _start_return,_experience
    attack=_army(conn,newcomer,True);defense=_army(conn,resident,False)
    if not attack or not defense:return None
    armies=(attack,defense);rows=(newcomer,resident)
    totals=[sum(u['unit_count'] for u in army) for army in armies]
    bonuses=[tuple(sum(u['units_stats'][stat] or 0 for u in army
                        if u['units_stats']['Класс юнита'] in ('2','3'))
                   for stat in ('Урон','Защита','Живучесть')) for army in armies]
    frames=[]
    def ready(army):
        ordinary=[u for u in army if u['unit_count']>0 and not u['hero_candidate']]
        return ordinary or [u for u in army if u['unit_count']>0]
    site=_stop(newcomer);place='Лес' if site['kind']=='forest' else 'Болото'
    for number in range(1,201):
        if not all(ready(army) for army in armies):break
        before=tuple(sum(u['unit_count'] for u in army) for army in armies)
        # Initiative can reverse the strike; the arrival penalty stays on its unit.
        turns=sorted(((u['units_stats']['Инициатива'],side,u) for side,army in enumerate(armies)
                      for u in ready(army)),key=lambda x:-x[0])
        for _,side,unit in turns:
            enemies=ready(armies[1-side])
            if unit['unit_count']<=0 or not enemies:continue
            skirmish(unit,enemies[0],place,newcomer['faction'],conn,
                     atk_hero_bonus=bonuses[side],def_hero_bonus=bonuses[1-side],
                     atk_fraction=rows[side]['faction'],def_fraction=rows[1-side]['faction'],
                     damage_infrastructure=False)
        after=tuple(sum(u['unit_count'] for u in army) for army in armies)
        frames.append(dict(round=number,atk_max=totals[0],def_max=totals[1],atk_total=after[0],def_total=after[1]))
        if before==after:break
    winner=0 if not ready(defense) and ready(attack) else 1 if not ready(attack) and ready(defense) else None
    for side,(row,army) in enumerate(zip(rows,armies)):
        for unit in army:
            count=max(0,int(unit['unit_count']))
            unit['unit_count']=count
            conn.execute('UPDATE garrisons SET unit_count=? WHERE city_name=? AND unit_name=?',
                         (count,row['camp'],unit['unit_name']))
            if side==winner and count and unit['units_stats']['Класс юнита']=='1' and _experience(conn):
                conn.execute('UPDATE garrisons SET experience=COALESCE(experience,0)+1 WHERE city_name=? AND unit_name=?',
                             (row['camp'],unit['unit_name']))
        conn.execute('DELETE FROM garrisons WHERE city_name=? AND unit_count<=0',(row['camp'],))
        if not any(u['unit_count']>0 for u in army):
            conn.execute('DELETE FROM terrain_journeys WHERE id=?',(row['id'],))
        elif (side==0 and winner!=0) or (side==1 and winner==0):
            _start_return(conn,row,_stop(row),current_turn(conn))
    result=dict(place=place,feature_id=site['id'],attacker=newcomer['faction'],defender=resident['faction'],
                attacker_source=newcomer['source'],defender_source=resident['source'],
                winner='attacker' if winner==0 else 'defender' if winner==1 else 'draw',
                penalty=15,army=attack,defenders=defense,rounds=frames)
    conn.execute('INSERT INTO terrain_battles(attacker_order,defender_order,attacker,defender,result) VALUES(?,?,?,?,?)',
        (newcomer['arrival_order'],resident['arrival_order'],newcomer['faction'],resident['faction'],json.dumps(result)))
    return result


def resolve_entry(conn,jid,skirmish=None):
    rows=_journeys(conn);new=next((r for r in rows if r['id']==jid),None)
    if new is None:return
    for old in rows:
        # A journey can arrive at a later stop before an older journey gets there.
        if old['arrival_order']>=new['arrival_order'] or _stop(old)['id']!=_stop(new)['id']:continue
        if not _hostile(conn,new['faction'],old['faction']):continue
        if conn.execute('SELECT 1 FROM terrain_battles WHERE attacker_order=? AND defender_order=?',
                        (new['arrival_order'],old['arrival_order'])).fetchone():continue
        result=resolve_battle(conn,new,old,skirmish)
        if result and result['winner']!='attacker':break


def resolve_waiting(conn):
    for row in _journeys(conn):resolve_entry(conn,row['id'])
