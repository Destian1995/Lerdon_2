"""Independent portal cities and transactional expedition markets (no Kivy).

Foreign cities never enter `cities`, so capture, tax and AI expansion cannot
change them. Expedition troops remain in garrisons for upkeep and hero limits.
"""
from contextlib import contextmanager
import random
import sqlite3

from city_war import current_turn
from city_construction import faction_garrison_consumption
from terrain_journeys import _credit, _camp_units
from utils.resource_payments import ensure_resource_schema
from otherworld_content import BACKGROUND,CITY_POSITIONS,CITY_ROADS,unit_catalog,artifact_catalog

WORLD_NAME = 'Зазеркалье'
QUEST_GARRISON_DEFENSE = 170_000_000
CITY_GARRISON_DEFENSE = 45_000_000
CITY_NAMES = ('Врата странников', 'Аметистовая гавань', 'Серебряный приют',
              'Лунный предел', 'Обсидиановый торг', 'Башни рассвета', 'Звёздный перекрёсток')


@contextmanager
def atomic(conn):
    conn.execute('SAVEPOINT otherworld_action')
    try:
        yield
        conn.execute('RELEASE otherworld_action')
    except Exception:
        conn.execute('ROLLBACK TO otherworld_action')
        conn.execute('RELEASE otherworld_action')
        raise


