"""Offline annotation authoring; requires Pillow. Run from project root.

Biome regions and water search windows are authored per map below. Colour
extraction runs only inside those windows; it is not used by the game. Review
assets/terrain-annotations.jpg after every art or annotation change.
"""
import hashlib
import json
import sys
from collections import deque
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw, ImageFilter, ImageChops
from map_terrain import LAND, WATER, FOREST, MOUNTAIN, SNOW, DESERT, CORRUPTION, VOID, TERRAIN_NAMES

GRID = (300, 200)
ALL = [(0, 0), (1, 0), (1, 1), (0, 1)]
EAST = [(.65, .06), (.97, .06), (.97, .57), (.90, .69), (.75, .70), (.67, .48)]
SPECS = {
    1: {'base': LAND, 'regions': [(FOREST, [(.29,.04),(.65,.04),(.70,.65),(.54,.87),(.33,.73)]),
                                 (MOUNTAIN, EAST), (SNOW, [(.83,.04),(.98,.04),(.98,.38),(.90,.40),(.81,.20)])],
        'water_windows': [ALL],
        'water_exclude': [[(.76,.04),(.98,.04),(.98,.50),(.85,.44)]]},
    2: {'base': LAND, 'regions': [(FOREST, [(.24,.04),(.67,.04),(.71,.63),(.54,.83),(.30,.69)]),
                                 (MOUNTAIN, EAST)], 'water_windows': [ALL],
        'water_exclude': [[(.64,.04),(.98,.04),(.98,.46),(.75,.46)]]},
    3: {'base': CORRUPTION, 'regions': [(SNOW, [(0,0),(.52,0),(.50,.39),(.48,.80),(.45,1),(0,1)]),
                                       (MOUNTAIN, [(.08,.05),(.42,.05),(.48,.22),(.23,.24)]),
                                       (MOUNTAIN, [(.58,.04),(.97,.04),(.97,.45),(.85,.40),(.72,.20)])],
        'water_windows': [[(.15,.28),(.34,.26),(.38,.34),(.32,.42),(.34,.48),(.34,.55),
                           (.43,.64),(.39,.76),(.25,.83),(.14,.74),(.16,.63),(.27,.51),(.25,.44),(.18,.39)],
                          [(.57,.54),(.91,.53),(.97,.92),(.97,.98),(.61,.98),(.65,.77),(.55,.70)]],
        'green_water': True},
    4: {'base': DESERT, 'regions': [(MOUNTAIN, [(.55,.04),(.97,.04),(.97,.25),(.72,.26)])],
        'water_windows': [ALL], 'green_water': True},
    5: {'base': FOREST, 'regions': [(SNOW, [(.50,0),(1,0),(1,1),(.47,1),(.49,.58)]),
                                   (MOUNTAIN, [(.63,.04),(.97,.04),(.97,.29),(.70,.31),(.58,.17)])],
        'water_windows': [[(0,0),(.49,0),(.49,1),(0,1)],
                          [(.58,.44),(.73,.42),(.74,.51),(.85,.55),(.91,.61),(.94,.72),
                           (.86,.87),(.67,.85),(.59,.73),(.65,.61),(.66,.53),(.58,.52)]]},
    6: {'base': FOREST, 'regions': [(CORRUPTION, [(.51,0),(1,0),(1,1),(.49,1),(.50,.61)]),
                                   (MOUNTAIN, [(.62,.04),(.97,.04),(.97,.43),(.88,.34),(.80,.18)])],
        'water_windows': [ALL], 'green_water': True},
    7: {'base': CORRUPTION, 'regions': [(MOUNTAIN, [(.68,.03),(.97,.03),(.97,.50),(.88,.42),(.72,.25)])],
        'water_windows': [ALL], 'green_water': True},
}
COLORS = {LAND: '#d9c382', WATER: '#187fbb', FOREST: '#376d35', MOUNTAIN: '#715364',
          SNOW: '#dae9f4', DESERT: '#e6b756', CORRUPTION: '#635346', VOID: '#181e27'}


def polygon(draw, points, size, fill):
    draw.polygon([(round(x * size[0]), round(y * size[1])) for x, y in points], fill=fill)


