"""Persistent PvE hunts, faction training and a single legendary relic reward."""
import json
import math
import sqlite3
from pathlib import Path

from city_war import current_turn

NAMES=('Каменный тролль','Паучья королева','Болотная гидра','Мёртвый страж',
       'Обсидиановый голем','Ледяной змей','Владыка бездны')
VARIANT_NAMES=(
    ('Каменный тролль','Лесной огр','Песчаный тролль','Пещерный тролль','Снежный огр'),
    ('Паучья королева','Костяная паучиха','Багровая вдова','Кристальная паучиха','Скорпион пустошей'),
    ('Болотная гидра','Ядовитая гидра','Глубинный левиафан','Болотный василиск','Костяная гидра'),
    ('Мёртвый страж','Король призраков','Палач склепа','Мёртвый минотавр','Костяной колосс'),
    ('Обсидиановый голем','Огненный циклоп','Железный исполин','Обсидиановый скорпион','Пламенный бык'),
    ('Ледяной змей','Ледяная виверна','Волк вечной зимы','Снежная химера','Грозовая птица'),
    ('Владыка бездны','Дракон бездны','Жнец душ','Титан пустоты','Падший серафим'))
COOLDOWN=5


def reward(tier):
    if not isinstance(tier,int) or not 1<=tier<=7:
        raise ValueError('Неизвестный уровень монстра.')
    return dict(defense=90_000_000+(tier-1)*25_000_000,
                duration=tier+2,resources=250_000+(tier-1)*100_000,
                legendary=tier==7)


def art_path(tier,variant=1):
    if not 1<=tier<=7 or not 1<=variant<=5:
        raise ValueError('Неизвестная внешность монстра.')
    suffix=f'_{variant}' if variant!=1 else ''
    return Path(__file__).resolve().parent/'files/map/monsters'/f'monster_{tier}{suffix}.png'


def monster_name(site):
    return VARIANT_NAMES[site['tier']-1][site.get('variant',1)-1]


def encounter_reward(site):
    prize=reward(site['tier'])
    if site.get('defeats',int(site.get('ready_turn',0)>0))>0:
        prize.update(resources=0,legendary=False)
    return prize


def ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS monster_sites(
        id INTEGER PRIMARY KEY,parent_city INTEGER NOT NULL,tier INTEGER NOT NULL,
        x REAL NOT NULL,y REAL NOT NULL,road TEXT NOT NULL,ready_turn INTEGER NOT NULL DEFAULT 0)''')
    if 'defeats' not in {r[1] for r in conn.execute('PRAGMA table_info(monster_sites)')}:
        conn.execute('ALTER TABLE monster_sites ADD COLUMN defeats INTEGER NOT NULL DEFAULT 0')
        conn.execute('UPDATE monster_sites SET defeats=1 WHERE ready_turn>0')
    if 'variant' not in {r[1] for r in conn.execute('PRAGMA table_info(monster_sites)')}:
        conn.execute('ALTER TABLE monster_sites ADD COLUMN variant INTEGER NOT NULL DEFAULT 1')
    conn.execute('''CREATE TABLE IF NOT EXISTS monster_progress(
        faction TEXT PRIMARY KEY,last_hunt INTEGER NOT NULL DEFAULT -100,
        veteran_until INTEGER NOT NULL DEFAULT 0,relic_earned INTEGER NOT NULL DEFAULT 0,
        relic_used INTEGER NOT NULL DEFAULT 0)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS monster_expeditions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,site_id INTEGER NOT NULL UNIQUE,
        faction TEXT NOT NULL,source TEXT NOT NULL,camp TEXT NOT NULL,
        attack REAL NOT NULL,stage TEXT NOT NULL DEFAULT 'outbound',result TEXT)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS monster_artifact_upgrades(
        faction TEXT PRIMARY KEY,artifact_table TEXT NOT NULL,artifact_id INTEGER NOT NULL,
        stat TEXT NOT NULL,created_turn INTEGER NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS monster_training_ranks(
        faction TEXT NOT NULL,city_name TEXT NOT NULL,unit_name TEXT NOT NULL,
        rank INTEGER NOT NULL,elite_extra INTEGER NOT NULL,until_turn INTEGER NOT NULL,
        PRIMARY KEY(faction,city_name,unit_name))''')


def sites(conn):
    try:
        columns={r[1] for r in conn.execute('PRAGMA table_info(monster_sites)')}
        defeats='defeats' if 'defeats' in columns else 'CASE WHEN ready_turn>0 THEN 1 ELSE 0 END'
        variant='variant' if 'variant' in columns else '1'
        return [dict(zip(('id','parent_city','tier','x','y','road','ready_turn','defeats','variant'),r))
                for r in conn.execute('SELECT id,parent_city,tier,x,y,road,ready_turn,'+defeats+','+variant+' FROM monster_sites ORDER BY id')]
    except sqlite3.OperationalError:
        return []


def progress(conn,faction):
    try:
        row=conn.execute('SELECT last_hunt,veteran_until,relic_earned,relic_used FROM monster_progress WHERE faction=?',
                         (faction,)).fetchone()
    except sqlite3.OperationalError:
        row=None
    return dict(zip(('last_hunt','veteran_until','relic_earned','relic_used'),row or (-100,0,0,0)))


def _training_rank(conn,faction,experience,city=None,name=None):
    experience=experience or 0
    if progress(conn,faction)['veteran_until']<=current_turn(conn):
        return experience,False
    if city and name:
        try:
            row=conn.execute('''SELECT rank,elite_extra FROM monster_training_ranks
                WHERE faction=? AND city_name=? AND unit_name=? AND until_turn>?''',
                (faction,city,name,current_turn(conn))).fetchone()
            if row:
                return max(experience,row[0]),bool(row[1])
        except sqlite3.OperationalError:
            pass
    return max(experience,3 if experience<1 else 7),experience>=7


def effective_experience(conn,faction,experience,city=None,name=None):
    return _training_rank(conn,faction,experience,city,name)[0]


def experience_multiplier(conn,faction,experience,city=None,name=None):
    rank,extra=_training_rank(conn,faction,experience,city,name)
    base=1.25 if rank>=7 else 1.15 if rank>=3 else 1.05 if rank>=1 else 1
    return base*(1.15 if extra else 1)


def copy_training(conn,source,target,name):
    try:
        conn.execute('''INSERT INTO monster_training_ranks(faction,city_name,unit_name,rank,elite_extra,until_turn)
            SELECT faction,?,unit_name,rank,elite_extra,until_turn FROM monster_training_ranks
            WHERE city_name=? AND unit_name=? AND until_turn>?
            ON CONFLICT(faction,city_name,unit_name) DO UPDATE SET
            rank=MAX(rank,excluded.rank),elite_extra=MAX(elite_extra,excluded.elite_extra),
            until_turn=MAX(until_turn,excluded.until_turn)''',(target,source,name,current_turn(conn)))
    except sqlite3.OperationalError:
        pass


def _snapshot_training(conn,faction,camp,until):
    owners=dict(conn.execute('SELECT name,faction FROM cities'))
    owners[camp]=faction
    for table in ('terrain_journeys','monster_expeditions'):
        if conn.execute('SELECT 1 FROM sqlite_master WHERE name=?',(table,)).fetchone():
            owners.update(conn.execute(f'SELECT camp,faction FROM {table}'))
    conn.execute('DELETE FROM monster_training_ranks WHERE faction=?',(faction,))
    for city,name,exp in conn.execute('''SELECT g.city_name,g.unit_name,COALESCE(g.experience,0)
        FROM garrisons g JOIN units u ON u.unit_name=g.unit_name
        WHERE g.unit_count>0 AND CAST(u.unit_class AS INTEGER)=1''').fetchall():
        if owners.get(city)==faction:
            conn.execute('INSERT INTO monster_training_ranks VALUES(?,?,?,?,?,?)',
                         (faction,city,name,3 if exp<1 else 7,int(exp>=7),until))


def cooldown_left(conn,faction):
    return max(0,progress(conn,faction)['last_hunt']+COOLDOWN-current_turn(conn))


def expedition(conn,expedition_id):
    names=('id','site_id','faction','source','camp','attack','stage','result')
    row=conn.execute('SELECT '+','.join(names)+' FROM monster_expeditions WHERE id=?',(expedition_id,)).fetchone()
    return dict(zip(names,row)) if row else None


def hunt_status(conn,site,faction):
    ensure_schema(conn)
    city=conn.execute('SELECT name,faction FROM cities WHERE id=?',(site['parent_city'],)).fetchone()
    if not city or city[1]!=faction:
        return False,'Для похода нужно владеть городом у начала дороги.'
    if cooldown_left(conn,faction):
        return False,f'Следующий поход через {cooldown_left(conn,faction)} х.'
    if site['ready_turn']>current_turn(conn):
        return False,f'Логово восстановится через {site["ready_turn"]-current_turn(conn)} х.'
    if conn.execute('SELECT 1 FROM monster_expeditions WHERE site_id=? OR faction=?',(site['id'],faction)).fetchone():
        return False,'Поход ещё не завершён.'
    rows=conn.execute('''SELECT u.unit_class,g.unit_count FROM garrisons g JOIN units u ON u.unit_name=g.unit_name
                         WHERE g.city_name=? AND g.unit_count>0''',(city[0],)).fetchall()
    if not any(str(c).split()[0] in ('2','3','4') and n>0 for c,n in rows):
        return False,'В гарнизоне у входа в логово нужен герой.'
    if not any(str(c).split()[0]=='1' and n>0 for c,n in rows):
        return False,'Герою нужны обычные войска сопровождения.'
    move=conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='turn_check_move'").fetchone()
    if move:
        cols={r[1] for r in conn.execute('PRAGMA table_info(turn_check_move)')}
        if 'moves_left' in cols:
            row=conn.execute('SELECT moves_left FROM turn_check_move WHERE faction=?',(faction,)).fetchone()
            if row and row[0]<=0:
                return False,'На этом ходу не осталось перемещений.'
    return True,city[0]


def begin_hunt(conn,site_id,faction):
    from utils.garrison_stats import garrison_totals
    from terrain_journeys import _credit,_experience
    ensure_schema(conn)
    site=next((s for s in sites(conn) if s['id']==site_id),None)
    if site is None:
        raise ValueError('Логово больше не существует.')
    with conn:
        allowed,source=hunt_status(conn,site,faction)
        if not allowed:
            raise ValueError(source)
        if not _experience(conn):
            conn.execute('ALTER TABLE garrisons ADD COLUMN experience INTEGER DEFAULT 0')
        attack=garrison_totals(conn,source)['attack']
        if not math.isfinite(attack) or attack<0:
            raise ValueError('Некорректные характеристики отряда.')
        cur=conn.execute('INSERT INTO monster_expeditions(site_id,faction,source,camp,attack) VALUES(?,?,?,?,?)',
                         (site_id,faction,source,'',attack))
        eid=cur.lastrowid;camp=f'@monster:{eid}'
        conn.execute('UPDATE monster_expeditions SET camp=? WHERE id=?',(camp,eid))
        xp='COALESCE(experience,0)' if _experience(conn) else '0'
        rows=conn.execute(f'SELECT unit_name,unit_count,unit_image,{xp} FROM garrisons WHERE city_name=? AND unit_count>0',
                          (source,)).fetchall()
        for name,count,image,exp in rows:
            _credit(conn,camp,name,count,image or '',exp)
            copy_training(conn,source,camp,name)
        conn.execute('DELETE FROM garrisons WHERE city_name=?',(source,))
        conn.execute('''INSERT INTO monster_progress(faction,last_hunt) VALUES(?,?)
            ON CONFLICT(faction) DO UPDATE SET last_hunt=excluded.last_hunt''',(faction,current_turn(conn)))
        if conn.execute("SELECT 1 FROM pragma_table_info('turn_check_move') WHERE name='moves_left'").fetchone():
            conn.execute('UPDATE turn_check_move SET moves_left=MAX(0,moves_left-1) WHERE faction=?',(faction,))
    return eid


def resolve_hunt(conn,eid):
    """One clash against the authored defense. Retreated armies earn nothing."""
    ensure_schema(conn)
    with conn:
        row=expedition(conn,eid)
        if row is None:
            return None
        if row['stage']!='outbound':
            return json.loads(row['result'])
        site=next(s for s in sites(conn) if s['id']==row['site_id'])
        prize=encounter_reward(site)
        won=row['attack']>=prize['defense']
        result=dict(won=won,name=monster_name(site),attack=row['attack'],**prize)
        result['new_relic']=False
        result['experience']=1 if won else 0
        if won:
            if prize['resources']:
                from utils.resource_payments import ensure_resource_schema
                ensure_resource_schema(conn)
                for resource in ('Кроны','Кристаллы'):
                    updated=conn.execute('UPDATE resources SET amount=amount+? WHERE faction=? AND resource_type=?',
                                         (prize['resources'],row['faction'],resource))
                    if not updated.rowcount:
                        conn.execute('INSERT INTO resources(faction,resource_type,amount) VALUES(?,?,?)',
                                     (row['faction'],resource,prize['resources']))
            from terrain_journeys import _experience
            if not _experience(conn):
                conn.execute('ALTER TABLE garrisons ADD COLUMN experience INTEGER DEFAULT 0')
            until=max(progress(conn,row['faction'])['veteran_until'],current_turn(conn)+prize['duration'])
            _snapshot_training(conn,row['faction'],row['camp'],until)
            conn.execute('''UPDATE garrisons SET experience=COALESCE(experience,0)+1
                WHERE city_name=? AND unit_count>0 AND unit_name IN
                (SELECT unit_name FROM units WHERE CAST(unit_class AS INTEGER)=1)''',(row['camp'],))
            new_relic=prize['legendary'] and not progress(conn,row['faction'])['relic_earned']
            conn.execute('''UPDATE monster_progress SET veteran_until=MAX(veteran_until,?),
                relic_earned=MAX(relic_earned,?) WHERE faction=?''',
                (current_turn(conn)+prize['duration'],int(prize['legendary']),row['faction']))
            conn.execute('UPDATE monster_sites SET ready_turn=?,defeats=defeats+1 WHERE id=?',
                         (current_turn(conn)+COOLDOWN,site['id']))
            result['new_relic']=new_relic
        conn.execute("UPDATE monster_expeditions SET stage='returning',result=? WHERE id=?",(json.dumps(result),eid))
    return result


def finish_hunt(conn,eid):
    """Return real camp troops, preserving natural XP; never enter a foreign city."""
    from terrain_journeys import _credit,_experience
    row=expedition(conn,eid)
    if row is None:
        return True
    if row['stage']=='outbound':
        resolve_hunt(conn,eid)
    candidates=conn.execute('SELECT name FROM cities WHERE faction=? ORDER BY name',(row['faction'],)).fetchall()
    names={r[0] for r in candidates}
    if not names:
        return False
    target=row['source'] if row['source'] in names else candidates[0][0]
    with conn:
        xp='COALESCE(experience,0)' if _experience(conn) else '0'
        for name,count,image,exp in conn.execute(
                f'SELECT unit_name,unit_count,unit_image,{xp} FROM garrisons WHERE city_name=?',(row['camp'],)).fetchall():
            _credit(conn,target,name,count,image,exp)
            copy_training(conn,row['camp'],target,name)
        conn.execute('DELETE FROM garrisons WHERE city_name=?',(row['camp'],))
        conn.execute('DELETE FROM monster_expeditions WHERE id=?',(eid,))
    return True


def recover_hunts(conn):
    """A closed app cannot strand or duplicate an expedition/reward."""
    ensure_schema(conn)
    for eid, in conn.execute('SELECT id FROM monster_expeditions').fetchall():
        finish_hunt(conn,eid)


def owned_artifacts(conn,faction):
    result=[]
    for table,equipment in (('artifacts','hero_equipment'),('artifacts_ai','ai_hero_equipment')):
        try:
            result.extend(dict(table=table,id=aid,name=name,attack=a or 0,defense=d or 0,
                               image=image or '',hero=hero,slot=slot)
                          for aid,name,a,d,image,hero,slot in conn.execute(f'''SELECT a.id,a.name,a.attack,a.defense,
                          a.image_url,e.hero_name,e.slot_type FROM {table} a JOIN {equipment} e ON a.id=e.artifact_id
                          WHERE e.faction_name=? ORDER BY a.id''',(faction,)))
        except sqlite3.OperationalError:
            continue
    return result


def upgrade_artifact(conn,faction,table,aid,stat,hero,slot):
    """Clone the owned item, adding 550 percentage points to one chosen stat."""
    ensure_schema(conn)
    if stat not in ('attack','defense') or table not in ('artifacts','artifacts_ai'):
        raise ValueError('Нужно выбрать атаку или защиту существующего артефакта.')
    with conn:
        state=progress(conn,faction)
        if not state['relic_earned'] or state['relic_used']:
            raise ValueError('Одноразовое улучшение недоступно.')
        owned=next((a for a in owned_artifacts(conn,faction) if
                    (a['table'],a['id'],a['hero'],str(a['slot']))==(table,aid,hero,str(slot))),None)
        if owned is None:
            raise ValueError('Артефакт больше не принадлежит вашему герою.')
        equipment='hero_equipment' if table=='artifacts' else 'ai_hero_equipment'
        columns=[r[1] for r in conn.execute(f'PRAGMA table_info({table})')]
        data=dict(zip(columns,conn.execute(f'SELECT * FROM {table} WHERE id=?',(aid,)).fetchone()))
        data['id']=conn.execute(f'SELECT COALESCE(MAX(id),0)+1 FROM {table}').fetchone()[0]
        data[stat]=(data[stat] or 0)+550
        data['name']=(data.get('name') or 'Артефакт')+' · Дар бездны'
        conn.execute(f'INSERT INTO {table}('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',
                     [data[c] for c in columns])
        conn.execute(f'UPDATE {equipment} SET artifact_id=? WHERE faction_name=? AND hero_name=? AND slot_type=? AND artifact_id=?',
                     (data['id'],faction,hero,slot,aid))
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='artifact_effects_log'").fetchone():
            offset=0 if table=='artifacts' else 1_000_000
            conn.execute('DELETE FROM artifact_effects_log WHERE hero_name=? AND artifact_id=?',(hero,aid+offset))
        conn.execute('UPDATE monster_progress SET relic_used=1 WHERE faction=?',(faction,))
        conn.execute('INSERT INTO monster_artifact_upgrades VALUES(?,?,?,?,?)',
                     (faction,table,data['id'],stat,current_turn(conn)))
    return data


def artifact_visible(conn,faction,aid,table='artifacts'):
    try:
        owner=conn.execute('SELECT faction FROM monster_artifact_upgrades WHERE artifact_table=? AND artifact_id=?',
                           (table,aid)).fetchone()
        return not owner or owner[0]==faction
    except sqlite3.OperationalError:
        return True
