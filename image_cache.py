"""Invalidate generated image caches on visual releases without touching saves."""
import json
from pathlib import Path
import shutil
import sys

IMAGE_CACHE_VERSION='8.5.0-full-icons-1'
IMAGE_CACHE_DIRS=('artifact_icon_cache','cache/artifact_icons','image_cache',
                  'icon_cache','texture_cache','cache/images','cache/icons','cache/textures')


def refresh_image_cache(storage_dir):
    storage=Path(storage_dir).resolve()
    marker=storage/'image-cache-version.json'
    try:
        if json.loads(marker.read_text(encoding='utf-8')).get('version')==IMAGE_CACHE_VERSION:
            return False
    except (OSError,ValueError):pass
    for name in IMAGE_CACHE_DIRS:
        target=(storage/name).resolve()
        if target.is_relative_to(storage) and target.is_dir():
            shutil.rmtree(target)
    from kivy.cache import Cache
    for category in ('kv.image','kv.texture','kv.atlas','kv.loader'):
        Cache.remove(category)
    sprites=sys.modules.get('mirror_effect_sprites')
    if sprites:
        sprites.animation_clip.cache_clear();sprites.atlas_texture.cache_clear()
    for module,names in (('town_scene',('texture','building_shape')),
                         ('map_city_effects',('faction_emblem',))):
        loaded=sys.modules.get(module)
        if loaded:
            for name in names:getattr(loaded,name).cache_clear()
    preload=sys.modules.get('preload_cache')
    if preload:
        preload._preloaded=False;preload._texture_paths=[]
    marker.write_text(json.dumps({'version':IMAGE_CACHE_VERSION}),encoding='utf-8')
    return True
