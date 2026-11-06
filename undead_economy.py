"""Civil development and paid recruitment in addition to invasion waves."""
STARTING_RESOURCES={'Кроны':1000,'Рабочие':0,'Кристаллы':500,'Население':200,
                    'Текущее потребление':0,'Лимит армии':0}


def initialize_resources(conn):
    """Seed missing undead balances once, preserving existing campaign funds."""
    for kind,amount in STARTING_RESOURCES.items():
        if not conn.execute("SELECT 1 FROM resources WHERE faction='Нежить' AND resource_type=?",(kind,)).fetchone():
            conn.execute("INSERT INTO resources(faction,resource_type,amount) VALUES('Нежить',?,?)",(kind,amount))


def next_building_cost(ai):
    from city_construction import CATALOG,building_counts
    costs=[]
    for city, in ai.db_connection.execute('SELECT name FROM cities WHERE faction=?',(ai.faction,)).fetchall():
        counts=building_counts(ai.db_connection,city,ai.faction)
        costs.extend(info['cost'] for name,info in CATALOG.items() if not counts.get(name,0))
    return min(costs,default=0)


def make_turn(ai):
    from city_development import develop_military_cities,refresh_ai_buildings
    from undead_invasion import _declare_war_to_all
    conn=ai.db_connection
    with conn:
        initialize_resources(conn)
        _declare_war_to_all(ai.cursor)
    ai.hero_used_in_turn=False;ai._action_taken_this_turn=False
    develop_military_cities(ai)
    savings=max(0,ai.resources.get('Кроны',0))
    ai.army=ai.load_army();ai.garrison=ai.load_garrison()
    ai.calculate_current_consumption()
    # Invasion waves grow outside normal hiring. Reserve the ordinary city
    # capacity for paid recruitment, so a large wave cannot disable it forever.
    ai.army_limit=ai.total_consumption+ai.calculate_army_limit()
    ai.update_resources()
    ai.sell_resources()
    # Spend newly earned money on infrastructure before recruitment consumes it.
    cash=max(0,ai.resources.get('Кроны',0))
    savings=min(cash,savings+max(0,cash-savings)//2)
    ai.save_resources_to_db()
    develop_military_cities(ai)
    spent=max(0,cash-ai.resources.get('Кроны',0))
    reserve=min(max(0,savings-spent),next_building_cost(ai),max(0,ai.resources.get('Кроны',0)))
    ai.army_limit=ai.total_consumption+ai.calculate_army_limit()
    # save_garrison expects only the newly hired stacks, not existing troops.
    ai.garrison={}
    # Keep accumulated capital plus half the new income for the next upgrade.
    # Other new income remains available for independent paid recruitment.
    ai.resources['Кроны']-=reserve
    try:
        ai.hire_army()
    finally:
        ai.resources['Кроны']+=reserve
        ai.save_resources_to_db()
    ai._undead_attack_nearest_cities()
    refresh_ai_buildings(ai)
    ai.garrison=ai.load_garrison()
