"""Shared distance rules for city links, independent of screen scale and art."""
import math

MAX_MOVE_DISTANCE = 280


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
