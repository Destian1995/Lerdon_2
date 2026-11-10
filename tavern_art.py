"""Taverns share each town's persistent faction and panorama variant."""
from pathlib import Path
from town_art import city_variant,theme_key

ROOT=Path('files/city/taverns')


def tavern_path(faction,city):
    return str(ROOT/theme_key(faction)/('tavern-'+str(city_variant(city))+'.png'))


def city_tavern(conn,city,player):
    row=conn.execute('SELECT faction FROM cities WHERE name=?',(city,)).fetchone()
    faction=row[0] if row else player
    columns={r[1] for r in conn.execute('PRAGMA table_info(cities)')}
    undead=conn.execute('SELECT COALESCE(is_undead,0) FROM cities WHERE name=?',(city,)).fetchone() if 'is_undead' in columns else None
    from morgana_covenant import presentation_faction
    faction='Нежить' if undead and undead[0] else presentation_faction(conn,city,faction)
    return tavern_path(faction,city or '')
