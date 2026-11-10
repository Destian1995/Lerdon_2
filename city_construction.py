"""One authoritative building catalogue and atomic purchases for city interiors."""
LEGACY_PRODUCTION_MULTIPLIER=12
HOSPITAL_GROWTH=50*LEGACY_PRODUCTION_MULTIPLIER*65//100
FACTORY_YIELD=105*LEGACY_PRODUCTION_MULTIPLIER*65//100
AI_FACTORY_YIELD=100*LEGACY_PRODUCTION_MULTIPLIER*65//100
DEFENSE_BONUS=.15
DEFENSE_NAMES={'Север':'Арсенал','Элины':'Пещера дракона','Вампиры':'Стена',
               'Эльфы':'Древо силы','Адепты':'Аббатство'}


def building_name(faction,building):
    """Faction presentation; keep the stable building ID for existing saves."""
    return DEFENSE_NAMES.get(faction,'Стена') if building=='Стена' else building

CATALOG={
    'Больница':dict(key='hospital',cost=1000,max=1,desc=f'+{HOSPITAL_GROWTH} населения и рабочих/ход',color=(.80,.22,.35,1)),
    'Фабрика':dict(key='factory',cost=1500,max=1,desc=f'+{FACTORY_YIELD} кристаллов/ход',color=(.50,.50,.12,1)),
    'Стена':dict(key='wall',cost=4000,max=1,desc=f'+{DEFENSE_BONUS*100:g}% защита гарнизона',color=(.45,.45,.55,1)),
    'Рынок':dict(key='market',cost=3000,max=1,desc='Смирение: +10% доход крон (Север: +15%). Борьба: +65% добыча кристаллов (Элины: +110%).',color=(.85,.65,.10,1)),
    'Кузница':dict(key='forge',cost=3000,max=1,desc='−5% потребление кристаллов гарнизоном города',color=(.60,.38,.12,1)),
    'Цитадель':dict(key='citadel',cost=5000,max=1,desc='+500 лимит армии',color=(.20,.55,.75,1)),
}


def building_description(conn,faction,building):
    if building=='Рынок':
        from utils.market_income import market_policy
        resource,percent=market_policy(conn,faction)
        return f'+{percent}% '+('дохода крон (Смирение)' if resource=='Кроны' else 'добычи кристаллов (Борьба)')
    return CATALOG[building]['desc']


def ensure_unique_buildings(conn):
    # Ownership changes have several entry points (battle, neutral occupation,
    # rebellion and invasion). Enforce demolition in their own transaction.
    conn.execute('''CREATE TRIGGER IF NOT EXISTS demolish_captured_city_buildings
        AFTER UPDATE OF faction ON cities
        WHEN OLD.faction IS NOT NEW.faction
        BEGIN DELETE FROM buildings WHERE city_name=NEW.name; END''')
    # Captures can happen after the uniqueness migration. Infrastructure belongs
    # to its town's current owner, even when the index already exists.
    conn.execute('''UPDATE buildings SET faction=(SELECT faction FROM cities
        WHERE name=buildings.city_name) WHERE EXISTS(SELECT 1 FROM cities
        WHERE name=buildings.city_name AND faction IS NOT buildings.faction)''')
    # Existing saves may already have the uniqueness index and a watchtower.
    if conn.execute("SELECT 1 FROM buildings WHERE building_type='Вышка' LIMIT 1").fetchone():
        conn.execute('SAVEPOINT rename_citadels')
        try:
            conn.execute("""DELETE FROM buildings WHERE building_type='Вышка' AND city_name IN
                (SELECT city_name FROM buildings WHERE building_type='Цитадель')""")
            conn.execute("UPDATE buildings SET building_type='Цитадель' WHERE building_type='Вышка'")
            conn.execute('RELEASE rename_citadels')
        except Exception:
            conn.execute('ROLLBACK TO rename_citadels');conn.execute('RELEASE rename_citadels');raise
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='unique_city_building_types'").fetchone():return
    conn.execute('SAVEPOINT unique_buildings')
    try:
        conn.execute('''UPDATE buildings SET faction=COALESCE((SELECT faction FROM cities
            WHERE name=buildings.city_name),faction),count=CASE WHEN count>0 THEN 1 ELSE 0 END''')
        conn.execute('DELETE FROM buildings WHERE count<=0')
        conn.execute('''DELETE FROM buildings WHERE rowid NOT IN
            (SELECT MAX(rowid) FROM buildings GROUP BY city_name,building_type)''')
        conn.execute('CREATE UNIQUE INDEX unique_city_building_types ON buildings(city_name,building_type)')
        for operation in ('INSERT','UPDATE OF count'):
            suffix='insert' if operation=='INSERT' else 'update'
            conn.execute(f'''CREATE TRIGGER IF NOT EXISTS single_building_{suffix} AFTER {operation} ON buildings
                WHEN NEW.count>1 BEGIN UPDATE buildings SET count=1 WHERE rowid=NEW.rowid; END''')
        conn.execute('RELEASE unique_buildings')
    except Exception:
        conn.execute('ROLLBACK TO unique_buildings');conn.execute('RELEASE unique_buildings');raise


