"""Economic investment and supply budgets for the strategic AI.

Uses ordinary purchases and market quotes; never grants money or buildings.
"""
import math

from city_construction import CATALOG, AI_FACTORY_YIELD, HOSPITAL_GROWTH, building_counts


def supply_reserve(ai):
    return max(100, math.ceil(2 * (max(0, getattr(ai, 'total_consumption', 0))
                                 + max(0, getattr(ai, 'food_peoples', 0)))))


def investment_plan(ai):
    """Rank marginal returns, recalculated after each completed purchase."""
    from utils.market_income import market_policy
    from utils.crystal_trade import ai_sell_price
    conn = ai.db_connection
    cities = [r[0] for r in conn.execute('SELECT name FROM cities WHERE faction=? ORDER BY name', (ai.faction,))]
    counts = {city: building_counts(conn, city, ai.faction) for city in cities}
    totals = {kind: sum(c.get(kind, 0) for c in counts.values()) for kind in CATALOG}
    resource, percent = market_policy(conn, ai.faction)
    price = ai_sell_price(ai) if getattr(ai, 'raw_material_price', 0) > 0 else 1
    population = max(0, ai.resources.get('Население', 0))
    food = max(0, getattr(ai, 'food_peoples', 0))
    army = max(0, getattr(ai, 'total_consumption', 0))
    production = totals['Фабрика'] * AI_FACTORY_YIELD
    if resource == 'Кристаллы': production *= 1 + totals['Рынок'] * percent / 100
    shortage = production < food + army
    at_war = bool(ai.get_factions_at_war())
    plan = []
    for city, buildings in counts.items():
        for kind in CATALOG:
            if buildings.get(kind): continue
            if kind == 'Фабрика':
                gain = AI_FACTORY_YIELD * price * (1 + (totals['Рынок'] * percent / 100 if resource == 'Кристаллы' else 0))
                if shortage: gain *= 4
            elif kind == 'Больница':
                # Three turns of new taxpayers, plus workers for future recruits.
                gain = HOSPITAL_GROWTH * (.34 * 3 + .20)
                if not buildings.get('Фабрика') and shortage: gain *= .15
            elif kind == 'Рынок':
                gain = ((production / max(1, 1 + totals['Рынок'] * percent / 100) * price)
                        if resource == 'Кристаллы' else max(0, getattr(ai, 'taxes_info', population * .34))) * percent / 100
            elif kind == 'Кузница':
                stationed = sum(max(0, u.get('unit_count', 0)) *
                                max(0, ai.army.get(u.get('unit_name'), {}).get('consumption', 0))
                                for u in getattr(ai, 'garrison', {}).get(city, []))
                gain = stationed * .05 * price
            elif kind == 'Цитадель':
                crowded = army >= max(1, getattr(ai, 'army_limit', 1)) * .85
                gain = 800 if crowded else 15
            else:
                gain = 500 if at_war and getattr(ai, 'garrison', {}).get(city) else 10
            plan.append((gain / CATALOG[kind]['cost'], city, kind))
    return sorted(plan, key=lambda item: (-item[0], item[1], item[2]))


def cash_target(ai):
    plan = investment_plan(ai)
    return CATALOG[plan[0][2]]['cost'] if plan else 1500


def develop(ai, kinds=None, limit=None):
    from city_construction import buy_building, construction_allowed
    from city_development import refresh_ai_buildings
    ai.save_resources_to_db()
    built = []
    with ai.db_connection:
        while limit is None or len(built) < limit:
            balance = ai.db_connection.execute("SELECT amount FROM resources WHERE faction=? AND resource_type='Кроны'", (ai.faction,)).fetchone()
            available = balance[0] if balance else 0
            plan = [p for p in investment_plan(ai) if (not kinds or p[2] in kinds)
                    and CATALOG[p[2]]['cost'] <= available
                    and construction_allowed(ai.db_connection, p[1], ai.faction)]
            if not plan: break
            _, city, kind = plan[0]
            buy_building(ai.db_connection, city, ai.faction, kind)
            built.append((city, kind))
    refresh_ai_buildings(ai)
    return built


def secure_supply(ai):
    """Buy two turns of supplies when production cannot feed the population."""
    from utils.crystal_trade import crystal_quotes, trade_efficiency
    shortage = max(0, supply_reserve(ai) - ai.resources.get('Кристаллы', 0))
    if shortage <= 0 or getattr(ai, 'raw_material_price', 0) <= 0: return 0
    buy, _ = crystal_quotes(ai.raw_material_price, trade_efficiency(ai.faction))
    price = buy / 100
    quantity = min(math.ceil(shortage), int(ai.resources.get('Кроны', 0) / price))
    if quantity:
        ai.resources['Кроны'] -= round(quantity * price, 2)
        ai.resources['Кристаллы'] += quantity
    return quantity


def hire_with_budget(ai):
    """Protect investments from *all* recruitment paths, including special heroes."""
    if ai.faction in ('Нежить', 'Мятежники'):
        return ai._orig_hire_army()
    at_war = bool(ai.get_factions_at_war())
    early = getattr(ai, 'turn', 0) < 8 and not at_war
    money = max(0, ai.resources.get('Кроны', 0))
    reserve = min(money * (.6 if early else .15), cash_target(ai))
    old_limit = ai.army_limit
    # Income after population food, plus expendable stock above the safety buffer.
    extra = max(0, ai.resources.get('Кристаллы', 0) - supply_reserve(ai)) / 3
    affordable_upkeep = max(0, getattr(ai, 'food_info', 0)) + extra
    ai.army_limit = min(old_limit, max(getattr(ai, 'total_consumption', 0), affordable_upkeep))
    ai.resources['Кроны'] -= reserve
    try:
        return ai._orig_hire_army()
    finally:
        ai.resources['Кроны'] += reserve
        ai.army_limit = old_limit
