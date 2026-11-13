"""Economic investment and supply budgets for the strategic AI.

Uses ordinary purchases and market quotes; never grants money or buildings.
"""
import math

from city_construction import CATALOG, AI_FACTORY_YIELD, HOSPITAL_GROWTH, building_counts

TAX_BASE={'Север':.12,'Эльфы':.08,'Вампиры':.06,'Адепты':.04,'Элины':.03}


def tax_policy(ai):
    """Grow the tax base first, then collect without tax-driven population loss."""
    population=ai.resources.get('Население',0)
    per_person={'Север':.3,'Эльфы':.15,'Вампиры':.08,'Адепты':.02,'Элины':.005}.get(ai.faction,0)
    # Finance supply before the tax-free population boom outruns production.
    future_population=population*1.57+getattr(ai,'hospitals',0)*HOSPITAL_GROWTH
    food=per_person*future_population
    production=getattr(ai,'factories',0)*AI_FACTORY_YIELD
    needs_income=population>=1000 and food+getattr(ai,'total_consumption',0)>production
    return 0 if population<50000 and getattr(ai,'turn',0)<12 and not needs_income else 34


def supply_reserve(ai):
    # food_info is production AFTER population food. Incoming production is
    # usable supply; buying two gross bills every turn bankrupted the AI.
    income=max(0,getattr(ai,'food_info',0))
    system=ai.load_political_system() if hasattr(ai,'load_political_system') else 'Смирение'
    if system=='Борьба':income*=6.5
    deficit=max(0,getattr(ai,'total_consumption',0)-income)
    # Negative population-food balance is not represented by clamped food_info.
    production=getattr(ai,'factories',0)*AI_FACTORY_YIELD
    if income<=0 and production<getattr(ai,'food_peoples',0):
        deficit+=getattr(ai,'food_peoples',0)-production
    return max(100,math.ceil(deficit*1.25))


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
    target=CATALOG[plan[0][2]]['cost'] if plan else 1500
    if hasattr(ai,'has_hero_of_class'):
        if not ai.has_hero_of_class('3'):
            heroes=[data for data in ai.army.values() if str(data['stats']['Класс'])=='3']
            if heroes:target=max(target,max(data['cost']['money'] for data in heroes))
        elif needs_equipment(ai):target=max(target,100000)
        elif getattr(ai,'total_consumption',0)<getattr(ai,'army_limit',0):target=max(target,100000)
    return target


def needs_equipment(ai):
    soldiers=sum(u.get('unit_count',0) for units in getattr(ai,'garrison',{}).values() for u in units
                 if str(ai.army.get(u.get('unit_name'),{}).get('stats',{}).get('Класс'))=='1')
    if soldiers<1000:return False
    rows=ai.db_connection.execute('''SELECT COUNT(*),COUNT(artifact_id) FROM ai_hero_equipment
        WHERE faction_name=?''',(ai.faction,)).fetchone()
    # Fund the first force multiplier, then resume mustering. Saving for all
    # five slots before recruiting would create another army-growth blockade.
    return bool(rows and rows[0] and not rows[1])


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
            plan=[p for p in plan if (p[2]!='Рынок' or available>10000)
                  and (p[2] in ('Фабрика','Больница','Рынок') or getattr(ai,'turn',0)>=8)]
            basics=[p for p in plan if p[2] in ('Фабрика','Больница')]
            if basics:plan=basics
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
    """Recruit heroes and soldiers using the real army cap, never a food quota."""
    if ai.faction in ('Нежить', 'Мятежники'):
        return ai._orig_hire_army()
    ai.update_buildings_for_current_cities()
    ai.calculate_current_consumption()
    city=ai._find_hero_city() or next(iter(ai.buildings),None)
    if not city:return
    pending={city:[]}
    available=max(0,ai.army_limit-ai.total_consumption)
    for rank in ('3','2','4'):
        if rank=='4' and ai.turn<14:continue
        if ai.has_hero_of_class(rank):continue
        choices=[(name,data) for name,data in ai.army.items()
                 if str(data['stats']['Класс'])==rank and not ai.is_unit_already_hired(name)]
        critical=getattr(ai,'_situation',{}).get('threat_level')=='critical'
        primary='Защита' if critical and len(ai.cities)<2 else 'Атака'
        choices.sort(key=lambda item:-(item[1]['stats'][primary]))
        # Save for the selected champion rather than permanently locking
        # the faction into a cheaper defensive hero while waiting for cash.
        choices=choices[:1]
        for name,data in choices:
            money,workers=data['cost']['money'],data['cost']['time']
            upkeep=data['consumption']
            if money>ai.resources.get('Кроны',0) or workers>ai.resources.get('Рабочие',0) or upkeep>available:continue
            ai.resources['Кроны']-=money;ai.resources['Рабочие']-=workers;available-=upkeep
            pending[city].append(dict(unit_name=name,unit_count=1))
            if rank=='3':ai.create_empty_equipment_slots_for_ai_hero(name)
            break
    if pending[city]:
        ai.garrison=pending;ai.save_garrison();ai.garrison=ai.load_garrison()
        ai.calculate_current_consumption()
    # Equipment is an army multiplier. Buy it before soldiers spend its budget.
    ai.generate_and_buy_artifacts_for_ai_hero()
    pending={city:[]}
    savings=100000 if needs_equipment(ai) else 0
    # A new town must not stay empty forever because every small daily income
    # is spent on soldiers before it reaches the price of a hospital/factory.
    basics=[p for p in investment_plan(ai) if p[2] in ('Фабрика','Больница')]
    has_soldiers=any(str(ai.army.get(u.get('unit_name'),{}).get('stats',{}).get('Класс'))=='1'
                     for units in ai.garrison.values() for u in units)
    if basics and has_soldiers:savings=max(savings,CATALOG[basics[0][2]]['cost'])
    ai.hire_units(pending,int(max(0,ai.resources.get('Кроны',0)-savings)*.8),
                  int(max(0,ai.resources.get('Рабочие',0))*.8),
                  max(0,ai.army_limit-ai.total_consumption))
    if pending[city]:
        ai.garrison=pending;ai.save_garrison();ai.garrison=ai.load_garrison()
        ai.calculate_current_consumption()
