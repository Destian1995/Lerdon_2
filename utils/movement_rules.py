"""Shared distance rules for city links, independent of screen scale and art."""
import math
from collections import defaultdict, deque

MAX_MOVE_DISTANCE = 280


def reachable_source_cities(conn, destination, faction):
    """Sources allowed by ordinary movement, also used by the troop picker.

    Own-to-own movement may follow a chain of owned cities. Any movement to
    another faction, or from an allied garrison, requires a direct road.
    """
    cities = {cid: (name, owner) for cid, name, owner in conn.execute('SELECT id,name,faction FROM cities')}
    target_id = next((cid for cid, (name, _) in cities.items() if name == destination), None)
    if target_id is None:
        return set()
    friendly = {faction}
    for first, second in conn.execute("SELECT faction1,faction2 FROM diplomacies WHERE relationship='союз'"):
        if first == faction:
            friendly.add(second)
        elif second == faction:
            friendly.add(first)
    adjacent = defaultdict(set)
    for first, second in conn.execute('SELECT city1,city2 FROM roads'):
        if first != second and first in cities and second in cities:
            adjacent[first].add(second)
            adjacent[second].add(first)
    sources = {cid for cid in adjacent[target_id] if cities[cid][1] in friendly}
    if cities[target_id][1] == faction:
        visited, queue = {target_id}, deque([target_id])
        while queue:
            current = queue.popleft()
            for neighbor in adjacent[current]:
                if neighbor not in visited and cities[neighbor][1] == faction:
                    visited.add(neighbor)
                    queue.append(neighbor)
                    sources.add(neighbor)
    return {cities[cid][0] for cid in sources if cid != target_id}


def can_move_between_cities(conn, source, destination, faction):
    return source in reachable_source_cities(conn, destination, faction)


def city_distance(first, second):
    return abs(first[0] - second[0]) + abs(first[1] - second[1])


def cities_in_range(first, second, limit=MAX_MOVE_DISTANCE):
    distance = city_distance(first, second)
    return math.isfinite(distance) and 0 < distance <= limit + 1e-7


def route_length(points):
    return sum(math.dist(a, b) for a, b in zip(points, points[1:]))


def route_in_range(points, scale=1, limit=MAX_MOVE_DISTANCE):
    """Rendered detours are measured back in world units, never screen pixels."""
    if scale <= 0 or len(points) < 2:
        return False
    length = route_length(points) / scale
    return math.isfinite(length) and 0 < length <= limit + 1e-7


def filter_city_links(cities, roads, scale=1, limit=MAX_MOVE_DISTANCE):
    """Validate existing links; do not invent connections to close a visual loop."""
    if scale <= 0:
        raise ValueError('Map scale must be positive')
    accepted = set()
    for a, b in roads:
        if a == b or a not in cities or b not in cities:
            continue
        if limit is None or cities_in_range(cities[a], cities[b], limit * scale):
            accepted.add(tuple(sorted((a, b))))
    return sorted(accepted)
