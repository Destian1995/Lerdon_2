"""Rebel treasury, legal offensive routes and the complete rebel turn."""
from collections import deque
import sqlite3

FACTION = 'Мятежники'


def initialize_resources(conn, new_uprising=False):
    """Seed a new uprising once; controller recreation never refills its purse."""
    defaults = {'Кроны': 1000, 'Рабочие': 0, 'Кристаллы': 0,
                'Население': 100, 'Текущее потребление': 0, 'Лимит армии': 0}
    for kind, amount in defaults.items():
        row = conn.execute('SELECT 1 FROM resources WHERE faction=? AND resource_type=?',
                           (FACTION, kind)).fetchone()
        if row and new_uprising:
            conn.execute('UPDATE resources SET amount=? WHERE faction=? AND resource_type=?',
                         (amount, FACTION, kind))
        elif not row:
            conn.execute('INSERT INTO resources(faction,resource_type,amount) VALUES(?,?,?)',
                         (FACTION, kind, amount))


def offensive_route(conn, target, enemy):
    """Plan road conquests through our towns, neutrals and the ordered enemy."""
    towns = list(conn.execute('SELECT id,name,faction FROM cities ORDER BY id'))
    owners = {r[1]: r[2] for r in towns}
    if owners.get(target) != enemy:
        return []
    names = {r[0]: r[1] for r in towns}
    graph = {name: [] for name in owners}
    for a, b in conn.execute('SELECT city1,city2 FROM roads'):
        a, b = names.get(a), names.get(b)
        if a and b:
            graph[a].append(b)
            graph[b].append(a)
    queue = deque([name] for name in owners if owners[name] == FACTION)
    visited = {path[0] for path in queue}
    while queue:
        path = queue.popleft()
        if path[-1] == target:
            return path
        for neighbor in graph[path[-1]]:
            if neighbor not in visited and owners[neighbor] in (FACTION, enemy, 'Нейтрал'):
                visited.add(neighbor)
                queue.append(path + [neighbor])
    return []


def declare_war(conn, enemy):
    if not enemy or enemy == FACTION:
        return
    conn.execute("UPDATE diplomacies SET relationship='война' WHERE "
                 '(faction1=? AND faction2=?) OR (faction1=? AND faction2=?)',
                 (FACTION, enemy, enemy, FACTION))
    if not conn.execute('SELECT 1 FROM diplomacies WHERE faction1=? AND faction2=?',
                        (FACTION, enemy)).fetchone():
        conn.execute('INSERT INTO diplomacies(faction1,faction2,relationship) VALUES(?,?,?)',
                     (FACTION, enemy, 'война'))


def attack(ai):
    conn = ai.db_connection
    try:
        order = conn.execute('SELECT target_city,target_faction FROM rebel_attack_order WHERE id=1').fetchone()
    except sqlite3.OperationalError:
        order = None
    if order:
        target, enemy = order
        declare_war(conn, enemy)
        conn.commit()
        owner = conn.execute('SELECT faction FROM cities WHERE name=?', (target,)).fetchone()
        if owner and owner[0] == FACTION:
            conn.execute('DELETE FROM rebel_attack_order WHERE id=1')
            conn.commit()
        else:
            route = offensive_route(conn, target, enemy)
            if route:
                # A distant order is fulfilled by capturing its enemy approaches.
                frontier = next(name for name in route if conn.execute(
                    'SELECT faction FROM cities WHERE name=?', (name,)).fetchone()[0] != FACTION)
                owner = conn.execute('SELECT faction FROM cities WHERE name=?', (frontier,)).fetchone()[0]
                ai.attack_city(frontier, owner)
                if conn.execute('SELECT faction FROM cities WHERE name=?', (target,)).fetchone() == (FACTION,):
                    conn.execute('DELETE FROM rebel_attack_order WHERE id=1')
                    conn.commit()
                return
            # Keep an unreachable order for retry, but fight on other legal fronts.
    candidates = []
    for enemy in ai.get_factions_at_war():
        for (target,) in conn.execute('SELECT name FROM cities WHERE faction=? ORDER BY id', (enemy,)):
            route = offensive_route(conn, target, enemy)
            if route:
                candidates.append((len(route), target, enemy, route))
    if candidates:
        _, _, enemy, route = min(candidates)
        frontier = next(name for name in route if conn.execute(
            'SELECT faction FROM cities WHERE name=?', (name,)).fetchone()[0] != FACTION)
        owner = conn.execute('SELECT faction FROM cities WHERE name=?', (frontier,)).fetchone()[0]
        ai.attack_city(frontier, owner)


def make_turn(ai):
    from city_development import develop_military_cities, refresh_ai_buildings
    ai.hero_used_in_turn = False
    ai._action_taken_this_turn = False
    initialize_resources(ai.db_connection)
    ai.db_connection.commit()
    develop_military_cities(ai)
    ai.army = ai.load_army()
    ai.garrison = ai.load_garrison()
    ai.army_limit = ai.calculate_army_limit()
    ai.calculate_current_consumption()
    ai.update_resources()
    ai.sell_resources()
    # save_garrison adds recruitment deltas; passing the full existing army
    # would duplicate troops in every other town when one town recruits.
    ai.garrison = {}
    ai.hire_army()
    ai.save_resources_to_db()
    ai.attack_enemy_cities()
    # Captures and losses must not be overwritten by the old city snapshot.
    refresh_ai_buildings(ai)
    ai.garrison = ai.load_garrison()
