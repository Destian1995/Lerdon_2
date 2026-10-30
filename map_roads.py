"""Deterministic visual road routing. The gameplay graph is never changed."""
import heapq
import math
import random
from dataclasses import dataclass, field
from collections import deque
from utils.movement_rules import MAX_MOVE_DISTANCE, filter_city_links, route_in_range

_surface_texture = None


def segment_hits_rect(a, b, rect):
    """Slab intersection, including endpoints and edges."""
    low, high = 0.0, 1.0
    for start, delta, minimum, maximum in (
        (a[0], b[0] - a[0], rect[0], rect[2]),
        (a[1], b[1] - a[1], rect[1], rect[3]),
    ):
        if abs(delta) < 1e-9:
            if start < minimum or start > maximum:
                return False
        else:
            t1, t2 = (minimum - start) / delta, (maximum - start) / delta
            low, high = max(low, min(t1, t2)), min(high, max(t1, t2))
            if low > high:
                return False
    return True


def _clear(points, obstacles, bounds, terrain=None, mode='land'):
    if any(not (bounds[0] <= x <= bounds[2] and bounds[1] <= y <= bounds[3]) for x, y in points):
        return False
    return (not any(segment_hits_rect(a, b, rect)
                    for a, b in zip(points, points[1:]) for rect in obstacles)
            and (terrain is None or terrain.path_clear(points, mode)))


def _bend(start, end, amount):
    dx, dy = end[0] - start[0], end[1] - start[1]
    length = max(math.hypot(dx, dy), 0.001)
    return [(start[0] + dx * i / 20 - dy / length * math.sin(math.pi * i / 20) * amount,
             start[1] + dy * i / 20 + dx / length * math.sin(math.pi * i / 20) * amount)
            for i in range(21)]


def _grid_route(start, end, obstacles, bounds, step, terrain=None, mode='land'):
    x0, y0, x1, y1 = bounds
    nx, ny = max(1, math.ceil((x1 - x0) / step)), max(1, math.ceil((y1 - y0) / step))
    sx, sy = (x1 - x0) / nx, (y1 - y0) / ny
    def point(node):
        return x0 + node[0] * sx, y0 + node[1] * sy
    def node(p):
        return (min(nx, max(0, round((p[0] - x0) / sx))),
                min(ny, max(0, round((p[1] - y0) / sy))))
    source, target = node(start), node(end)
    occupied = set()
    terrain_costs = {}
    directions = ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1))
    if terrain is not None:
        grid_key = (bounds, step, mode)
        cached = terrain.routing_grids.get(grid_key)
        if cached is None:
            for iy in range(ny + 1):
                for ix in range(nx + 1):
                    cell = (ix, iy)
                    cost = terrain.cost_at(point(cell), mode)
                    terrain_costs[cell] = cost
                    if math.isinf(cost):
                        occupied.add(cell)
            components = {}
            component_id = 0
            if mode == 'land':
                for cell in terrain_costs:
                    if cell in occupied or cell in components:
                        continue
                    component_id += 1
                    queue = deque([cell])
                    components[cell] = component_id
                    while queue:
                        current = queue.popleft()
                        for dx, dy in directions:
                            neighbor = current[0] + dx, current[1] + dy
                            if (neighbor not in terrain_costs or neighbor in occupied
                                    or neighbor in components):
                                continue
                            if dx and dy and ((current[0] + dx, current[1]) in occupied or
                                              (current[0], current[1] + dy) in occupied):
                                continue
                            components[neighbor] = component_id
                            queue.append(neighbor)
            cached = terrain_costs, frozenset(occupied), components
            terrain.routing_grids[grid_key] = cached
        terrain_costs, blocked, components = cached
        occupied = set(blocked)
        if mode == 'land':
            if source in occupied or target in occupied:
                return None
            if components[source] != components[target]:
                return None
    for left, bottom, right, top in obstacles:
        # A little clearance keeps both the road shoulders and rounded bends off labels.
        for ix in range(max(0, math.floor((left - x0) / sx) - 1),
                        min(nx, math.ceil((right - x0) / sx) + 1) + 1):
            for iy in range(max(0, math.floor((bottom - y0) / sy) - 1),
                            min(ny, math.ceil((top - y0) / sy) + 1) + 1):
                occupied.add((ix, iy))
    occupied.difference_update((source, target))
    queue = [(math.dist(source, target), 0.0, source)]
    costs, parents = {source: 0.0}, {}
    while queue:
        _, cost, current = heapq.heappop(queue)
        if cost > costs[current]:
            continue
        if current == target:
            path = [end]
            while current != source:
                path.append(point(current))
                current = parents[current]
            path.extend((point(source), start))
            path.reverse()
            # Visibility simplification removes grid staircases.
            simplified, index = [path[0]], 0
            while index < len(path) - 1:
                last = len(path) - 1
                while last > index + 1 and not _clear([path[index], path[last]], obstacles, bounds, terrain, mode):
                    last -= 1
                simplified.append(path[last])
                index = last
            # Round the corners only if the rounded path still clears obstacles.
            rounded = simplified
            for _ in range(2):
                smooth = [rounded[0]]
                for a, b in zip(rounded, rounded[1:]):
                    smooth.extend(((a[0] * .75 + b[0] * .25, a[1] * .75 + b[1] * .25),
                                   (a[0] * .25 + b[0] * .75, a[1] * .25 + b[1] * .75)))
                smooth.append(rounded[-1])
                if _clear(smooth, obstacles, bounds, terrain, mode):
                    rounded = smooth
            return rounded if _clear(rounded, obstacles, bounds, terrain, mode) else None
        for dx, dy in directions:
            neighbor = current[0] + dx, current[1] + dy
            if not (0 <= neighbor[0] <= nx and 0 <= neighbor[1] <= ny) or neighbor in occupied:
                continue
            if dx and dy and ((current[0] + dx, current[1]) in occupied or
                              (current[0], current[1] + dy) in occupied):
                continue
            new_cost = cost + math.hypot(dx, dy) * terrain_costs.get(neighbor, 1.0)
            if new_cost < costs.get(neighbor, math.inf):
                parents[neighbor], costs[neighbor] = current, new_cost
                heapq.heappush(queue, (new_cost + math.dist(neighbor, target), new_cost, neighbor))
    return None


