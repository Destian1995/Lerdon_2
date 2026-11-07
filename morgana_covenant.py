"""Optional player allegiance to Morgana; ownership and expedition IDs stay stable."""
import ast
import sqlite3
from city_war import current_turn

LEGION_PREFIX='Легион: '
FACTIONS=('Север','Эльфы','Вампиры','Адепты','Элины','Мятежники')


def state(conn,faction):
    try:
        cursor=conn.execute('SELECT * FROM morgana_covenants WHERE faction=?',(faction,));row=cursor.fetchone()
    except sqlite3.OperationalError:return None
    return dict(zip((c[0] for c in cursor.description),row)) if row else None


def serving(conn,faction):
    row=state(conn,faction)
    return bool(row and row['status']=='accepted')


def multiplier(conn,faction):return 1.45 if serving(conn,faction) else 1


def peace_locked(conn,a,b):
    return a!=b and 'Нежить' not in (a,b) and (serving(conn,a) or serving(conn,b))


def ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS morgana_covenants(
        faction TEXT PRIMARY KEY,status TEXT NOT NULL,offered_turn INTEGER NOT NULL,
        accepted_turn INTEGER,notified INTEGER NOT NULL DEFAULT 0)''')


def undead_present(conn):
    return bool(conn.execute("SELECT 1 FROM cities WHERE faction='Нежить' LIMIT 1").fetchone())


def offer(conn,faction):
    from mirror_monster_quest import pact
    ensure_schema(conn)
    if not state(conn,faction) and pact(conn,faction) and undead_present(conn):
        conn.execute('INSERT INTO morgana_covenants VALUES(?,?,?,NULL,0)',(faction,'offered',current_turn(conn)))
    return state(conn,faction)


def presentation_faction(conn,city,owner):
    return 'Нежить' if serving(conn,owner) else owner


def _locked_status(a,b):
    other='CASE WHEN NEW.faction1=c.faction THEN NEW.faction2 ELSE NEW.faction1 END'
    return f"CASE WHEN ({other})='Нежить' THEN {a} ELSE {b} END"


def install_wars(conn):
    """Enforce allegiance even when diplomacy changes through events or AI."""
    conn.execute('CREATE TABLE IF NOT EXISTS diplomacies(faction1 TEXT,faction2 TEXT,relationship TEXT,UNIQUE(faction1,faction2))')
    conn.execute('CREATE TABLE IF NOT EXISTS relations(faction1 TEXT,faction2 TEXT,relationship INTEGER,UNIQUE(faction1,faction2))')
    for table,ally,enemy in (('diplomacies',"'союз'","'война'"),('relations','100','0')):
        value=_locked_status(ally,enemy)
        condition="c.status='accepted' AND (NEW.faction1=c.faction OR NEW.faction2=c.faction) AND NEW.faction1<>NEW.faction2 AND NEW.faction1<>'Нейтрал' AND NEW.faction2<>'Нейтрал'"
        for operation in ('INSERT','UPDATE'):
            conn.execute(f'''CREATE TRIGGER IF NOT EXISTS morgana_{table}_{operation.lower()}
                AFTER {operation} ON {table} WHEN EXISTS(SELECT 1 FROM morgana_covenants c WHERE {condition})
                BEGIN UPDATE {table} SET relationship=(SELECT {value} FROM morgana_covenants c WHERE {condition} LIMIT 1)
                WHERE rowid=NEW.rowid AND relationship IS NOT (SELECT {value} FROM morgana_covenants c WHERE {condition} LIMIT 1); END''')
        old_condition=condition.replace('NEW.','OLD.')
        old_value=value.replace('NEW.','OLD.')
        conn.execute(f'''CREATE TRIGGER IF NOT EXISTS morgana_{table}_delete AFTER DELETE ON {table}
            WHEN EXISTS(SELECT 1 FROM morgana_covenants c WHERE {old_condition})
            BEGIN INSERT INTO {table}(faction1,faction2,relationship)
            SELECT OLD.faction1,OLD.faction2,{old_value} FROM morgana_covenants c WHERE {old_condition} LIMIT 1; END''')
    conn.execute('''CREATE TABLE IF NOT EXISTS truces(id INTEGER PRIMARY KEY AUTOINCREMENT,
        faction1 TEXT NOT NULL,faction2 TEXT NOT NULL,truce_until_turn INTEGER NOT NULL,UNIQUE(faction1,faction2))''')
    for operation in ('INSERT','UPDATE'):
        conn.execute(f'''CREATE TRIGGER IF NOT EXISTS morgana_truce_{operation.lower()} AFTER {operation} ON truces
            WHEN NEW.faction1<>'Нежить' AND NEW.faction2<>'Нежить' AND EXISTS(SELECT 1 FROM morgana_covenants c
            WHERE c.status='accepted' AND c.faction IN (NEW.faction1,NEW.faction2))
            BEGIN DELETE FROM truces WHERE rowid=NEW.rowid; END''')
    # The owner remains the player: capture/diplomacy/UI continue to use the
    # original campaign identity, while the town becomes a necropolis.
    columns={r[1] for r in conn.execute('PRAGMA table_info(cities)')}
    if 'is_undead' not in columns:conn.execute('ALTER TABLE cities ADD COLUMN is_undead INTEGER DEFAULT 0')
    conn.execute('''CREATE TRIGGER IF NOT EXISTS morgana_captured_city AFTER UPDATE OF faction ON cities
        WHEN EXISTS(SELECT 1 FROM morgana_covenants WHERE faction=NEW.faction AND status='accepted')
        BEGIN UPDATE cities SET is_undead=1 WHERE rowid=NEW.rowid; END''')


def enforce_wars(conn,faction):
    if not serving(conn,faction):return
    conn.execute("DELETE FROM truces WHERE (faction1=? OR faction2=?) AND faction1<>'Нежить' AND faction2<>'Нежить'",(faction,faction))
    for other in (*FACTIONS,'Нежить'):
        if other==faction:continue
        for a,b in ((faction,other),(other,faction)):
            for table,status in (('diplomacies','союз' if other=='Нежить' else 'война'),('relations',100 if other=='Нежить' else 0)):
                if conn.execute(f'SELECT 1 FROM {table} WHERE faction1=? AND faction2=?',(a,b)).fetchone():
                    conn.execute(f'UPDATE {table} SET relationship=? WHERE faction1=? AND faction2=?',(status,a,b))
                else:conn.execute(f'INSERT INTO {table}(faction1,faction2,relationship) VALUES(?,?,?)',(a,b,status))


def restore_cities(conn,faction):
    from city_construction import CATALOG,ensure_unique_buildings
    if not serving(conn,faction):return
    ensure_unique_buildings(conn)
    conn.execute('UPDATE cities SET is_undead=1 WHERE faction=?',(faction,))
    columns={r[1] for r in conn.execute('PRAGMA table_info(cities)')}
    if 'color_faction' in columns:conn.execute("UPDATE cities SET color_faction='#33BF99' WHERE faction=?",(faction,))
    for kind in CATALOG:
        conn.execute('''INSERT INTO buildings(city_name,faction,building_type,count)
            SELECT name,faction,?,1 FROM cities WHERE faction=?
            ON CONFLICT(city_name,building_type) DO UPDATE SET count=1,faction=excluded.faction''',(kind,faction))


def _legion_units(conn,faction):
    """Personal templates allow normal player controls without stealing AI heroes."""
    result={}
    rows=conn.execute("SELECT * FROM units WHERE faction='Нежить' AND CAST(unit_class AS INTEGER)=1").fetchall()
    names=[c[0] for c in conn.execute('SELECT * FROM units LIMIT 0').description]
    for row in rows:
        data=dict(zip(names,row));original=data['unit_name']
        name=LEGION_PREFIX+original+' / '+faction
        found=conn.execute('SELECT 1 FROM units WHERE unit_name=?',(name,)).fetchone()
        if not found:
            data.pop('id',None);data.update(unit_name=name,faction=faction)
            conn.execute('INSERT INTO units('+','.join(data)+') VALUES('+','.join('?' for _ in data)+')',tuple(data.values()))
        result[original]=name
    return result


def accept(conn,faction):
    import otherworlds as worlds
    from mirror_monster_quest import pact
    from terrain_journeys import _credit
    from city_construction import faction_garrison_consumption
    ensure_schema(conn)
    with worlds.atomic(conn):
        row=offer(conn,faction);deal=pact(conn,faction)
        if not row or row['status']!='offered' or not undead_present(conn) or not deal:
            raise ValueError('Предложение Морганы сейчас недоступно.')
        if current_turn(conn)>=deal['deadline']:raise ValueError('Срок сделки за душу уже истёк.')
        homes=[r[0] for r in conn.execute('SELECT name FROM cities WHERE faction=? ORDER BY id',(faction,))]
        if not homes:raise ValueError('Для принятия легиона нужен собственный город.')
        conn.execute("UPDATE morgana_covenants SET status='accepted',accepted_turn=? WHERE faction=?",(current_turn(conn),faction))
        install_wars(conn);enforce_wars(conn,faction);restore_cities(conn,faction)
        templates=_legion_units(conn,faction)
        # Fill only the new capacity; the independent royal armies retain their
        # heroes and the rest of their soldiers, including the capital guard.
        towers=conn.execute("SELECT COUNT(*) FROM buildings WHERE faction=? AND building_type='Цитадель' AND count>0",(faction,)).fetchone()[0]
        room=max(0,int((4000+1000*len(homes)+500*towers)*1.45)-faction_garrison_consumption(conn,faction))
        party=worlds.party(conn,faction)
        destination=party['camp'] if party else homes[0]
        transferred=0
        for city,name,count,image,consumption in conn.execute('''SELECT g.city_name,g.unit_name,g.unit_count,g.unit_image,u.consumption
            FROM garrisons g JOIN cities c ON c.name=g.city_name JOIN units u ON u.unit_name=g.unit_name
            WHERE c.faction='Нежить' AND u.faction='Нежить' AND CAST(u.unit_class AS INTEGER)=1 AND g.unit_count>0
            ORDER BY g.city_name,g.unit_name''').fetchall():
            if name=='Лучник нежити':continue
            take=min(count//3,int(room/max(.01,float(consumption or 0))))
            if take<=0:continue
            _credit(conn,destination,templates[name],take,image)
            conn.execute('UPDATE garrisons SET unit_count=unit_count-? WHERE city_name=? AND unit_name=?',(take,city,name))
            room-=take*(consumption or 0);transferred+=take
    return transferred


def decline(conn,faction):
    row=offer(conn,faction)
    if not row or row['status']!='offered':raise ValueError('Предложения нет.')
    conn.execute("UPDATE morgana_covenants SET status='declined' WHERE faction=?",(faction,))


def turn(conn,faction):
    row=state(conn,faction)
    if row and row['status']=='accepted':
        enforce_wars(conn,faction);restore_cities(conn,faction)
    else:offer(conn,faction)


def won(conn,faction):
    return serving(conn,faction) and not conn.execute("SELECT 1 FROM cities WHERE faction NOT IN (?, 'Нежить','Нейтрал') LIMIT 1",(faction,)).fetchone()


def ally_attacks(ai):
    """Morgana and Nizar each march with their own hero and troop detachment."""
    allies={r[0] for r in ai.db_connection.execute("SELECT faction FROM morgana_covenants WHERE status='accepted'")}
    for hero in ('Низар','Моргана'):
        source=ai.cursor.execute('''SELECT c.name,c.coordinates FROM garrisons g JOIN cities c ON c.name=g.city_name
            WHERE g.unit_name=? AND g.unit_count>0 AND c.faction='Нежить' LIMIT 1''',(hero,)).fetchone()
        if not source:continue
        origin=ast.literal_eval(source[1])
        targets=[]
        for name,coords,faction in ai.cursor.execute("SELECT name,coordinates,faction FROM cities WHERE faction NOT IN ('Нежить','Нейтрал')"):
            if faction in allies:continue
            point=ast.literal_eval(coords)
            targets.append(((point[0]-origin[0])**2+(point[1]-origin[1])**2,name,faction))
        if targets:
            _,target,faction=min(targets)
            ai._undead_direct_attack(source[0],target,faction,hero=hero)


def resolve_royal_attack(ai,source,target,defender,detachment):
    """Move only the chosen leader's detachment; never sweep the other army."""
    from terrain_journeys import _credit
    conn=ai.db_connection
    defenders=ai.get_defending_army(target)
    if not defenders:
        with conn:
            for unit in detachment:
                count=unit['unit_count'];name=unit['unit_name']
                conn.execute('UPDATE garrisons SET unit_count=unit_count-? WHERE city_name=? AND unit_name=?',(count,source,name))
                _credit(conn,target,name,count,unit['unit_image'])
            conn.execute('DELETE FROM garrisons WHERE unit_count<=0')
            conn.execute("UPDATE cities SET faction='Нежить' WHERE name=?",(target,))
        return
    from fight import fight
    army=[]
    for unit in detachment:
        stats=conn.execute('SELECT attack,defense,durability,unit_class FROM units WHERE unit_name=?',(unit['unit_name'],)).fetchone()
        army.append(dict(unit,units_stats=dict(zip(('Урон','Защита','Живучесть','Класс юнита'),stats))))
    # The ordinary battle resolver accounts for survivors and ownership itself.
    fight(attacking_city=source,defending_city=target,defending_army=defenders,attacking_army=army,
          attacking_fraction='Нежить',defending_fraction=defender,conn=conn)
