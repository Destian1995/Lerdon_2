"""Civil development and paid recruitment in addition to invasion waves."""
def make_turn(ai):
    from city_development import develop_military_cities,refresh_ai_buildings
    from undead_invasion import _declare_war_to_all
    conn=ai.db_connection
    # Repair partial resource rows in old saves without refilling balances.
    defaults={'Кроны':5000,'Рабочие':0,'Кристаллы':500,'Население':5000,
              'Текущее потребление':0,'Лимит армии':0}
    with conn:
        for kind,amount in defaults.items():
            if not conn.execute('SELECT 1 FROM resources WHERE faction=? AND resource_type=?',
                                (ai.faction,kind)).fetchone():
                conn.execute('INSERT INTO resources(faction,resource_type,amount) VALUES(?,?,?)',
                             (ai.faction,kind,amount))
        _declare_war_to_all(ai.cursor)
    ai.hero_used_in_turn=False;ai._action_taken_this_turn=False
    develop_military_cities(ai)
    ai.army=ai.load_army();ai.garrison=ai.load_garrison()
    ai.calculate_current_consumption()
    # Invasion waves grow outside normal hiring. Reserve the ordinary city
    # capacity for paid recruitment, so a large wave cannot disable it forever.
    ai.army_limit=ai.total_consumption+ai.calculate_army_limit()
    ai.update_resources()
    ai.sell_resources()
    # save_garrison expects only the newly hired stacks, not existing troops.
    ai.garrison={}
    ai.hire_army();ai.save_resources_to_db()
    ai._undead_attack_nearest_cities()
    refresh_ai_buildings(ai)
    ai.garrison=ai.load_garrison()
