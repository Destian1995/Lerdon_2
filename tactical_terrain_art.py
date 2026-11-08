"""Painted tactical landmarks, sharing forests and marshes with the world map."""
import json
from pathlib import Path

from kivy.core.image import Image as CoreImage
from terrain_icons import icon_path

ROOT = Path(__file__).resolve().parent
ART = ROOT / 'files/battlefields/terrain'


def terrain_path(kind, pos, biome):
    variant = (pos[0] * 7 + pos[1] * 11) % 2
    if kind in ('forest', 'swamp'):
        palette = 'dead' if biome == 'corruption' else 'green'
        number = (2 if biome == 'snow' else (1, 4)[variant]) if kind == 'forest' else (1, 4)[variant]
        return icon_path(kind, number, palette)
    if kind in ('hill', 'rock', 'water', 'bridge'):
        return ART / (kind + '.png')
    return None


def landmark_rect(texture_size, px, py, cell):
    """Keep the complete silhouette inside its cell, including on small screens."""
    width, height = texture_size
    scale = min(cell * .94 / width, cell * .86 / height)
    size = width * scale, height * scale
    return (px + (cell - size[0]) / 2, py + cell * .07), size


class TerrainArt:
    def __init__(self):
        self.textures = {}
        self.bounds = json.loads((ART / 'bounds.json').read_text(encoding='utf-8'))

    def texture(self, kind, pos, biome):
        path = terrain_path(kind, pos, biome)
        if path is None:
            return None
        key = path.relative_to(ROOT).as_posix()
        if key not in self.textures:
            texture = CoreImage(str(path), nocache=True, mipmap=True).texture
            left, top, right, bottom = self.bounds[key]
            self.textures[key] = texture.get_region(left, texture.height - bottom,
                                                   right - left, bottom - top)
        return self.textures[key]

    def clear(self):
        self.textures.clear()
