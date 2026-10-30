"""Terrain annotations, land-only spawning, coast-aware roads and ferry lanes."""
import ast
import contextlib
import io
import json
import math
from pathlib import Path
import random
import tempfile
import unittest

from map_terrain import TerrainMap, TerrainView, load_terrain, LAND, WATER, VOID
from map_roads import build_transport_network, dashed_segments


def synthetic_terrain(water_rects):
    rows = []
    for y in range(80):
        row = []
        for x in range(120):
            # Rectangles use bottom-left game coordinates, matching city positions.
            wx, wy = (x + .5) * 10, 800 - (y + .5) * 10
            value = WATER if any(l <= wx < r and b <= wy < t for l, b, r, t in water_rects) else LAND
            if row and row[-1][0] == value:
                row[-1][1] += 1
            else:
                row.append([value, 1])
        rows.append(row)
    return TerrainMap({'version': 1, 'grid_size': [120, 80], 'world_size': [1200, 800],
                       'row_origin': 'top-left', 'rows': rows})


class TerrainAnnotationTests(unittest.TestCase):
    def test_all_seven_images_have_matching_annotations_and_water(self):
        for number in range(1, 8):
            terrain = load_terrain(f'files/map/generate/map_{number}.png')
            self.assertIsNotNone(terrain)
            self.assertEqual((terrain.width, terrain.height), (300, 200))
            self.assertGreater(terrain.grid.count(WATER), 500)
            self.assertEqual(terrain.kind_at(-1, 300), VOID)

    def test_image_vertical_axis_and_screen_scale(self):
        terrain = synthetic_terrain([(0, 600, 1200, 800)])
        self.assertEqual(terrain.kind_at(400, 700), WATER)
        self.assertEqual(terrain.kind_at(400, 100), LAND)
        view = TerrainView(terrain, (100, 50), .5)
        self.assertEqual(view.kind_at((300, 400)), WATER)
        self.assertEqual(view.kind_at((300, 100)), LAND)

    def test_updated_image_requires_updated_annotation(self):
        with tempfile.TemporaryDirectory() as directory:
            image = Path(directory) / 'map_1.png'
            image.write_bytes(b'changed artwork')
            with self.assertRaisesRegex(ValueError, 'does not match'):
                load_terrain(image)

    def test_malformed_rle_is_rejected(self):
        with self.assertRaises(ValueError):
            TerrainMap({'version': 1, 'grid_size': [2, 1], 'row_origin': 'top-left', 'rows': [[[0, 1]]]})

    def test_city_footprint_cannot_hang_over_water(self):
        terrain = synthetic_terrain([(600, 0, 1200, 800)])
        self.assertTrue(terrain.city_allowed(400, 300))
        self.assertFalse(terrain.city_allowed(560, 300))
        self.assertFalse(terrain.city_allowed(530, 300, sprite_scale=.7))

    def test_generation_on_every_map_at_two_sprite_scales(self):
        tree = ast.parse(Path('generate_map.py').read_text(encoding='utf-8'))
        names = ('generate_city_coords', 'select_faction_cities', 'generate_all_cities', 'manhattan')
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        rng = random.Random()
        ns = dict(random=rng, math=math, MARGIN=100, MAP_SIZE=(1200, 800),
                  MIN_DISTANCE_PX=120, MAX_DISTANCE_PX=300, MANHATTAN_MOVE_LIMIT=280, TOTAL_CITIES=26)
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'generate_map.py', 'exec'), ns)
        for number in range(1, 8):
            terrain = load_terrain(f'files/map/generate/map_{number}.png')
            for scale in (.8, 1.15):
                rng.seed(2026 + number)
                with contextlib.redirect_stdout(io.StringIO()):
                    positions = ns['generate_all_cities'](terrain, sprite_scale=scale)
                self.assertEqual(len(positions), 26)
                self.assertTrue(all(terrain.city_allowed(*p, sprite_scale=scale) for p in positions))
                reached = {0}
                while True:
                    following = {i for i, p in enumerate(positions) if any(
                        abs(p[0] - positions[j][0]) + abs(p[1] - positions[j][1]) <= 280 for j in reached)}
                    if following <= reached:
                        break
                    reached |= following
                self.assertEqual(len(reached), 26)

    def test_actual_map_routes_keep_all_ground_segments_off_water(self):
        tree = ast.parse(Path('generate_map.py').read_text(encoding='utf-8'))
        names = ('generate_city_coords', 'select_faction_cities', 'generate_all_cities', 'manhattan')
        functions = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        rng = random.Random()
        ns = dict(random=rng, math=math, MARGIN=100, MAP_SIZE=(1200, 800),
                  MIN_DISTANCE_PX=120, MAX_DISTANCE_PX=300, MANHATTAN_MOVE_LIMIT=280, TOTAL_CITIES=26)
        exec(compile(ast.Module(body=functions, type_ignores=[]), 'generate_map.py', 'exec'), ns)
        for number in range(1, 8):
            terrain = load_terrain(f'files/map/generate/map_{number}.png')
            rng.seed(901 + number)
            with contextlib.redirect_stdout(io.StringIO()):
                positions = ns['generate_all_cities'](terrain)
            cities = dict(enumerate(positions))
            # The generator's growing point cloud guarantees at least one
            # previous neighbour within the existing movement limit.
            edges = [(i, min((j for j in range(i) if abs(positions[i][0] - positions[j][0]) +
                              abs(positions[i][1] - positions[j][1]) <= 280),
                             key=lambda j: math.dist(positions[i], positions[j])))
                     for i in range(1, len(positions))]
            view = TerrainView(terrain)
            network = build_transport_network(cities, edges, {}, (35, 35, 1165, 765), terrain=view)
            self.assertEqual(network.connections, len(edges))
            self.assertTrue(all(view.path_clear(path) for a, b, path in network.land))