def ensure_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_worlds(
        id INTEGER PRIMARY KEY,name TEXT NOT NULL,background TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_cities(
        id INTEGER PRIMARY KEY,world_id INTEGER NOT NULL,name TEXT NOT NULL,
        x REAL NOT NULL,y REAL NOT NULL,price INTEGER NOT NULL,guards INTEGER NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_roads(
        city1 INTEGER NOT NULL,city2 INTEGER NOT NULL,PRIMARY KEY(city1,city2))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_parties(
        faction TEXT PRIMARY KEY,world_id INTEGER NOT NULL,city_id INTEGER NOT NULL,
        source TEXT NOT NULL,camp TEXT NOT NULL UNIQUE)''')
    from portal_home import install
    install(conn)
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_market(
        city_id INTEGER NOT NULL,kind TEXT NOT NULL,item TEXT NOT NULL,
        stock INTEGER NOT NULL,turn INTEGER NOT NULL,PRIMARY KEY(city_id,kind,item))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_battles(
        city_id INTEGER NOT NULL,faction TEXT NOT NULL,ready_turn INTEGER NOT NULL,
        PRIMARY KEY(city_id,faction))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_guard_buffs(
        faction TEXT PRIMARY KEY,expires_turn INTEGER NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_presentation(
        world_id INTEGER PRIMARY KEY,version INTEGER NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_artifacts(
        faction TEXT NOT NULL,catalog_id INTEGER NOT NULL,artifact_id INTEGER NOT NULL UNIQUE,
        PRIMARY KEY(faction,catalog_id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_beam_journeys(
        faction TEXT PRIMARY KEY,source INTEGER NOT NULL,destination INTEGER NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS portal_return_history(
        faction TEXT PRIMARY KEY,returned_turn INTEGER NOT NULL,source TEXT NOT NULL)''')
    backwards=conn.execute('SELECT city1,city2 FROM portal_roads WHERE city1>city2').fetchall()
    if backwards:
        with atomic(conn):
            for a,b in backwards:
                conn.execute('INSERT OR IGNORE INTO portal_roads VALUES(?,?)',(b,a))
                conn.execute('DELETE FROM portal_roads WHERE city1=? AND city2=?',(a,b))


def upgrade_world(conn):
    """Restyle old campaigns once, keeping city IDs, parties and battle progress."""
    ensure_schema(conn)
    if not conn.execute('SELECT 1 FROM portal_worlds WHERE id=1').fetchone():
        return
    row=conn.execute('SELECT version FROM portal_presentation WHERE world_id=1').fetchone()
    version=row[0] if row else 0
    if version>=7:
        return
    with atomic(conn):
        if version<1:
            conn.execute('UPDATE portal_worlds SET background=? WHERE id=1',(BACKGROUND,))
            for cid,(x,y) in enumerate(CITY_POSITIONS,1):
                conn.execute('UPDATE portal_cities SET x=?,y=? WHERE id=?',(x,y,cid))
            conn.execute('DELETE FROM portal_roads')
            conn.executemany('INSERT INTO portal_roads VALUES(?,?)',CITY_ROADS)
            # Old market keys referred to ordinary faction goods, not local goods.
            conn.execute("DELETE FROM portal_market WHERE kind IN ('unit','artifact')")
        from otherworld_themes import THEMES
        has_unit_type='unit_type' in {row[1] for row in conn.execute('PRAGMA table_info(units)')}
        for faction in THEMES:
            for unit in unit_offers(conn,faction):
                if version<5:
                    conn.execute('UPDATE units SET attack=?,defense=?,durability=?,consumption=?,cost_money=?,image_path=? WHERE unit_name=? AND faction=?',
                             (unit['attack'],unit['defense'],unit['durability'],unit['consumption'],unit['cost_money'],unit['image_path'],
                              'Странник: '+unit['unit_name']+' / '+faction,faction))
                else:
                    conn.execute('UPDATE units SET image_path=? WHERE unit_name=? AND faction=?',
                                 (unit['image_path'],'Странник: '+unit['unit_name']+' / '+faction,faction))
                conn.execute('UPDATE garrisons SET unit_image=? WHERE unit_name=?',
                             (unit['image_path'],'Странник: '+unit['unit_name']+' / '+faction))
                if has_unit_type:
                    conn.execute('UPDATE units SET unit_type=? WHERE unit_name=? AND faction=?',
                                 (unit['unit_type'],'Странник: '+unit['unit_name']+' / '+faction,faction))
        from otherworld_quests import migrate_conflict_sides
        migrate_conflict_sides(conn)
        conn.execute('INSERT OR REPLACE INTO portal_presentation VALUES(1,7)')


def _dicts(cursor):
    keys=[c[0] for c in cursor.description]
    return [dict(zip(keys,row)) for row in cursor]


def world(conn,faction=None):
    ensure_schema(conn)
    rows=_dicts(conn.execute('SELECT * FROM portal_worlds WHERE id=1'))
    result=rows[0] if rows else None
    if result and faction:
        from otherworld_themes import theme,background
        result.update(background=background(faction),name=theme(faction)['name'])
    return result


def create_world(conn,rng=None,background=None):
    """Generate once; all factions visit the same persistent network/markets."""
    ensure_schema(conn)
    existing=world(conn)
    if existing:
        upgrade_world(conn)
        return world(conn)
    rng=rng or random
    background=str(background or BACKGROUND).replace('\\','/')
    from map_terrain import load_terrain
    terrain=load_terrain(background)
    candidates=[(x,y) for x in range(90,1060,40) for y in range(100,660,40)
                if terrain is None or terrain.city_allowed(x-38,y-24)]
    if len(candidates)<7:
        raise ValueError('На карте другого мира недостаточно места для городов.')
    positions=[rng.choice(candidates)]
    while len(positions)<7:
        # Spread cities across the authored land, outside each other's captions.
        positions.append(max((p for p in candidates if p not in positions),
                             key=lambda p:min((p[0]-q[0])**2+(p[1]-q[1])**2 for q in positions)))
    with atomic(conn):
        if background==BACKGROUND:
            positions=list(CITY_POSITIONS)
        conn.execute('INSERT INTO portal_worlds VALUES(1,?,?)',(WORLD_NAME,background))
        for i,((x,y),name) in enumerate(zip(positions,CITY_NAMES),1):
            conn.execute('INSERT INTO portal_cities VALUES(?,1,?,?,?,?,?)',
                         (i,name,x,y,rng.randint(85,135),250+i*120))
        # Connected minimum spanning tree plus short extra links.
        connected={1};edges=set()
        distance=lambda a,b:sum((positions[a-1][i]-positions[b-1][i])**2 for i in (0,1))
        while len(connected)<7:
            a,b=min(((a,b) for a in connected for b in range(1,8) if b not in connected),
                    key=lambda e:distance(*e))
            edges.add(tuple(sorted((a,b))));connected.add(b)
        for i in range(1,8):
            nearest=min((j for j in range(1,8) if j!=i),key=lambda j:distance(i,j))
            edges.add(tuple(sorted((i,nearest))))
        conn.executemany('INSERT INTO portal_roads VALUES(?,?)',CITY_ROADS if background==BACKGROUND else sorted(edges))
        if background==BACKGROUND:
            conn.execute('INSERT OR REPLACE INTO portal_presentation VALUES(1,1)')
    return world(conn)


def cities(conn,faction=None):
    ensure_schema(conn)
    result=_dicts(conn.execute('SELECT * FROM portal_cities ORDER BY id'))
    if faction:
        from otherworld_themes import theme,city_position
        for city in result:
            city['name']=theme(faction)['cities'][city['id']-1]
            city['x'],city['y']=city_position(faction,city['id'])
    return result


def party(conn,faction):
    ensure_schema(conn)
    rows=_dicts(conn.execute('SELECT * FROM portal_parties WHERE faction=?',(faction,)))
    return rows[0] if rows else None


def _party_city(conn,faction):
    p=party(conn,faction)
    if not p:
        raise ValueError('Сначала отправьте отряд через портал.')
    if beam(conn,faction):raise ValueError('Отряд ещё перемещается лучом.')
    city=next(c for c in cities(conn,faction) if c['id']==p['city_id'])
    return p,city


def _move(conn,faction):
    row=conn.execute('SELECT moves_left FROM turn_check_move WHERE faction=?',(faction,)).fetchone()
    if not row or row[0]<1:
        raise ValueError('Нет ходов для похода. Завершите текущий ход.')
    conn.execute('UPDATE turn_check_move SET moves_left=moves_left-1 WHERE faction=?',(faction,))


def departure_units(conn,source):
    """Only troops and class 2–3 heroes may cross; legends stay at home."""
    return [row for row in _camp_units(conn,source) if str(row[7]).split()[0] in ('1','2','3')]


def enter(conn,faction,source):
    create_world(conn)
    with atomic(conn):
        if party(conn,faction):
            raise ValueError('Ваш отряд уже находится в другом мире.')
        owner=conn.execute('SELECT faction FROM cities WHERE name=?',(source,)).fetchone()
        if not owner or owner[0]!=faction:
            raise ValueError('Отправиться можно только из своего города.')
        units=departure_units(conn,source)
        if not any(str(r[7]).split()[0] in ('2','3') for r in units):
            raise ValueError('Для перехода нужен герой 2–3 класса. Герой 4 класса остаётся в основном мире.')
        if not any(str(r[7]).split()[0]=='1' for r in units):
            raise ValueError('Герою нужны войска для путешествия.')
        _move(conn,faction)
        camp='@portal:'+faction
        for name,count,image,exp,*_ in units:
            _credit(conn,camp,name,count,image,exp,training_source=source)
            conn.execute('DELETE FROM garrisons WHERE city_name=? AND unit_name=?',(source,name))
        # A newly validated expedition must not inherit another campaign's loss.
        conn.execute('DELETE FROM portal_home_losses WHERE faction=?',(faction,))
        conn.execute('INSERT INTO portal_parties VALUES(?,1,1,?,?)',(faction,source,camp))
        _collect_city_camp(conn,faction,1,camp)
    return party(conn,faction)


def beam(conn,faction):
    try:
        row=conn.execute('SELECT source,destination FROM portal_beam_journeys WHERE faction=?',(faction,)).fetchone()
        return tuple(row) if row else None
    except sqlite3.OperationalError:
        return None


def city_camp(conn,faction,city_id):
    p=party(conn,faction)
    if p and p['city_id']==city_id and not beam(conn,faction):
        return p['camp']
    return '@portal-city:'+faction+':'+str(city_id)


def _collect_city_camp(conn,faction,city_id,camp):
    local='@portal-city:'+faction+':'+str(city_id)
    for name,count,image,exp,*_ in _camp_units(conn,local):
        _credit(conn,camp,name,count,image,exp,training_source=local)
    conn.execute('DELETE FROM garrisons WHERE city_name=?',(local,))


def begin_beam(conn,faction,destination,selected_units=None,source=None):
    with atomic(conn):
        p,_=_party_city(conn,faction)
        if source is not None and int(source)!=p['city_id']:
            source=int(source)
            local='@portal-city:'+faction+':'+str(source)
            if not _camp_units(conn,local):
                raise ValueError('В этом городе нет ваших войск.')
            parked='@portal-city:'+faction+':'+str(p['city_id'])
            for name,count,image,exp,*_ in _camp_units(conn,p['camp']):
                _credit(conn,parked,name,count,image,exp,training_source=p['camp'])
            conn.execute('DELETE FROM garrisons WHERE city_name=?',(p['camp'],))
            conn.execute('UPDATE portal_parties SET city_id=? WHERE faction=?',(source,faction))
            _collect_city_camp(conn,faction,source,p['camp'])
            p=party(conn,faction)
        destination=int(destination)
        if destination==p['city_id'] or not conn.execute('SELECT 1 FROM portal_cities WHERE id=?',(destination,)).fetchone():
            raise ValueError('Выберите другой город Зазеркалья.')
        units=_camp_units(conn,p['camp'])
        selected=set(selected_units) if selected_units is not None else {r[0] for r in units}
        if not selected or not selected.issubset({r[0] for r in units}):
            raise ValueError('Выберите доступные отряды для похода.')
        _move(conn,faction)
        local='@portal-city:'+faction+':'+str(p['city_id'])
        for name,count,image,exp,*_ in units:
            if name not in selected:
                _credit(conn,local,name,count,image,exp,training_source=p['camp'])
                conn.execute('DELETE FROM garrisons WHERE city_name=? AND unit_name=?',(p['camp'],name))
        conn.execute('INSERT INTO portal_beam_journeys VALUES(?,?,?)',(faction,p['city_id'],destination))


def finish_beam(conn,faction):
    with atomic(conn):
        pending=beam(conn,faction)
        if pending:
            conn.execute('UPDATE portal_parties SET city_id=? WHERE faction=?',(pending[1],faction))
            conn.execute('DELETE FROM portal_beam_journeys WHERE faction=?',(faction,))
            _collect_city_camp(conn,faction,pending[1],party(conn,faction)['camp'])


def travel(conn,faction,destination):
    begin_beam(conn,faction,destination)
    finish_beam(conn,faction)


def return_home(conn,faction):
    with atomic(conn):
        p,_=_party_city(conn,faction)
        conn.execute('''INSERT INTO portal_return_history VALUES(?,?,?) ON CONFLICT(faction)
            DO UPDATE SET returned_turn=excluded.returned_turn,source=excluded.source''',
            (faction,current_turn(conn),p['source']))
        from portal_home import loss_reason
        reason=loss_reason(conn,faction)
        if reason:raise ValueError(reason)
        if p['city_id']!=1:
            raise ValueError('Для возвращения дойдите до Врат странников.')
        home=conn.execute('SELECT name FROM cities WHERE name=? AND faction=?',(p['source'],faction)).fetchone()
        if not home:
            raise ValueError('В основном мире не осталось вашего города для возвращения.')
        _move(conn,faction)
        for name,count,image,exp,*_ in _camp_units(conn,p['camp']):
            _credit(conn,home[0],name,count,image,exp,training_source=p['camp'])
        conn.execute('DELETE FROM garrisons WHERE city_name=?',(p['camp'],))
        if conn.execute("SELECT 1 FROM sqlite_master WHERE name='monster_training_ranks'").fetchone():
            conn.execute('DELETE FROM monster_training_ranks WHERE city_name=?',(p['camp'],))
        conn.execute('DELETE FROM portal_parties WHERE faction=?',(faction,))
    return home[0]


def unit_offers(conn,faction=None):
    catalog=unit_catalog(faction)
    if not faction:return catalog
    columns=[r[1] for r in conn.execute('PRAGMA table_info(units)')]
    rows=[dict(zip(columns,row)) for row in conn.execute(
        "SELECT * FROM units WHERE faction=? AND unit_class='1' AND unit_name NOT LIKE 'Странник:%' ORDER BY id",(faction,))]
    # A shared reference preserves ascending prices/power even when ordinary
    # faction roles have radically different prices and stat distributions.
    candidates=[r for r in rows if (r.get('attack') or 0)+(r.get('defense') or 0)>0]
    base=dict(min(candidates or catalog,key=lambda u:(max(1,u.get('cost_money') or 0),u['id'])))
    for item in catalog:
        from otherworld_content import balance_mirror_unit
        balance_mirror_unit(item,base,faction)
    return catalog


def recruitment_limit(conn,faction,template_id):
    """Read-only availability for the quantity mixer; recruit validates again."""
    _,city=_party_city(conn,faction)
    unit=next(u for u in unit_offers(conn,faction) if u['id']==template_id)
    cash=sum(r[0] for r in conn.execute("SELECT amount FROM resources WHERE faction=? AND resource_type='Кроны'",(faction,)))
    owned=conn.execute('SELECT COUNT(*) FROM cities WHERE faction=?',(faction,)).fetchone()[0]
    towers=conn.execute("SELECT COALESCE(SUM(count),0) FROM buildings WHERE faction=? AND building_type IN ('Цитадель','Вышка')",(faction,)).fetchone()[0]
    used=faction_garrison_consumption(conn,faction)
    stock=conn.execute("SELECT stock,turn FROM portal_market WHERE city_id=? AND kind='unit' AND item=?",
                       (city['id'],faction+':'+str(template_id))).fetchone()
    available=stock[0] if stock and stock[1]==current_turn(conn) else 1000
    capacity=max(0,4000+owned*1000+towers*500-used)
    return max(0,min(available,int(cash//price(city,unit['cost_money'])),
                     int((capacity+1e-8)//unit['consumption']) if unit['consumption'] else 1000))


def artifact_offers(conn,faction=None):
    if faction:
        from portal_items import offers
        return offers(conn,faction)
    return artifact_catalog()


def price(city,base):
    return max(1,(int(base)*city['price']+99)//100)


def _stock(conn,city,kind,item,limit):
    turn=current_turn(conn)
    conn.execute('''INSERT INTO portal_market VALUES(?,?,?,?,?)
        ON CONFLICT(city_id,kind,item) DO UPDATE SET stock=excluded.stock,turn=excluded.turn
        WHERE portal_market.turn<>excluded.turn''',(city,kind,str(item),limit,turn))
    return conn.execute('SELECT stock FROM portal_market WHERE city_id=? AND kind=? AND item=?',
                        (city,kind,str(item))).fetchone()[0]


def _take(conn,city,kind,item,quantity,limit):
    if _stock(conn,city,kind,item,limit)<quantity:
        raise ValueError('У торговца недостаточно товара. Запас обновится на следующем ходу.')
    conn.execute('UPDATE portal_market SET stock=stock-? WHERE city_id=? AND kind=? AND item=?',
                 (quantity,city,kind,str(item)))


def _pay(conn,faction,resource,amount):
    if conn.execute('UPDATE resources SET amount=amount-? WHERE faction=? AND resource_type=? AND amount>=?',
                    (amount,faction,resource,amount)).rowcount!=1:
        raise ValueError('Недостаточно '+resource.lower()+'.')


def _grant(conn,faction,resource,amount):
    conn.execute('''INSERT INTO resources(faction,resource_type,amount) VALUES(?,?,?)
        ON CONFLICT(faction,resource_type) DO UPDATE SET amount=resources.amount+excluded.amount''',
                 (faction,resource,amount))


def trade_crystals(conn,faction,buy=True):
    """Turn-bound floating quotes; city recruitment markups never affect crystals."""
    ensure_resource_schema(conn)
    with atomic(conn):
        _,city=_party_city(conn,faction)
        quantity=10_000
        _take(conn,city['id'],'resource',faction+(':buy' if buy else ':sell'),quantity,100_000)
        coins=crystal_trade_price(conn,buy)
        _pay(conn,faction,'Кроны' if buy else 'Кристаллы',coins if buy else quantity)
        _grant(conn,faction,'Кристаллы' if buy else 'Кроны',quantity if buy else coins)
    return coins


def crystal_quote(conn):
    """Same 76.3–148.7 per-100 range and ±4.5 walk as the main crystal market."""
    conn.execute('CREATE TABLE IF NOT EXISTS portal_crystal_quotes(turn INTEGER PRIMARY KEY,price REAL NOT NULL)')
    turn=current_turn(conn)
    row=conn.execute('SELECT price FROM portal_crystal_quotes WHERE turn=?',(turn,)).fetchone()
    if row:return row[0]
    previous=conn.execute('SELECT price FROM portal_crystal_quotes WHERE turn<? ORDER BY turn DESC LIMIT 1',(turn,)).fetchone()
    value=round(max(76.3,min(148.7,previous[0]+random.uniform(-4.5,4.5))) if previous else random.uniform(76.3,148.7),2)
    with atomic(conn):conn.execute('INSERT INTO portal_crystal_quotes VALUES(?,?)',(turn,value))
    return value


def crystal_trade_price(conn,buy=True):
    # Ten thousand crystals = one hundred 100-crystal market lots. A small
    # bid/ask spread prevents a profitable same-turn buy/sell loop.
    base=round(crystal_quote(conn)*100)
    return (base*105+99)//100 if buy else base*95//100


def recruit(conn,faction,template_id,quantity=100):
    if not isinstance(quantity,int) or quantity<1 or quantity>1000:
        raise ValueError('Можно нанять от 1 до 1000 бойцов.')
    ensure_resource_schema(conn)
    with atomic(conn):
        p,city=_party_city(conn,faction)
        template=next((u for u in unit_offers(conn,faction) if u['id']==template_id),None)
        if not template:
            raise ValueError('Такого юнита у торговца нет.')
        _take(conn,city['id'],'unit',faction+':'+str(template_id),quantity,1000)
        owned=conn.execute('SELECT COUNT(*) FROM cities WHERE faction=?',(faction,)).fetchone()[0]
        towers=conn.execute("SELECT COALESCE(SUM(count),0) FROM buildings WHERE faction=? AND building_type IN ('Цитадель','Вышка')",(faction,)).fetchone()[0]
        consumption=faction_garrison_consumption(conn,faction)
        if consumption+quantity*(template.get('consumption') or 0)>4000+owned*1000+towers*500:
            raise ValueError('Недостаточно лимита армии для найма.')
        cost=price(city,template['cost_money'])*quantity
        _pay(conn,faction,'Кроны',cost)
        name='Странник: '+template['unit_name']+' / '+faction
        # Faction-owned templates keep consumption, XP, combat and army limits
        # working after the mercenaries return to the ordinary world.
        available={r[1] for r in conn.execute('PRAGMA table_info(units)')}
        clone={k:v for k,v in template.items() if k!='id' and k in available}
        clone.update(unit_name=name,faction=faction)
        columns=list(clone)
        if not conn.execute('SELECT 1 FROM units WHERE unit_name=?',(name,)).fetchone():
            conn.execute('INSERT INTO units('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',
                         [clone[k] for k in columns])
        _credit(conn,p['camp'],name,quantity,template['image_path'],0)
    return cost


def buy_artifact(conn,faction,artifact_id,hero=None):
    """Equip the purchased slot immediately, using the normal seasonal engine."""
    ensure_resource_schema(conn)
    with atomic(conn):
        p,city=_party_city(conn,faction)
        artifact=next((a for a in artifact_offers(conn,faction) if a['id']==artifact_id),None)
        if not artifact:
            raise ValueError('Такого артефакта у торговца нет.')
        from portal_items import champions,issue,remaining
        eligible=champions(conn,faction,p['camp'])
        if not eligible:raise ValueError('Для артефакта нужен герой 3 класса в отряде.')
        hero=hero or eligible[0]
        active=conn.execute('SELECT artifact_id FROM portal_artifacts WHERE faction=? AND catalog_id=?',(faction,artifact_id)).fetchone()
        if active and (remaining(conn,active[0]) or 0)>0:
            raise ValueError('Этот артефакт уже действует. Дождитесь окончания его срока.')
        _take(conn,city['id'],'artifact',faction+':'+str(artifact_id),1,1)
        cost=price(city,artifact['cost'])
        _pay(conn,faction,'Кроны',cost)
        aid=issue(conn,faction,p['camp'],artifact,hero)
        conn.execute('''INSERT INTO portal_artifacts VALUES(?,?,?) ON CONFLICT(faction,catalog_id)
            DO UPDATE SET artifact_id=excluded.artifact_id''',(faction,artifact_id,aid))
    return cost


def battle_ready(conn,faction):
    p,city=_party_city(conn,faction)
    row=conn.execute('SELECT ready_turn FROM portal_battles WHERE city_id=? AND faction=?',(city['id'],faction)).fetchone()
    return max(0,(row[0] if row else 0)-current_turn(conn))


def guard_profile(conn,faction,city):
    from otherworld_quests import war_target
    from otherworld_themes import image_path
    target=war_target(conn,faction,city['id'])
    count=100_000 if target else city['guards']
    attack=round((45+city['id']*15)*(1.5 if target else 1))
    defense=QUEST_GARRISON_DEFENSE//count if target else (CITY_GARRISON_DEFENSE+count-1)//count
    kind=unit_catalog(faction)[0]['unit_type']
    guard=dict(unit_name=target or 'Стражи '+city['name'],unit_count=count,initial_count=count,
               unit_image=image_path(faction,'units','boss') if target else unit_catalog(faction)[0]['image_path'],
               unit_class='1',attack=attack,defense=defense,durability=0,
               unit_type=kind,initiative=50,morale=100,crit_chance=5)
    guard['units_stats']={'Урон':attack,'Защита':defense,'Живучесть':0,'Класс юнита':'1','Тип':kind}
    return guard,target


def guard_bonus_left(conn,faction):
    ensure_schema(conn)
    row=conn.execute('SELECT expires_turn FROM portal_guard_buffs WHERE faction=?',(faction,)).fetchone()
    return max(0,row[0]-current_turn(conn)) if row else 0


def expedition_profiles(conn,faction,camp):
    from utils.garrison_stats import garrison_profiles
    profiles=garrison_profiles(conn,camp,faction=faction)
    if guard_bonus_left(conn,faction):
        for profile in profiles.values():profile['attack']*=1.03
    return profiles


def fight_guards(conn,faction,skirmish=None,encounter=None,tactical=False):
    """Use ordinary skirmish rules but never invoke city capture/political writes."""
    if skirmish is None:
        from fight import battle_chain
        skirmish=battle_chain
    from utils.garrison_stats import garrison_profiles
    ensure_resource_schema(conn)
    with atomic(conn):
        p,city=_party_city(conn,faction)
        if encounter is None and battle_ready(conn,faction):
            raise ValueError('Следующий бой здесь через '+str(battle_ready(conn,faction))+' х.')
        from battle_presentation import pick_battle_image
        roster=_camp_units(conn,p['camp'])
        portraits=[]
        for name,_,image,*rest in roster:
            if not image:
                row=conn.execute('SELECT image_path FROM units WHERE unit_name=?',(name,)).fetchone()
                image=row[0] if row else None
            portraits.append(dict(unit_class=rest[-1],unit_image=image))
        attacker_image=pick_battle_image(portraits,faction)
        profiles=expedition_profiles(conn,faction,p['camp'])
        army=[]
        for name,count,image,exp,attack,defense,durability,cls in _camp_units(conn,p['camp']):
            if str(cls).split()[0]!='1':
                continue  # Heroes supply the same aura, and retreat with survivors.
            profile=profiles[name]
            template=_dicts(conn.execute('SELECT * FROM units WHERE unit_name=?',(name,)))[0]
            kind=template.get('unit_type') or 'infantry'
            army.append(dict(unit_name=name,unit_count=count,initial_count=count,unit_class='1',
                             unit_image=image,
                             attack=profile['attack'],defense=profile['defense'],durability=0,
                             units_stats={'Урон':profile['attack'],'Защита':profile['defense'],
                                          'Живучесть':0,'Класс юнита':'1','Тип':kind,
                                          'Инициатива':template.get('initiative',50),'Крит':template.get('crit_chance',5)},
                             unit_type=kind,initiative=50,morale=100,crit_chance=5))
        if not army:
            raise ValueError('Для боя нужны обычные войска в отряде.')
        from otherworld_quests import battle_won
        guard,target=(encounter,None) if encounter is not None else guard_profile(conn,faction,city)
        initial=sum(u['unit_count'] for u in army);frames=[]
        tactical_state=None
        if tactical:
            from fight import TYPE_MOD,_get_season_mult
            from tactical_battle_bridge import request_battle,battle_context
            from monster_sites import experience_multiplier
            tactical_army=[]
            for name,count,image,exp,attack,defense,durability,cls in _camp_units(conn,p['camp']):
                template=_dicts(conn.execute('SELECT * FROM units WHERE unit_name=?',(name,)))[0]
                regular=str(cls).split()[0]=='1'
                tactical_army.append(dict(unit_name=name,unit_count=count,initial_count=count,
                    unit_image=image or template.get('image_path'),
                    consumption=template.get('consumption') or 0,
                    _experience_multiplier=experience_multiplier(conn,faction,exp,p['camp'],name) if regular else 1,
                    _encounter_attack_multiplier=1.03 if not regular and guard_bonus_left(conn,faction) else 1,
                    units_stats={'Урон':attack,'Защита':defense,'Живучесть':durability,'Класс юнита':cls,
                                 'Тип':template.get('unit_type') or 'infantry',
                                 'Инициатива':template.get('initiative') or 50,'Крит':template.get('crit_chance') or 5}))
                if regular:
                    # The quick Mirror fight receives these completed profiles
                    # rather than raw soldiers. Preserve that exact rounding.
                    tactical_army[-1]['_quick_combat_power']=(int(profiles[name]['attack']),int(profiles[name]['defense']))
            context=battle_context(conn,city['name'],faction)
            context['season_multipliers']={faction:_get_season_mult(faction,conn)}
            context['morale_rules']=False
            tactical_state=request_battle(tactical_army,[guard],'attacker',city['name'],context,TYPE_MOD,
                                           (faction,'Независимая стража'))
            if tactical_state is not None:
                army=tactical_army
                tactical_state.apply_to(army,[guard])
                frames=list(tactical_state.frames)
        for round_number in range(1,61) if tactical_state is None else ():
            if guard['unit_count']<=0 or not any(u['unit_count']>0 for u in army):
                break
            before=(sum(u['unit_count'] for u in army),guard['unit_count'])
            for unit in army:
                if unit['unit_count']>0 and guard['unit_count']>0:
                    skirmish(unit,guard,city['name'],faction,conn,damage_infrastructure=False)
            frames.append(dict(round=round_number,atk_max=initial,def_max=guard['initial_count'],
                               atk_total=sum(u['unit_count'] for u in army),def_total=guard['unit_count']))
            if before==(sum(u['unit_count'] for u in army),guard['unit_count']):
                break
        won=tactical_state.winner=='attacker' if tactical_state is not None else guard['unit_count']<=0
        for unit in army:
            conn.execute('UPDATE garrisons SET unit_count=?,experience=COALESCE(experience,0)+? WHERE city_name=? AND unit_name=?',
                         (unit['unit_count'],int(won and str(unit['units_stats'].get('Класс юнита',1)).split()[0]=='1'),p['camp'],unit['unit_name']))
        conn.execute('DELETE FROM garrisons WHERE city_name=? AND unit_count<=0',(p['camp'],))
        if encounter is None:
            conn.execute('INSERT INTO portal_battles VALUES(?,?,?) ON CONFLICT(city_id,faction) DO UPDATE SET ready_turn=excluded.ready_turn',
                         (city['id'],faction,current_turn(conn)+5))
        coins=(10_000+city['id']*5000) if won and encounter is None else 0
        if coins:
            _grant(conn,faction,'Кроны',coins)
        if won and encounter is None:
            conn.execute('INSERT INTO portal_guard_buffs VALUES(?,?) ON CONFLICT(faction) DO UPDATE SET expires_turn=excluded.expires_turn',
                         (faction,current_turn(conn)+9))
        quest_win=battle_won(conn,faction,city['id']) if won and encounter is None else False
    return dict(won=won,coins=coins,city=city['name'],army=army,guards=[guard],rounds=frames,quest_win=quest_win,quest_target=target,
                attacker_image=attacker_image,tactical=tactical_state is not None)
