"""Shared faction balance and read-only summaries of the effects used by the game."""
import json
import sqlite3
from collections import defaultdict

NORTH_MULTIPLIER = 1.80
ADEPT_MULTIPLIER = 1.55
VAMPIRE_RATE = .15
ELF_RATE = .60
PEAK_SEASONS = {'Север': 0, 'Вампиры': 1, 'Эльфы': 2, 'Адепты': 3, 'Элины': 2, 'Нежить': 0}
FACTION_ABILITIES = {
    'Север': f'[b]Шквал[/b] — если бонусы увеличили урон в 20+ раз, +{(NORTH_MULTIPLIER - 1) * 100:.0f}% к урону',
    'Эльфы': f'[b]Природное исцеление[/b] — {ELF_RATE * 100:g}% погибших возвращаются в строй после победы, летом — 100%',
    'Вампиры': f'[b]Вампиризм[/b] — {VAMPIRE_RATE * 100:g}% убитых врагов воскресают как ваши юниты',
    'Адепты': f'[b]Оплот[/b] — если бонусы увеличили защиту в 20+ раз, +{(ADEPT_MULTIPLIER - 1) * 100:.0f}% к защите',
    'Элины': '[b]Торговая империя[/b] — 2 перемещения/атаки за ход, +35% кристаллы, +25% торговля',
}


def season_multiplier(faction, season):
    return 2.75 if PEAK_SEASONS.get(faction) == season else 1.0


def combat_multiplier(faction, conn):
    try:
        row = conn.execute('SELECT season_index FROM season LIMIT 1').fetchone()
        season = row[0] if row else -1
    except (sqlite3.Error, AttributeError):
        season = -1
    base = {'Север': NORTH_MULTIPLIER, 'Адепты': ADEPT_MULTIPLIER}.get(faction, 1)
    return base * season_multiplier(faction, season)


def combat_bonus_status(faction, attack, defense, durability, hero_bonus=(0, 0, 0)):
    """Use battle_chain's threshold before experience, morale and other effects."""
    if faction == 'Север':
        base, extra, name = attack, hero_bonus[0], 'Шквал'
    elif faction == 'Адепты':
        base = max(defense + durability / 2.0, 1)
        extra, name = hero_bonus[1] + hero_bonus[2] / 2.0, 'Оплот'
    else:
        return '', False, 0, 0
    boosted = base + extra
    return name, base > 0 and boosted / base >= 20, base, boosted


def battle_spirit_multiplier(conn,faction):
    """The same recent counter-pick victories checked by battle_chain."""
    counters={'Адепты':('Элины','Север'),'Элины':('Север','Эльфы'),
              'Вампиры':('Адепты','Элины'),'Север':('Вампиры','Эльфы'),
              'Эльфы':('Адепты','Вампиры')}.get(faction)
    if not counters:
        return 1.0
    try:
        from city_war import current_turn
        wins=conn.execute('''SELECT COUNT(*) FROM faction_victories
            WHERE faction=? AND defeated IN (?,?) AND turn>?''',
            (faction,*counters,current_turn(conn)-4)).fetchone()[0]
        return 1.15 if wins>=2 else 1.0
    except sqlite3.OperationalError:
        return 1.0


def garrison_bonus_status(conn, faction):
    """Count eligible troop stacks using the heroes currently in each city."""
    cities = defaultdict(list)
    for city, unit_class, attack, defense, durability in conn.execute('''
            SELECT g.city_name,u.unit_class,u.attack,u.defense,u.durability
            FROM garrisons g JOIN units u ON u.unit_name=g.unit_name
            WHERE u.faction=? AND g.unit_count>0''', (faction,)):
        cities[city].append((str(unit_class), attack or 0, defense or 0, durability or 0))
    active, total = 0, 0
    for units in cities.values():
        heroes = tuple(sum(u[i] for u in units if u[0] in ('2', '3')) for i in (1, 2, 3))
        for cls, attack, defense, durability in units:
            if cls == '1':
                total += 1
                active += combat_bonus_status(faction, attack, defense, durability, heroes)[1]
    return active, total


def council_bonuses(conn, faction=None):
    """Match resource, trade and relation formulas, including the greed split."""
    try:
        rows = conn.execute("SELECT loyalty, ideology FROM nobles WHERE status='active'").fetchall()
    except sqlite3.Error:
        rows = []
    return summarize_council(rows, faction)


