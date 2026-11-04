"""Unique city infrastructure, shared by manual construction, council and AI."""
import sqlite3
from city_construction import CATALOG,building_counts,buy_building,construction_allowed,ensure_unique_buildings


def average_loyalty(conn,faction=None):
    try:
        columns={r[1] for r in conn.execute('PRAGMA table_info(nobles)')}
        extra=' AND faction=?' if 'faction' in columns and faction else ''
        args=(faction,) if extra else ()
        row=conn.execute("SELECT AVG(COALESCE(loyalty,0)) FROM nobles WHERE status='active'"+extra,args).fetchone()
        return max(0,min(100,float(row[0] or 0)))
    except sqlite3.OperationalError:return 0


def auto_develop(conn,faction,require_council=True,kinds=None,limit=None):
    ensure_unique_buildings(conn)
    if require_council and average_loyalty(conn,faction)<=80:return []
    cities=[r[0] for r in conn.execute('SELECT name FROM cities WHERE faction=? ORDER BY name',(faction,))
            if construction_allowed(conn,r[0],faction)]
    built=[]
    for name in kinds or CATALOG:
        if name not in CATALOG:continue
        for city in cities:
            if limit is not None and len(built)>=limit:return built
            if building_counts(conn,city,faction).get(name,0):continue
            balance=conn.execute("SELECT amount FROM resources WHERE faction=? AND resource_type='Кроны'",(faction,)).fetchone()
            if not balance or balance[0]<CATALOG[name]['cost']:continue
            buy_building(conn,city,faction,name);built.append((city,name))
    return built


def refresh_ai_buildings(ai):
    ensure_unique_buildings(ai.db_connection)
    ai.cities=ai.load_cities()
    ai.load_buildings();ai.update_buildings_for_current_cities()
    ai.cities_buildings={city:dict(data['Здания']) for city,data in ai.buildings.items()}
    ai.resources.update(dict(ai.db_connection.execute('SELECT resource_type,amount FROM resources WHERE faction=?',(ai.faction,))))
    ai.load_resources()


def player_build(model,city,kind,quantity=1):
    if quantity<=0:return False
    if building_counts(model.conn,city,model.faction).get(kind,0):return False
    with model.conn:buy_building(model.conn,city,model.faction,kind)
    model.load_buildings()
    from utils.resource_payments import sync_resources
    sync_resources(model.conn,model.faction,model)
    return True


def ai_build(ai,kinds=None,limit=None):
    ai.save_resources_to_db()
    with ai.db_connection:
        built=auto_develop(ai.db_connection,ai.faction,require_council=False,kinds=kinds,limit=limit)
    refresh_ai_buildings(ai)
    return built
