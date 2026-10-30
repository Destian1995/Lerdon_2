# Building / faction icons

Generated with the built-in `image_gen` tool on 2026-10-30.
Final assets: `files/buildings/*.png`. Existing filenames are retained for game compatibility.

Inputs for each generation: the corresponding original PNG (edit target) and
`assets/buildings-reference-sheet.jpg` (supporting reference showing original icons and armies).
All requests used `transparent_background: true`.

## Shared prompt

Use case: style-transfer. One premium dark fantasy strategy game faction UI icon.
Image 1 is the edit target: preserve its recognizable symbol or building silhouette,
redesign flat clipart into finely crafted cinematic painted realistic game art.
Image 2 is the army style reference contact sheet. Square canvas, centered 85% fill,
safe transparent padding, bold silhouette legible at 48px and refined details at
larger display. Actual transparent background, clean alpha cutout. No scenery,
rectangular tile, lettering, frame, extra objects, ground, broad glow or cast shadow.

## Asset-specific prompt set

- `adepts.png`: Ornate substantial burnished gold double cross, blackened steel
  bevels, restrained ember red inset gems, fine sacred engravings. Preserve the
  original gold cross silhouette. Match the adepts' fiery gold/black crusader armies.
  Cinematic painted realism, crisp silhouette, one cross emblem only.
- `people.png`: NORTHERN faction: an ornate single long rifle diagonal bottom left
  to top right as original, icy blued steel, black gunmetal, aged silver engravings,
  dark walnut stock, restrained frost highlights. Match people army snowbound
  riflemen and dark fur armor.
- `elfs.png`: ELVEN faction: single ancient living oak tree as original tree
  silhouette, twisting sculptural dark brown trunk with exposed roots, luxuriant
  emerald foliage, subtle small green magical jewels among branches. Match elfs
  army moss, deep forest, emerald sorcery, dark elegant natural fantasy. Not cartoon.
- `poly.png`: ELINES faction: retain original intertwined THREE curved pointed
  triangular bands (triquetra symbol) forming a unified emblem. Rich blood red
  enamel and antique gold metal, subtle dragon-scale engravings and ember
  highlights, bold blackened recesses. Match poly army dragon fire, red/gold
  armored warrior and nature priestess. Precisely interwoven shape, no new symbol.
- `vampires.png`: VAMPIRE faction: a single symmetrical outstretched bat emblem
  with pointed wings, as original bat shape. Obsidian-black and dark silver
  sculpted bat, rich burgundy red leathery wing membranes with delicate violet
  accents and crimson gem eyes. Match vampires army gothic black armor, blood red
  and purple sorcery. Elegant menacing silhouette.
- `castle_death.png`: UNDEAD faction: one compact small fortress castle in
  three-quarter isometric view matching original multi-tower castle silhouette.
  Ruined black stone, jagged gothic spires, cold blue slate roofs, small icy cyan
  glowing window slits, weathered skeletal architectural carvings. Match death
  army cold cyan spectral magic and blackened frost armor. Building only, no
  skull objects floating beside it.
- `keig.png`: REBELLION faction: preserve original anarchist A symbol, an angular
  capital A with extended crossbar and pointed apex, no surrounding circle. Make
  a single forged iron insignia, rough black steel with battered silver bevel
  edges, discreet gold inlaid scratches and tiny ember red accents. Match
  rebellion army grim dark steel armored militia, muted gold cross accents and
  red sky. Legible iconic silhouette.
- `default.png`: NEUTRAL city: one compact medieval castle in three-quarter
  isometric view matching original building silhouette and tower arrangement.
  Pale weathered limestone, warm dark red terracotta roofs, dark metal details,
  fine realistic masonry, warmly lit tiny windows. Same premium painted dark
  fantasy material quality as army reference but neutral subdued palette.
  Clear small-size silhouette, no surrounding landscape.

The shared prompt above consolidates minor wording variations between calls;
the subject, material, palette and transparency requirements are preserved here.
