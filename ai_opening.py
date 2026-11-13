"""Invest, muster and expand in the same turn, using normal movement rules."""


def development_cycle(ai):
    from ai_strategy import emergency_sell_crystals,ensure_scout_unit,early_expansion,rally_units_to_frontier
    from city_development import refresh_ai_buildings
    # Foundations before the army; every captured town repeats this investment.
    ai.manage_buildings()
    emergency_sell_crystals(ai);ai.sell_resources()
    ai.manage_buildings()
    ai.hire_army();ensure_scout_unit(ai)
    ai.save_resources_to_db()
    from alliance_rules import allies
    player=getattr(ai,'player_faction',None)
    defending_player=ai.faction in allies(ai.db_connection,player) and bool(ai.get_factions_at_war())
    if defending_player:
        # Help the ally before spending this turn's movement on neutral towns.
        rally_units_to_frontier(ai)
        ai.check_and_declare_war()
    for _ in range(2 if ai.faction=='Элины' else 1):
        if defending_player and ai._action_taken_this_turn:
            break
        ai._action_taken_this_turn=False
        early_expansion(ai)
        refresh_ai_buildings(ai)
        ai.army_limit=ai.calculate_army_limit()
        ai.manage_buildings()
    # If peaceful expansion spent the action, ordinary attacks observe its flag.
    if ai.get_factions_at_war() and not defending_player:
        rally_units_to_frontier(ai)
        ai.check_and_declare_war()
    elif not defending_player and not ai._action_taken_this_turn and ai.turn>=8:
        ai.check_and_declare_war()
    ai.sell_resources()