def build(number, spec):
    source = Path(f'files/map/generate/map_{number}.png')
    image = Image.open(source).convert('RGB')
    annotation = Image.new('L', GRID, spec['base'])
    draw = ImageDraw.Draw(annotation)
    for kind, points in spec['regions']:
        polygon(draw, points, GRID, kind)
    # Constrain the snow maps' blue shadows to explicitly authored water windows.
    windows = Image.new('L', image.size, 0)
    for points in spec['water_windows']:
        polygon(ImageDraw.Draw(windows), points, image.size, 255)
    for points in spec.get('water_exclude', []):
        polygon(ImageDraw.Draw(windows), points, image.size, 0)
    pixels = []
    for index, (r, g, b) in enumerate(image.getdata()):
        blue = g > r * 1.12 and b > r * 1.08 and b >= g * .90 and g >= b * .72 and max(r, g, b) > 24
        green_region = number in (4, 7) or (number in (3, 6) and index % image.width > image.width * .52)
        green = (spec.get('green_water', False) and green_region and
                 g > r * 1.16 and b > r * .80 and b > g * .60)
        pixels.append(255 if blue or green else 0)
    water = Image.new('L', image.size)
    water.putdata(pixels)
    water = ImageChops.multiply(water, windows).resize(GRID, Image.Resampling.BOX)
    water = water.point(lambda p: 255 if p >= 60 else 0)
    water = water.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.MinFilter(3))
    # Remove isolated speckles, preserving narrow connected river channels.
    values = list(water.getdata())
    visited = set()
    for index, value in enumerate(values):
        if not value or index in visited:
            continue
        component, queue = [], deque([index])
        visited.add(index)
        while queue:
            item = queue.popleft()
            component.append(item)
            y, x = divmod(item, GRID[0])
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx, ny = x + dx, y + dy
                neighbor = ny * GRID[0] + nx
                if 0 <= nx < GRID[0] and 0 <= ny < GRID[1] and values[neighbor] and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        if len(component) < 5:
            for item in component:
                values[item] = 0
    water.putdata(values)
    annotation.paste(WATER, mask=water)
    # Refine forest regions to actual tree clusters, leaving their clearings open.
    small = image.resize(GRID, Image.Resampling.BOX)
    values = list(annotation.getdata())
    for index, ((r, g, b), kind) in enumerate(zip(small.getdata(), values)):
        if kind == FOREST and not (g > r * .92 and g > b * 1.12 and (r + g + b) / 3 < 140):
            values[index] = LAND
    for y in range(GRID[1]):
        for x in range(GRID[0]):
            if x < 8 or x >= GRID[0] - 8 or y < 8 or y >= GRID[1] - 8:
                values[y * GRID[0] + x] = VOID
    annotation.putdata(values)
    rows = []
    for y in range(GRID[1]):
        runs = []
        for value in values[y * GRID[0]:(y + 1) * GRID[0]]:
            if runs and runs[-1][0] == value:
                runs[-1][1] += 1
            else:
                runs.append([value, 1])
        rows.append(runs)
    data = {'version': 1, 'image': source.name,
            'image_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
            'image_size': list(image.size), 'world_size': [1200, 800],
            'grid_size': list(GRID), 'row_origin': 'top-left',
            'classes': TERRAIN_NAMES, 'authoring': spec, 'rows': rows}
    destination = Path(f'files/map/terrain/map_{number}.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    preview = Image.new('RGB', GRID)
    preview.putdata([tuple(bytes.fromhex(COLORS[v][1:])) for v in values])
    preview.save(destination.with_suffix('.png'))
    print(source.name, 'water:', round(values.count(WATER) / len(values) * 100, 1), '%')
    return image, preview


if __name__ == '__main__':
    sheet = Image.new('RGB', (1200, 7 * 285 + 35), '#181e27')
    text = ImageDraw.Draw(sheet)
    text.text((12, 9), 'BLUE water | GREEN forest | PURPLE mountains | WHITE snow | GOLD desert | BROWN corruption', fill='white')
    for number, spec in SPECS.items():
        image, preview = build(number, spec)
        y = 35 + (number - 1) * 285
        original = image.resize((400, 266), Image.Resampling.LANCZOS)
        mask = preview.resize((400, 266), Image.Resampling.NEAREST)
        overlay = Image.blend(original, mask, .48)
        sheet.paste(original, (0, y))
        sheet.paste(mask, (400, y))
        sheet.paste(overlay, (800, y))
        text.text((8, y + 267), f'map_{number}: original / annotation / overlay', fill='white')
    sheet.save('assets/terrain-annotations.jpg', quality=94)