def build_road_paths(cities, roads, labels, bounds, scale=1, movement_limit=None):
    """Return (city1, city2, points) for the existing, deduplicated road graph.

    cities: {id: (sprite_left, sprite_bottom)} in screen pixels.
    labels: {id: (left, bottom, right, top)}. Routing knows buildings and labels,
    but deliberately makes no claims about traversability of painted terrain.
    """
    result, seen = [], set()
    building_rects = {key: (x - 5, y - 4, x + 82, y + 82) for key, (x, y) in cities.items()}
    for a, b in filter_city_links(cities, roads, scale, movement_limit):
        if a == b or a not in cities or b not in cities or (a, b) in seen:
            continue
        seen.add((a, b))
        start = cities[a][0] + 38.5, cities[a][1] + 30
        end = cities[b][0] + 38.5, cities[b][1] + 30
        obstacles = [rect for key, rect in building_rects.items() if key not in (a, b)]
        obstacles.extend(labels.values())
        hard_obstacles = [rect for key, rect in building_rects.items() if key not in (a, b)]
        def within_budget(candidate):
            return candidate is not None and (movement_limit is None or route_in_range(candidate, scale, movement_limit))
        length = math.dist(start, end)
        # A stable seed prevents the route from jumping after capture or refresh.
        sign = 1 if (a * 31 + b * 17) % 2 else -1
        amount = min(14 * scale, length * .07) * sign
        path = None
        for factor in (1, -1, 2, -2, 0):
            candidate = _bend(start, end, amount * factor)
            if _clear(candidate, obstacles, bounds) and within_budget(candidate):
                path = candidate
                break
        if path is None:
            path = _grid_route(start, end, obstacles, bounds, max(9, 12 * scale))
        if not within_budget(path):
            path = None
            # A label must not create a detour longer than a legal city move.
            for factor in (1, -1, 2, -2, 0):
                candidate = _bend(start, end, amount * factor)
                if _clear(candidate, hard_obstacles, bounds) and within_budget(candidate):
                    path = candidate
                    break
        if path is None:
            candidate = _grid_route(start, end, hard_obstacles, bounds, max(9, 12 * scale))
            if within_budget(candidate):
                path = candidate
        if path is None:
            continue
        # Continue under the sprite to its entrance; transparent sprite margins
        # must not leave a road ending in empty space beside a city.
        if len(path) >= 2:
            result.append((a, b, path))
    return result


@dataclass
class TransportNetwork:
    land: list = field(default_factory=list)
    sea: list = field(default_factory=list)
    bridges: list = field(default_factory=list)
    docks: list = field(default_factory=list)
    connections: int = 0

    def __len__(self):
        return self.connections


