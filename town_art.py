"""Faction art and persistent visual identity of a city, independent of Python hash seeds."""
from hashlib import sha256
from pathlib import Path
from city_construction import CATALOG

ROOT=Path('files/city/interiors')
THEMES={'Север':'north','Эльфы':'elves','Вампиры':'vampires','Адепты':'adepts',
        'Элины':'elines','Нежить':'undead','Мятежники':'rebels','Нейтрал':'neutral'}
VARIANTS=3
# Ground anchors and widths in panorama coordinates. Sprite bases sit on the ground.
LOTS={'Больница':(.20,.38,.19),'Фабрика':(.77,.38,.20),'Стена':(.84,.56,.31),
      'Рынок':(.52,.19,.24),'Кузница':(.22,.13,.20),'Цитадель':(.52,.50,.22)}

# Top stair landing in each 1536×864 panorama (left/top image coordinates).
# Forest and necropolis approaches are asymmetric and vary between panoramas.
CITADEL_STAIRS={
    'north':((805,390),(768,397),(785,383)),
    'elves':((581,310),(612,352),(626,363)),
    'vampires':((786,390),(787,392),(800,393)),
    'adepts':((779,386),(768,396),(793,385)),
    'elines':((791,387),(786,365),(794,387)),
    'undead':((842,365),(688,380),(818,372)),
    'rebels':((803,377),(790,391),(802,378)),
    'neutral':((783,385),(770,392),(783,387)),
}

# Ground contact of each entry path, in bottom-origin sprite UV coordinates.
# The moderate three-quarter camera follows the approved Elines artwork.
CITADEL_DOORS={'north':(.41,.038),'elves':(.41,.035),'vampires':(.415,.048),
    'adepts':(.48,.028),'elines':(.27,.170),'undead':(.40,.046),
    'rebels':(.415,.053),'neutral':(.42,.043)}


def citadel_stair(faction,city):
    x,y=CITADEL_STAIRS[theme_key(faction)][city_variant(city)-1]
    return x/1536,1-y/864


def citadel_entry(faction,city):
    x,y=citadel_stair(faction,city)
    # Elven stairs enter the terrace at its left edge. The keep stands farther
    # right on that terrace, with the landing leading across to its doorway.
    return (x+.12 if theme_key(faction)=='elves' else x),y


def citadel_lot(faction,city,panorama_aspect,sprite_aspect):
    """Place the doorway on its approach, including transparent margins."""
    target_x,target_y=citadel_entry(faction,city)
    door_x,door_y=CITADEL_DOORS[theme_key(faction)]
    width=LOTS['Цитадель'][2]
    height=width*panorama_aspect*sprite_aspect
    if target_y+(1-door_y)*height>.98:
        width*=(.98-target_y)/((1-door_y)*height)
        height=width*panorama_aspect*sprite_aspect
    return target_x+(.5-door_x)*width,target_y-door_y*height,width


def building_mirrored(faction,building):
    """Match the gate's visible side to the keep in the faction panorama."""
    return False  # New faction defenses are painted in their final orientation.


def defense_lot(faction,panorama_aspect,sprite_aspect):
    """Keep tall towers and trees inside the panorama without stretching them."""
    x,y,width=LOTS['Стена']
    if theme_key(faction)=='north':
        # The compact arsenal sits farther back inside the upper oval lot.
        return .83,.62,min(.185,.165/(panorama_aspect*sprite_aspect))
    if theme_key(faction)=='adepts':
        # A low abbey occupies its terrace rather than dominating the skyline.
        return .83,.58,min(.20,.21/(panorama_aspect*sprite_aspect))
    if theme_key(faction)=='elves':
        # Move the tree back on its terrace, keeping the crown inside the view.
        y=.60
    width={'elves':.23}.get(theme_key(faction),width)
    height=width*panorama_aspect*sprite_aspect
    if theme_key(faction) in ('north','elves','adepts','elines'):
        width*=min(1,(.98-y)/height)
    return x,y,width


def theme_key(faction):return THEMES.get(faction,'neutral')


def map_icon(faction):
    key={'north':'people','elves':'elfs','elines':'poly','undead':'castle_death',
         'rebels':'keig','neutral':'default'}.get(theme_key(faction),theme_key(faction))
    return f'files/buildings/{key}.png'


def city_variant(city):return int.from_bytes(sha256(city.encode('utf-8')).digest()[:4],'big')%VARIANTS+1


def panorama_path(faction,city):return str(ROOT/theme_key(faction)/f'city-{city_variant(city)}.jpg')


def building_path(faction,building):return str(ROOT/theme_key(faction)/(CATALOG[building]['key']+'.png'))
