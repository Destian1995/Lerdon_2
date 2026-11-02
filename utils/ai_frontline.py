"""Choose diplomatic threats and legal staging cities without UI dependencies."""
import ast
from dataclasses import dataclass

from utils.movement_rules import reachable_source_cities


@dataclass(frozen=True)
class Frontier:
    faction: str
    city: str
    enemy_city: str
    direct_border: bool


def choose_frontier(conn, faction, relations, strengths, target=None):
    cities = {}
    for cid, name, owner, raw in conn.execute('SELECT id,name,faction,coordinates FROM cities'):
        try:
            x, y = ast.literal_eval(raw)
            cities[cid] = (name, owner, float(x), float(y))
        except (ValueError, TypeError, SyntaxError):
            continue
    owned = {cid: city for cid, city in cities.items() if city[1] == faction}
    if not owned:
        return None
    allies = set()
    for a, b in conn.execute("SELECT faction1,faction2 FROM diplomacies WHERE relationship='союз'"):
        if a == faction:
            allies.add(b)
        elif b == faction:
            allies.add(a)
    living = {c[1] for c in cities.values()} - {faction, 'Нейтрал', None, ''} - allies
    if target is None:
        candidates = []
        for other, relation in relations.items():
            if other not in living:
                continue
            try:
                candidates.append((float(relation), strengths.get(other, 0), other))
            except (ValueError, TypeError):
                continue
        if not candidates:
            return None
        target = min(candidates)[2]
    if target not in living:
        return None
    roads = {tuple(sorted((a, b))) for a, b in conn.execute('SELECT city1,city2 FROM roads')}
    # Prefer a real shared road, then the shortest distance to that border.
    pairs = [(tuple(sorted((a, b))) not in roads,
              abs(own[2] - enemy[2]) + abs(own[3] - enemy[3]), own[0], enemy[0])
             for a, own in owned.items() for b, enemy in cities.items() if enemy[1] == target]
    remote, distance, own, enemy = min(pairs)
    return Frontier(target, own, enemy, not remote)


def rally_frontier(controller, target=None):
    conn, faction = controller.db_connection, controller.faction
    plan = choose_frontier(conn, faction, controller.load_relations(),
                           controller.calculate_army_strength(), target)
    if plan is None:
        return None
    reachable = reachable_source_cities(conn, plan.city, faction)
    # Only own territory supplies the staging army; allied garrisons stay put.
    units = conn.execute('''SELECT g.city_name,g.unit_name,g.unit_count,g.unit_image
        FROM garrisons g JOIN units u ON u.unit_name=g.unit_name
        JOIN cities c ON c.name=g.city_name
        WHERE u.faction=? AND c.faction=? AND g.unit_count>0
          AND CAST(u.unit_class AS INTEGER) IN (1,2,3)''', (faction, faction)).fetchall()
    for city, name, count, image in units:
        if city in reachable:
            controller.relocate_units(city, plan.city, name, count, image)
    controller._frontier_plan = plan
    return plan


def prepare_border_war(controller, target):
    """Spend at least one turn staging before declaring a new war."""
    plan = rally_frontier(controller, target)
    if plan is None or not plan.direct_border:
        return False
    key = (target, plan.city)
    previous = getattr(controller, '_war_preparation', None)
    if previous is None or previous[:2] != key:
        controller._war_preparation = (*key, controller.turn)
        return False
    if previous[2] >= controller.turn:
        return False
    row = controller.db_connection.execute('''SELECT COALESCE(SUM(g.unit_count),0)
        FROM garrisons g JOIN units u ON u.unit_name=g.unit_name
        WHERE g.city_name=? AND u.faction=? AND CAST(u.unit_class AS INTEGER)=1''',
                                            (plan.city, controller.faction)).fetchone()
    return row[0] > 0