def _split_transport(network, a, b, path, terrain, scale):
    from map_terrain import WATER
    # Sample all segments, including smoothed curves. Ground road shoulders may
    # never overhang water: the shore buffer becomes part of the ferry approach.
    dense = [path[0]]
    for start, end in zip(path, path[1:]):
        count = max(1, math.ceil(math.dist(start, end) / max(.75, terrain.cell / 2)))
        dense.extend((start[0] + (end[0] - start[0]) * i / count,
                      start[1] + (end[1] - start[1]) * i / count) for i in range(1, count + 1))
    runs = []
    for start, end in zip(dense, dense[1:]):
        land = terrain.path_clear([start, end], 'land')
        if runs and runs[-1][0] == land:
            runs[-1][1].append(end)
        else:
            runs.append((land, [start, end]))
    for index, (land, points) in enumerate(runs):
        if land:
            network.land.append((a, b, points))
            continue
        length = sum(math.dist(p, q) for p, q in zip(points, points[1:])) / scale
        wet_length = sum(math.dist(p, q) for p, q in zip(points, points[1:])
                         if terrain.kind_at(((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)) == WATER) / scale
        if (0 < index < len(runs) - 1 and wet_length <= 24
                and length <= 36 + 2 * terrain.cell / scale):
            network.bridges.append((a, b, points))
        else:
            network.sea.append((a, b, points))
            if index:
                network.docks.append((points[0], points[min(2, len(points) - 1)]))
            if index < len(runs) - 1:
                network.docks.append((points[-1], points[max(0, len(points) - 3)]))


def build_transport_network(cities, roads, labels, bounds, scale=1, terrain=None,
                            movement_limit=MAX_MOVE_DISTANCE):
    roads = filter_city_links(cities, roads, scale, movement_limit)
    if terrain is None:
        paths = build_road_paths(cities, roads, labels, bounds, scale, movement_limit)
        return TransportNetwork(land=paths, connections=len(paths))
    network = TransportNetwork()
    seen = set()
    rects = {key: (x - 5, y - 4, x + 82, y + 82) for key, (x, y) in cities.items()}
    for a, b in roads:
        if a == b or a not in cities or b not in cities or (a, b) in seen:
            continue
        seen.add((a, b))
        start = cities[a][0] + 38.5, cities[a][1] + 30
        end = cities[b][0] + 38.5, cities[b][1] + 30
        hard_obstacles = [rect for key, rect in rects.items() if key not in (a, b)]
        obstacles = hard_obstacles + list(labels.values())
        def within_budget(candidate):
            return candidate is not None and (movement_limit is None or route_in_range(candidate, scale, movement_limit))
        amount = min(14 * scale, math.dist(start, end) * .07) * (1 if (a * 31 + b * 17) % 2 else -1)
        path = None
        for factor in (1, -1, 2, -2, 0):
            candidate = _bend(start, end, amount * factor)
            if _clear(candidate, obstacles, bounds, terrain) and within_budget(candidate):
                path = candidate
                break
        step = max(8 * scale, terrain.cell * 2)
        if path is None:
            path = _grid_route(start, end, obstacles, bounds, step, terrain)
        if not within_budget(path):
            path = None
            # Labels are soft obstacles. Water is never a soft obstacle for roads.
            for factor in (1, -1, 2, -2, 0):
                candidate = _bend(start, end, amount * factor)
                if _clear(candidate, hard_obstacles, bounds, terrain) and within_budget(candidate):
                    path = candidate
                    break
        if path is None:
            candidate = _grid_route(start, end, hard_obstacles, bounds, step, terrain)
            if within_budget(candidate):
                path = candidate
        if path is not None:
            network.land.append((a, b, path))
        else:
            # If a long coastal bypass exceeds one move, use an eligible short
            # water crossing. Never force a loop just to connect the picture.
            for blocked in (obstacles, hard_obstacles):
                for factor in (1, -1, 2, -2, 0):
                    candidate = _bend(start, end, amount * factor)
                    if _clear(candidate, blocked, bounds, terrain, 'mixed') and within_budget(candidate):
                        path = candidate
                        break
                if path is not None:
                    break
                candidate = _grid_route(start, end, blocked, bounds, step, terrain, 'mixed')
                if within_budget(candidate):
                    path = candidate
                    break
            if path is None:
                continue
            _split_transport(network, a, b, path, terrain, scale)
        network.connections += 1
    return network


def dashed_segments(points, on=8, off=6):
    """Explicit dashes work with thick antialiased Kivy lines on every backend."""
    result, phase = [], 0.0
    period = on + off
    for a, b in zip(points, points[1:]):
        length = math.dist(a, b)
        if length < 1e-6:
            continue
        position = 0.0
        while position < length - 1e-6:
            local = phase % period
            visible = local < on
            take = min(length - position, (on - local) if visible else (period - local))
            if take < 1e-6:
                phase += 1e-5
                continue
            if visible:
                result.append(((a[0] + (b[0] - a[0]) * position / length,
                                a[1] + (b[1] - a[1]) * position / length),
                               (a[0] + (b[0] - a[0]) * (position + take) / length,
                                a[1] + (b[1] - a[1]) * (position + take) / length)))
            position += take
            phase += take
    return result


def draw_transport_layer(network, scale=1):
    from kivy.graphics import Color, InstructionGroup, Line, Ellipse
    group = InstructionGroup()
    group.add(draw_road_layer(network.land, scale))
    width = max(.85, min(scale, 1.35))
    dashes = [dash for a, b, points in network.sea for dash in dashed_segments(points, 8 * width, 6 * width)]
    for rgb, alpha, thickness in (((.02,.09,.16), .85, 2.5), ((.62,.92,1.0), 1, 1.05)):
        group.add(Color(*rgb, alpha))
        for a, b in dashes:
            group.add(Line(points=[*a, *b], width=thickness * width, cap='round'))
    for a, b, points in network.bridges:
        group.add(Color(.17, .11, .06, 1))
        group.add(Line(points=[v for p in points for v in p], width=4.5 * width))
        # Short transverse timber planks distinguish a bridge from a sea lane.
        for p, q in dashed_segments(points, .8 * width, 3 * width):
            dx, dy = q[0] - p[0], q[1] - p[1]
            length = max(math.hypot(dx, dy), .001)
            nx, ny = -dy / length * 3.5 * width, dx / length * 3.5 * width
            group.add(Color(.83, .67, .42, 1))
            group.add(Line(points=[p[0] - nx, p[1] - ny, p[0] + nx, p[1] + ny], width=1.0 * width))
    for shore, direction in network.docks:
        group.add(Color(.08,.12,.16,.95))
        group.add(Ellipse(pos=(shore[0] - 4 * width, shore[1] - 4 * width), size=(8 * width, 8 * width)))
        group.add(Color(.94,.83,.55,1))
        group.add(Ellipse(pos=(shore[0] - 2 * width, shore[1] - 2 * width), size=(4 * width, 4 * width)))
    return group


def draw_road_layer(paths, scale=1):
    """Paint compacted earth, contrasting shoulders and two subtle wheel ruts."""
    from kivy.graphics import Color, InstructionGroup, Line, Mesh
    from kivy.graphics.texture import Texture
    global _surface_texture
    if _surface_texture is None:
        rng = random.Random(3407)
        pixels = bytearray()
        for y in range(64):
            for x in range(32):
                u = x / 31
                rut = sum(math.exp(-((u - center) / .09) ** 2) for center in (.28, .72))
                grain = rng.uniform(-.045, .045) - rut * .075
                pixels.extend((*[int(max(0, min(1, value + grain)) * 255)
                                 for value in (.78, .64, .43)], 255))
        _surface_texture = Texture.create(size=(32, 64), colorfmt='rgba')
        _surface_texture.wrap = 'repeat'
        _surface_texture.blit_buffer(bytes(pixels), colorfmt='rgba', bufferfmt='ubyte')
    group = InstructionGroup()
    width_scale = max(0.85, min(scale, 1.35))
    # Network-wide passes blend junctions instead of stacking road-end stripes.
    for rgb, alpha, width, shift in (
        ((0.10, 0.08, 0.06), 0.35, 5.0, (0.8, -1.0)),
        ((0.23, 0.17, 0.10), 0.95, 3.8, (0, 0)),
        ((0.86, 0.73, 0.49), 1.00, 3.0, (0, 0)),
        ((0.78, 0.64, 0.43), 1.00, 2.5, (0, 0)),
    ):
        group.add(Color(*rgb, alpha))
        for a, b, points in paths:
            group.add(Line(points=[value for x, y in points for value in (x + shift[0], y + shift[1])],
                           width=width * width_scale, joint='round', cap='round'))
    group.add(Color(1, 1, 1, 1))
    for a, b, points in paths:
        vertices, indices, distance = [], [], 0.0
        for index, (x, y) in enumerate(points):
            previous, following = points[max(0, index - 1)], points[min(len(points) - 1, index + 1)]
            dx, dy = following[0] - previous[0], following[1] - previous[1]
            length = max(math.hypot(dx, dy), 0.001)
            if index:
                distance += math.dist(points[index - 1], (x, y))
            for side, u in ((-1, 0), (1, 1)):
                offset = side * 2.4 * width_scale
                vertices.extend((x - dy / length * offset, y + dx / length * offset, u, distance / 32))
            if index:
                v = index * 2
                indices.extend((v - 2, v - 1, v, v - 1, v + 1, v))
        group.add(Mesh(vertices=vertices, indices=indices, mode='triangles', texture=_surface_texture))
    return group