def summarize_council(rows, faction=None):
    result = dict(crowns=0, crystals=0, trade=0, relations=defaultdict(int), active=0)
    for loyalty, raw in rows:
        if loyalty is None or loyalty < 50:
            continue
        try:
            if isinstance(raw, dict):
                traits = raw
            elif isinstance(raw, str) and raw.startswith('{'):
                traits = json.loads(raw)
            elif isinstance(raw, str) and raw.startswith('Любит '):
                traits = dict(type='race_love', value=raw[6:])
            else:
                traits = dict(type='ideology', value=raw)
            if not isinstance(traits, dict):
                continue
        except (ValueError, TypeError):
            continue
        percent = min(int((loyalty - 50) / 5), 10)
        kind = traits.get('type')
        if kind == 'ideology':
            result['crystals' if traits.get('value') == 'Борьба' else 'crowns'] += percent
            result['active'] += int(percent > 0)
        elif kind == 'greed':
            result['crowns'] += percent // 2
            result['crystals'] += percent // 2
            result['active'] += int(percent // 2 > 0)
        elif kind == 'race_love':
            target = traits.get('value')
            relation = min(int(loyalty - 50), 10)
            if target and target != faction and relation > 0:
                result['relations'][target] += relation
                result['active'] += 1
    result['trade'] = (result['crowns'] + result['crystals']) / 2
    return result


def supplied_cities(conn, faction):
    """Largest connected component of owned cities, as in the economy."""
    try:
        cities = {cid: name for cid, name, owner in conn.execute('SELECT id,name,faction FROM cities')
                  if owner == faction}
        adjacency = defaultdict(list)
        for first, second in conn.execute('SELECT city1,city2 FROM roads'):
            adjacency[first].append(second)
            adjacency[second].append(first)
        visited, components = set(), []
        for start in set(cities):
            if start in visited:
                continue
            component, queue = set(), [start]
            visited.add(start)
            while queue:
                city = queue.pop(0)
                component.add(city)
                for neighbor in adjacency[city]:
                    if neighbor in cities and neighbor not in visited:
                        visited.add(neighbor)
                        queue.append(neighbor)
            components.append(component)
        return {cities[cid] for cid in max(components, key=len, default=set())}
    except sqlite3.Error:
        return {row[0] for row in conn.execute('SELECT name FROM cities WHERE faction=?', (faction,))}


def current_effect_rows(conn, faction, season):
    """Display actual building totals and council effects; local defenses stay local."""
    supplied = supplied_cities(conn, faction)
    totals, all_totals = defaultdict(int), defaultdict(int)
    rows = []
    from monster_sites import progress
    from city_war import current_turn
    training=progress(conn,faction)['veteran_until']-current_turn(conn)
    if training>0:
        rows.append(('Охота на монстров',f'Ещё {training} х.',
                     'Применяется: новобранцы — ветераны; воины и ветераны — элита; элита получает ещё +15%'))
    from utils.city_terrain import read_all as read_city_terrain
    for city,info in read_city_terrain(conn).items():
        owner=conn.execute('SELECT faction FROM cities WHERE name=?',(city,)).fetchone()
        if not owner or owner[0] != faction:
            continue
        if info.landform == 'highland':
            rows.append((f'Горы · {city}','','+30% к боевой защите всего гарнизона этого города'))
        elif info.landform == 'lowland':
            rows.append((f'Низина · {city}','','−20% к боевой защите всего гарнизона этого города'))
        economic=[]
        if info.landform == 'lowland':
            economic.append('+15% к доле города в доходе крон')
        if info.waterside:
            economic.append('+20% к выработке кристаллов фабрик города')
        if economic:
            effect='; '.join(economic) if city in supplied else 'Без снабжения: экономические бонусы рельефа не действуют'
            rows.append((f'Рельеф · {city}','',effect))
    for city, kind, count in conn.execute(
            'SELECT city_name,building_type,count FROM buildings WHERE faction=?', (faction,)):
        if kind == 'Вышка':kind = 'Цитадель'
        count = count or 0
        all_totals[kind] += count
        if city in supplied:
            totals[kind] += count
    population_mult, factory_mult = {0: (1.2, .85), 1: (1.3, 1.1), 2: (1.1, 1.25),
                                     3: (1.15, 1.2)}.get(season, (1, 1))
    if totals['Больница']:
        from city_construction import HOSPITAL_GROWTH
        rows.append(('Больницы', totals['Больница'],
                     f"+{int(totals['Больница'] * HOSPITAL_GROWTH * population_mult)} населения и рабочих/ход до налогов (сезон учтён)"))
    if totals['Фабрика']:
        from city_construction import FACTORY_YIELD
        rows.append(('Фабрики', totals['Фабрика'],
                     f"{totals['Фабрика'] * FACTORY_YIELD * factory_mult:g} кристаллов/ход до потребления; −{totals['Фабрика'] * 20} рабочих/ход"))
    if totals['Рынок']:
        rows.append(('Рынки', totals['Рынок'], f"+{totals['Рынок'] * 10}% доход крон; +{totals['Рынок'] * 10}% к множителю торговли"))
    if totals['Цитадель']:
        rows.append(('Цитадели', totals['Цитадель'], f"+{totals['Цитадель'] * 500} к лимиту армии"))
    for city, walls, smithies in conn.execute('''
            SELECT city_name,
                   SUM(CASE WHEN building_type='Стена' THEN count ELSE 0 END),
                   SUM(CASE WHEN building_type='Кузница' THEN count ELSE 0 END)
            FROM buildings WHERE faction=? GROUP BY city_name''', (faction,)):
        if walls:
            rows.append((f'Стены · {city}', walls, f'+{walls * 15}% защиты гарнизона этого города'))
        if smithies:
            rows.append((f'Кузницы · {city}', smithies, '−5% потребление кристаллов гарнизоном этого города'))
    for kind in ('Больница', 'Фабрика', 'Рынок', 'Цитадель'):
        cut_off = all_totals[kind] - totals[kind]
        if cut_off:
            rows.append((f'{kind} · без снабжения', cut_off, 'Экономический эффект не действует'))
    council = council_bonuses(conn, faction)
    rows.append(('Советники с действующим бонусом', council['active'],
                 f"+{council['crowns']}% доход крон; +{council['crystals']}% добыча кристаллов; +{council['trade']:g}% к множителю торговли"))
    for target, points in sorted(council['relations'].items()):
        rows.append((f'Советники · {target}', '', f'+{points} п. отношений/ход, максимум отношений 100'))
    from otherworld_quests import cap_turns
    left=cap_turns(conn,faction)
    if left:rows.append(('Награда Зазеркалья',f'{left} х.','+35% к лимитам крон, кристаллов, рабочих и населения'))
    return rows
