# City military indicators

Generated with the built-in `image_gen` tool, two separate calls with
`transparent_background: true`. New art is in
`files/status/army_in_city/garrison_shield.png` and `hero_helm.png`.
The previous star assets are retained. Rendering is in
`GameScreen.draw_army_stars_on_map` in `game_process.py`.

The 68 x 28 map badge contains one 28px shield and three rising bars.
Filled gold bars indicate levels 1–3; unfilled bars stay slate grey.
A separate 32px gold/crimson helmet above the badge indicates a hero,
including when the strength level is zero. Empty cities have no strength badge.

Levels now use consumption: sum(unit_count * units.consumption) for all troops
in the city, divided by the current total army consumption of the city's owner.
One bar: positive and at most 30%; two: above 30% and at most 70%; three: above
70%. Zero consumption has no badge. Totals follow the existing economic upkeep
rules in calculate_and_deduct_consumption: all troops in owned cities plus
faction troops in other cities except rebel cities, without counting the same
troops twice within a faction. Foreign troops in an owned city are included.
This is a share of current consumption, not of the maximum army limit.
Hero detection remains unit_class IN (2, 3, 4).

## Shield prompt

Use case: stylized-concept. Asset type: ONE standalone transparent fantasy strategy map UI garrison icon, must read perfectly at 26 pixels. Create a completely original premium hand-painted sculpted heraldic military SHIELD: broad pointed heater shield, dark midnight blue enamel face, thick bright worn silver steel bevel with tiny restrained antique brass accents. On the face one bold raised silver upright sword, simple broad blade, hilt clearly readable. Strong compact silhouette, frontal symmetric composition, sophisticated realistic metal shading but bold simple forms, high contrast bright perimeter to separate from green and parchment maps. Object fills 86% of square canvas. No stars, no crown, no wings, no text, no letters, no scenery, no pedestal, no frame outside shield, no extra objects, no tiny busy ornaments, no broad glow or cast shadow. Genuinely transparent background, clean alpha cutout. Output only ONE finished icon.

## Hero prompt

Use case: stylized-concept. Asset type: ONE standalone transparent fantasy strategy map UI HERO PRESENT icon, readable at 30 pixels. Create completely original premium hand-painted sculpted heraldic commander helmet: bold front-facing closed medieval great helm in warm pale gold metal, deep black narrow T-shaped visor, thick simple bright gold edges, a SINGLE bold deep crimson red plume arching upward and slightly to right. Compact regal silhouette distinct from a shield. Sophisticated realistic sculpted metal shading but broad simple forms, maximum readability when reduced, high contrast bright perimeter against green and parchment maps. Match a premium silver and midnight-blue military shield icon family, with the hero differentiated by gold and crimson. Object fills 86% of square canvas. No stars, no weapons, no body, no face, no wings, no text, no letters, no scenery, no pedestal, no enclosing circle, no outer frame, no broad glow or cast shadow, no busy tiny ornament. Genuinely transparent background, clean alpha cutout. Output only ONE finished icon.
