"""Free undead infrastructure and paid recruitment alongside invasion waves."""
STARTING_RESOURCES={'Кроны':1000,'Рабочие':0,'Кристаллы':500,'Население':200,
                    'Текущее потребление':0,'Лимит армии':0}


def initialize_resources(conn):
    """Seed missing undead balances once, preserving existing campaign funds."""
    for kind,amount in STARTING_RESOURCES.items():
        if not conn.execute("SELECT 1 FROM resources WHERE faction='Нежить' AND resource_type=?",(kind,)).fetchone():
            conn.execute("INSERT INTO resources(faction,resource_type,amount) VALUES('Нежить',?,?)",(kind,amount))


def restore_undead_buildings(conn):
    """Restore every owned town at the start of its turn, without spending funds.

    Never call this from a battle or a town preview: damage must persist until
    the next undead turn, and captured towns follow their new owner's rules.
    Caller owns the transaction.
    """
    from city_construction import CATALOG,ensure_unique_buildings
    from city_war import ensure_city_war_schema,current_turn
    ensure_unique_buildings(conn)
    for building in CATALOG:
        conn.execute('''INSERT INTO buildings(city_name,faction,building_type,count)
            SELECT name,faction,?,1 FROM cities WHERE faction='Нежить'
            ON CONFLICT(city_name,building_type) DO UPDATE SET count=1,faction=excluded.faction''',
            (building,))
    ensure_city_war_schema(conn)
    conn.execute('''UPDATE city_war_state SET ruined=0,smoke_until=-1,
        ready_turn=NULL,revision=revision+1,event_kind='rebuild',event_turn=?,owner='Нежить'
        WHERE (ruined<>0 OR smoke_until>=0) AND city_name IN
        (SELECT name FROM cities WHERE faction='Нежить')''',(current_turn(conn),))


def make_turn(ai):
    from city_development import refresh_ai_buildings
    from undead_invasion import _declare_war_to_all
    conn=ai.db_connection
    with conn:
        initialize_resources(conn)
        _declare_war_to_all(ai.cursor)
        restore_undead_buildings(conn)
    ai.hero_used_in_turn=False;ai._action_taken_this_turn=False
    refresh_ai_buildings(ai)
    ai.army=ai.load_army();ai.garrison=ai.load_garrison()
    ai.calculate_current_consumption()
    # Invasion waves grow outside normal hiring. Reserve the ordinary city
    # capacity for paid recruitment, so a large wave cannot disable it forever.
    ai.army_limit=ai.total_consumption+ai.calculate_army_limit()
    ai.update_resources()
    ai.sell_resources()
    ai.save_resources_to_db()
    ai.army_limit=ai.total_consumption+ai.calculate_army_limit()
    # save_garrison expects only the newly hired stacks, not existing troops.
    ai.garrison={}
    ai.hire_army()
    ai.save_resources_to_db()
    ai._undead_attack_nearest_cities()
    refresh_ai_buildings(ai)
    ai.garrison=ai.load_garrison()