def ensure_neutral_buildings(conn):
    """Neutral towns have the full catalogue, independent of treasury/council."""
    ensure_unique_buildings(conn)
    for building in CATALOG:
        conn.execute('''UPDATE buildings SET count=1 WHERE building_type=? AND count<>1
            AND city_name IN (SELECT name FROM cities WHERE faction='Нейтрал')''',(building,))
        conn.execute('''INSERT INTO buildings(city_name,faction,building_type,count)
            SELECT c.name,c.faction,?,1 FROM cities c WHERE c.faction='Нейтрал'
            AND NOT EXISTS(SELECT 1 FROM buildings b WHERE b.city_name=c.name AND b.building_type=?)''',
            (building,building))


def building_counts(conn,city,faction):
    if faction=='Нейтрал':ensure_neutral_buildings(conn)
    else:ensure_unique_buildings(conn)
    return dict(conn.execute('''SELECT building_type,SUM(count) FROM buildings
        WHERE city_name=? AND faction=? GROUP BY building_type HAVING SUM(count)>0''',(city,faction)))


def city_owner(conn,city):
    row=conn.execute('SELECT faction FROM cities WHERE name=?',(city,)).fetchone()
    return row[0] if row else None


def construction_allowed(conn,city,faction):
    return city_owner(conn,city)==faction


def garrison_consumption_multipliers(conn):
    """A local 5% discount; legacy duplicate smithies never stack."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='buildings'").fetchone():return {}
    return {city:.95 for city, in conn.execute("""SELECT DISTINCT b.city_name FROM buildings b
        JOIN cities c ON c.name=b.city_name AND c.faction=b.faction
        WHERE b.building_type='Кузница' AND b.count>0""")}


def faction_garrison_consumption(conn,faction):
    rates=garrison_consumption_multipliers(conn)
    return sum(count*(consumption or 0)*rates.get(city,1) for city,count,consumption in conn.execute('''
        SELECT g.city_name,g.unit_count,u.consumption FROM garrisons g
        JOIN units u ON g.unit_name=u.unit_name WHERE u.faction=?
        AND g.city_name NOT IN (SELECT name FROM cities WHERE faction='Мятежники')''',(faction,)))


def buy_building(conn,city,faction,building):
    from utils.resource_payments import ensure_resource_schema
    if building not in CATALOG:raise ValueError('Неизвестное здание.')
    ensure_resource_schema(conn)
    conn.execute('SAVEPOINT city_construction')
    try:
        if not construction_allowed(conn,city,faction):raise ValueError('Строительство доступно только в своём городе.')
        info=CATALOG[building];counts=building_counts(conn,city,faction)
        if counts.get(building,0)>=info['max']:raise ValueError('Достигнут предел этого здания.')
        paid=conn.execute('''UPDATE resources SET amount=amount-? WHERE faction=?
            AND resource_type='Кроны' AND amount>=?''',(info['cost'],faction,info['cost']))
        if paid.rowcount!=1:raise ValueError('Недостаточно крон.')
        conn.execute('DELETE FROM buildings WHERE city_name=? AND faction=? AND building_type=?',(city,faction,building))
        conn.execute('INSERT INTO buildings(city_name,faction,building_type,count) VALUES(?,?,?,?)',
                     (city,faction,building,counts.get(building,0)+1))
        from city_war import reconcile_city_rebuilding
        reconcile_city_rebuilding(conn)
        conn.execute('RELEASE city_construction')
    except Exception:
        conn.execute('ROLLBACK TO city_construction');conn.execute('RELEASE city_construction');raise
    return building_counts(conn,city,faction)
