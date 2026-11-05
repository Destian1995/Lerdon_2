"""Faction art and persistent visual identity of a city, independent of Python hash seeds."""
from hashlib import sha256
from pathlib import Path
from city_construction import CATALOG

ROOT=Path('files/city/interiors')
THEMES={'Север':'north','Эльфы':'elves','Вампиры':'vampires','Адепты':'adepts',
        'Элины':'elines','Нежить':'undead','Мятежники':'rebels','Нейтрал':'neutral'}
VARIANTS=3
# Ground anchors and widths in panorama coordinates. Sprite bases sit on the ground.
LOTS={'Больница':(.20,.42,.19),'Фабрика':(.77,.42,.20),'Стена':(.50,.60,.31),
      'Рынок':(.52,.23,.24),'Кузница':(.22,.17,.20),'Цитадель':(.84,.60,.22)}


def theme_key(faction):return THEMES.get(faction,'neutral')


def map_icon(faction):
    key={'north':'people','elves':'elfs','elines':'poly','undead':'castle_death',
         'rebels':'keig','neutral':'default'}.get(theme_key(faction),theme_key(faction))
    return f'files/buildings/{key}.png'


def city_variant(city):return int.from_bytes(sha256(city.encode('utf-8')).digest()[:4],'big')%VARIANTS+1


def panorama_path(faction,city):return str(ROOT/theme_key(faction)/f'city-{city_variant(city)}.jpg')


def building_path(faction,building):return str(ROOT/theme_key(faction)/(CATALOG[building]['key']+'.png'))
