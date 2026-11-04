"""City map indicators exclude troops already marching out of the city."""
import sys


def military_presence(conn):
    screen = getattr(sys.modules.get('game_process'), '_active_game_screen', None)
    departures = (getattr(screen, '_march_departures', {})
                  if getattr(screen, 'conn', None) is conn else {})
    columns = {row[1] for row in conn.execute('PRAGMA table_info(units)')}
    unit_class = 'CAST(u.unit_class AS INTEGER)' if 'unit_class' in columns else '1'
    consumption = 'COALESCE(u.consumption,0)' if 'consumption' in columns else '0'
    rows = conn.execute('''SELECT g.city_name,g.unit_name,u.faction,c.faction,
        g.unit_count,''' + consumption + ',' + unit_class + '''
        FROM garrisons g JOIN units u ON u.unit_name=g.unit_name
        LEFT JOIN cities c ON c.name=g.city_name WHERE g.unit_count>0''')
    city_consumption, faction_consumption, city_counts, heroes = {}, {}, {}, set()
    for city, name, faction, owner, count, upkeep, rank in rows:
        remaining = max(0, count - departures.get((city, name), 0))
        city_counts[city] = city_counts.get(city, 0) + remaining
        city_consumption[city] = city_consumption.get(city, 0) + remaining * upkeep
        # Moving troops remain part of the faction's army: the denominator of
        # the city's strength badge must not shrink while the marker travels.
        if owner is not None:
            faction_consumption[owner] = faction_consumption.get(owner, 0) + count * upkeep
        if faction != owner and owner != 'Мятежники':
            faction_consumption[faction] = faction_consumption.get(faction, 0) + count * upkeep
        if remaining and rank in (2, 3, 4):
            heroes.add((city, faction))
    return dict(city_consumption=city_consumption, faction_consumption=faction_consumption,
                city_counts=city_counts, heroes=tuple(sorted(heroes)))