class TerrainRoutingTests(unittest.TestCase):
    def assert_land_roads_clear(self, network, view):
        self.assertTrue(all(view.path_clear(points) for a, b, points in network.land))

    def test_lake_is_detoured_without_ferry(self):
        view = TerrainView(synthetic_terrain([(510, 270, 650, 450)]))
        network = build_transport_network({1: (350, 300), 2: (750, 300)}, [(1, 2)], {},
                                          (40, 40, 1160, 760), terrain=view, movement_limit=None)
        self.assertEqual(network.connections, 1)
        self.assertEqual(network.sea, [])
        self.assert_land_roads_clear(network, view)

    def test_sea_channel_splits_ground_roads_and_water_lane(self):
        view = TerrainView(synthetic_terrain([(550, 0, 700, 800)]))
        network = build_transport_network({1: (450, 300), 2: (730, 300)}, [(1, 2)], {},
                                          (40, 40, 1160, 760), terrain=view)
        self.assertEqual(len(network.sea), 1)
        self.assertEqual(len(network.docks), 2)
        self.assertEqual(network.bridges, [])
        self.assert_land_roads_clear(network, view)
        self.assertTrue(any(view.kind_at(point) == WATER for point in network.sea[0][2]))

    def test_narrow_river_has_a_bridge(self):
        view = TerrainView(synthetic_terrain([(600, 0, 610, 800)]))
        network = build_transport_network({1: (450, 300), 2: (730, 300)}, [(1, 2)], {},
                                          (40, 40, 1160, 760), terrain=view)
        self.assertEqual(len(network.bridges), 1)
        self.assertEqual(network.sea, [])
        self.assert_land_roads_clear(network, view)

    def test_blocked_labels_never_force_ground_roads_through_water(self):
        view = TerrainView(synthetic_terrain([(550, 0, 700, 800)]))
        network = build_transport_network({1: (450, 300), 2: (730, 300)}, [(1, 2)],
                                          {3: (0, 200, 1200, 500)}, (40, 40, 1160, 760), terrain=view)
        self.assertTrue(network.sea)
        self.assert_land_roads_clear(network, view)

    def test_dashes_are_continuous_across_polyline_vertices(self):
        dashes = dashed_segments([(0, 0), (5, 0), (20, 0)], on=8, off=6)
        length = sum(math.dist(a, b) for a, b in dashes)
        self.assertAlmostEqual(length, 14)
        self.assertTrue(all(a[0] <= b[0] for a, b in dashes))


if __name__ == '__main__':
    unittest.main()
