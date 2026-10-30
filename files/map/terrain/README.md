# Terrain annotations

Each `map_N.json` describes its matching `../generate/map_N.png`.
The neighbouring PNG is a colour-coded inspection mask, not a game background.
The game loads JSON with Python's standard library; Pillow is only required by
the offline authoring and preview tools.

- World coordinates: 1200 × 800, origin at the bottom left, matching cities.
- Annotation grid: 300 × 200; one cell covers 4 × 4 world units.
- Stored rows: top to bottom, explicitly marked `row_origin: top-left`.
- `rows`: each row is run-length encoded as `[class_id, cell_count]` pairs.
- Classes: 0 land, 1 water, 2 forest, 3 mountain, 4 snow, 5 desert,
  6 corruption, 255 decorative frame / outside playable terrain.
- Water includes seas, lakes, rivers and the dark pools of corrupted maps.
- `image_sha256` ties the annotation to the exact artwork. Changing a PNG
  without updating its annotation causes a clear error instead of silently
  routing roads with the wrong geography.

## Authoring and review

The initial water mask is extracted offline inside per-map water windows.
Biome regions, snow exclusions and green-water areas are authored separately
for each map in `tools/build_map_terrain.py` (`SPECS`). These are stored in each
JSON's `authoring` section as a record of the source regions. The JSON grid is
the runtime source of truth; biome regions are broad planning regions, not
pixel-perfect mountain silhouettes.

To change a map's classification, update its `SPECS` entry and/or the offline
extraction rule, then run from the project root:

```powershell
py -3.12 tools/build_map_terrain.py
py -3.12 -m unittest discover -s tests -v
py -3.12 tests/render_roads_preview.py
```

Inspect `assets/terrain-annotations.jpg` (original / mask / overlay) for all
seven maps, especially coastlines, snowy shadows, oasis banks and green pools.
Review the resulting JSON and inspection PNGs together. Rebuilding replaces
the generated masks, so custom corrections should be kept in the authoring
tool rather than only painting the inspection PNG.

## Gameplay integration

The background is selected **before** city generation. The generator rejects
water and frame cells across the city's ground footprint, including a shore
clearance and the current sprite scale. It retains 26 cities and the existing
distance/connectivity rules, with a bounded retry limit.

Roads first search for a continuous land path, respecting a clearance wide
enough for the road shoulders. Labels are soft obstacles; water never is.
If a land path does not exist, a mixed land/water route is computed. Only its
land portions receive the ground-road texture. Longer water portions receive
a contrasting dashed sea/ferry lane and shore markers; short bounded spans
(up to 24 world units of actual water, plus shore approach clearance and grid
resolution tolerance) receive timber bridges.

Terrain weights favour open land over forests and mountains during path
search. These are visual routing weights, not new army movement prices. The
city connection graph retains the 280-unit Manhattan movement limit. Roads are
also filtered before rendering: a decorative detour cannot exceed 280 world
units, and labels cannot force a longer loop. If no short terrain-safe route
can be found, that visual connection is omitted rather than forced. Terrain
annotations do not relocate cities in an already existing database.

`map_terrain.py` handles coordinate conversion, image validation and shared
shore-clearance data. `map_roads.py` caches terrain search grids per projection;
`MapWidget` caches the complete transport geometry until its inputs change.
