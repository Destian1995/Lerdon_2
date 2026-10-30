"""Versioned terrain annotations, in the same 1200x800 coordinates as cities.

Runtime uses only stdlib. PNG analysis is an offline authoring step; the game
loads reviewed RLE annotations, never guesses water from screen colours.
"""
from collections import deque
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

LAND, WATER, FOREST, MOUNTAIN, SNOW, DESERT, CORRUPTION, VOID = 0, 1, 2, 3, 4, 5, 6, 255
TERRAIN_NAMES = {LAND: 'land', WATER: 'water', FOREST: 'forest', MOUNTAIN: 'mountain',
                 SNOW: 'snow', DESERT: 'desert', CORRUPTION: 'corruption', VOID: 'frame'}


class TerrainMap:
    def __init__(self, data):
        self.width, self.height = data['grid_size']
        self.world_width, self.world_height = data.get('world_size', [1200, 800])
        self.cell = min(self.world_width / self.width, self.world_height / self.height)
        if data.get('version') != 1 or data.get('row_origin') != 'top-left':
            raise ValueError('Unsupported terrain annotation version or orientation')
        if len(data['rows']) != self.height:
            raise ValueError('Invalid terrain row count')
        self.grid = []
        for runs in data['rows']:
            row = []
            for value, count in runs:
                if value not in TERRAIN_NAMES or count <= 0:
                    raise ValueError('Invalid terrain run')
                row.extend([value] * count)
            if len(row) != self.width:
                raise ValueError('Invalid terrain row width')
            self.grid.extend(row)
        self.image_hash = data.get('image_sha256')
        # Distance to water/frame, in conservative Chebyshev grid cells.
        self.clearance = [65535] * len(self.grid)
        queue = deque()
        for index, value in enumerate(self.grid):
            if value in (WATER, VOID):
                self.clearance[index] = 0
                queue.append(index)
        while queue:
            index = queue.popleft()
            y, x = divmod(index, self.width)
            next_distance = self.clearance[index] + 1
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < self.width and 0 <= ny < self.height:
                        neighbor = ny * self.width + nx
                        if self.clearance[neighbor] > next_distance:
                            self.clearance[neighbor] = next_distance
                            queue.append(neighbor)

    def index_at(self, x, y):
        if not (0 <= x < self.world_width and 0 <= y < self.world_height):
            return None
        ix = min(self.width - 1, int(x / self.world_width * self.width))
        iy = min(self.height - 1, int((1 - y / self.world_height) * self.height))
        return iy * self.width + ix

    def kind_at(self, x, y):
        index = self.index_at(x, y)
        return VOID if index is None else self.grid[index]

    def is_land(self, x, y, clearance=0):
        index = self.index_at(x, y)
        return (index is not None and self.grid[index] not in (WATER, VOID)
                and self.clearance[index] * self.cell > clearance + self.cell * 0.75)

    def city_allowed(self, x, y, sprite_scale=1):
        # Coordinates refer to the bottom-left of the 77px city sprite. Check
        # the actual ground footprint, not just a corner hidden under the icon.
        return all(self.is_land(x + dx / sprite_scale, y + dy / sprite_scale, clearance=5)
                   for dx, dy in ((12, 8), (38.5, 8), (65, 8),
                                  (12, 30), (38.5, 30), (65, 30), (38.5, 48)))


@lru_cache(maxsize=16)
def _load_cached(image_path, image_stamp, annotation_stamp):
    image = Path(image_path)
    annotation = Path(__file__).resolve().parent / 'files/map/terrain' / (image.stem + '.json')
    data = json.loads(annotation.read_text(encoding='utf-8'))
    if hashlib.sha256(image.read_bytes()).hexdigest() != data['image_sha256']:
        raise ValueError(f'Terrain annotation does not match {image.name}; rebuild its mask')
    return TerrainMap(data)


def load_terrain(image_path):
    image = Path(image_path).resolve()
    annotation = Path(__file__).resolve().parent / 'files/map/terrain' / (image.stem + '.json')
    if not annotation.is_file():
        return None
    return _load_cached(str(image), image.stat().st_mtime_ns, annotation.stat().st_mtime_ns)


class TerrainView:
    """Projection shared by routing, shore clearance and transport rendering."""
    def __init__(self, terrain, origin=(0, 0), scale=1):
        self.terrain, self.origin, self.scale = terrain, tuple(origin), scale
        self.cell = terrain.cell * scale
        self.road_clearance = 5 * max(.85, min(scale, 1.35)) / scale
        self.routing_grids = {}

    def world(self, point):
        return ((point[0] - self.origin[0]) / self.scale,
                (point[1] - self.origin[1]) / self.scale)

    def kind_at(self, point):
        return self.terrain.kind_at(*self.world(point))

    def is_land(self, point):
        return self.terrain.is_land(*self.world(point), clearance=self.road_clearance)

    def cost_at(self, point, mode='land'):
        kind = self.kind_at(point)
        if kind == VOID or (mode == 'land' and not self.is_land(point)):
            return math.inf
        return {WATER: 5.0, FOREST: 1.35, MOUNTAIN: 3.5, SNOW: 1.2,
                DESERT: 1.15, CORRUPTION: 1.2}.get(kind, 1.0)

    def path_clear(self, points, mode='land'):
        for a, b in zip(points, points[1:]):
            count = max(1, math.ceil(math.dist(a, b) / max(.75, self.cell / 2)))
            for index in range(count + 1):
                point = (a[0] + (b[0] - a[0]) * index / count,
                         a[1] + (b[1] - a[1]) * index / count)
                if mode == 'land':
                    if not self.is_land(point):
                        return False
                elif self.kind_at(point) == VOID:
                    return False
        return True
