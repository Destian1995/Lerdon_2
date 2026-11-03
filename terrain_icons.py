"""The nine painted waypoint sprites; variant IDs are saved with the map."""
from functools import lru_cache
from pathlib import Path
import itertools
import math

VARIANTS = {
    'swamp': ('Болото камышей','Мёртвые топи','Кипарисовая трясина','Туманные трясины'),
    'forest': ('Дубовая роща','Сосновый бор','Осенний лес','Берёзовая роща','Древняя чаща'),
}


WARM_NAMES = ('Осенняя дубрава','Золотая лиственница','Осенний лес',
              'Осенняя берёзовая роща','Осенняя древняя чаща')


def local_palette(terrain,x,y):
    """Reviewed background colours, sampled in world space, never screen space."""
    from map_terrain import CORRUPTION
    kind_at=getattr(terrain,'kind_at',lambda *_:None)
    dead = terrain and sum(kind_at(x+dx,y+dy)==CORRUPTION
                           for dx in (-30,0,30) for dy in (-30,0,30)) >= 2
    palette=getattr(terrain,'foliage_palette',None)
    if not palette:
        return ('dead' if dead else 'green'),(105,125,65)
    width,height=palette['grid_size']
    ix=max(0,min(width-1,int(x/terrain.world_width*width)))
    iy=max(0,min(height-1,int((1-y/terrain.world_height)*height)))
    r,g,b,warm=palette['cells'][iy*width+ix]
    if dead or (max(r,g,b)-min(r,g,b)<20 and g<115):
        return 'dead',(r,g,b)
    return ('warm' if warm else 'green'),(r,g,b)


def site_palette(terrain,site):
    return local_palette(terrain,site['x'],site['y'])[0]


def assign_variants(sites,terrain,rng):
    """Find a joint palette match without ever reusing a species on a map."""
    from map_terrain import MOUNTAIN,SNOW
    for kind,names in VARIANTS.items():
        group=[s for s in sites if s['kind']==kind]
        if not group:
            continue
        costs={}
        for i,site in enumerate(group):
            _,rgb=local_palette(terrain,site['x'],site['y'])
            for variant in range(1,len(names)+1):
                cost=0
                if kind=='swamp':
                    # Reed marsh, dead peat bog, lush cypress, misty hummocks.
                    color=((132,132,65),(100,86,56),(74,116,66),(94,103,79))[variant-1]
                    cost=math.dist(rgb,color)/255
                elif terrain and terrain.kind_at(site['x'],site['y']) in (MOUNTAIN,SNOW):
                    cost=0 if variant==2 else .6
                costs[i,variant]=cost+rng.random()*.08
        choices=itertools.permutations(range(1,len(names)+1),len(group))
        best=min(choices,key=lambda ids:sum(costs[i,v] for i,v in enumerate(ids)))
        for site,variant in zip(group,best):
            site['icon_variant']=variant
    return sites


def icon_path(kind, variant, palette=None):
    if kind not in VARIANTS or not 1 <= variant <= len(VARIANTS[kind]):
        raise ValueError('Неизвестный вариант леса или болота.')
    suffix=''
    if palette=='dead':
        suffix='_dead'
    elif kind=='forest':
        if palette=='green' and variant==3:
            suffix='_green'
        elif palette=='warm' and variant!=3:
            suffix='_warm'
    return Path(__file__).resolve().parent/'files/map/features'/f'{kind}_{variant}{suffix}.png'


def icon_name(kind, variant, palette=None):
    if palette=='dead':
        return {'forest':('Мёртвая роща','Сухой бор','Лес безмолвия','Мёртвые берёзы','Пепельная чаща'),
                'swamp':('Безжизненные топи','Смоляная трясина','Затонувший лес','Мёртвое болото')}[kind][variant-1]
    if kind=='forest' and palette=='warm':
        return WARM_NAMES[variant-1]
    if kind=='forest' and palette=='green' and variant==3:
        return 'Кленовый лес'
    return VARIANTS[kind][variant-1]


@lru_cache(maxsize=32)
def _texture(path):
    from kivy.core.image import Image as CoreImage
    return CoreImage(path,mipmap=True).texture


def icon_texture(kind, variant, palette=None):
    return _texture(str(icon_path(kind,variant,palette)))
