"""Render hero standards and smoking battle aftermath without accessing a save."""
import os
import ast
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update(KIVY_NO_ARGS='1', KIVY_NO_FILELOG='1', KIVY_NO_CONFIG='1',
                  KIVY_METRICS_DENSITY='1', KIVY_METRICS_FONTSCALE='1')
from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
Config.set('graphics', 'width', '1200')
Config.set('graphics', 'height', '800')
from kivy.core.image import Image as CoreImage
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle, Line, Ellipse, RoundedRectangle
from kivy.uix.widget import Widget
from PIL import Image as PILImage
from map_atmosphere import MapAtmosphere
from city_war import CityWarState

root = Widget(size=(1200, 800), size_hint=(None, None))
cities = [('Север', 180, 500, 'people'), ('Эльфы', 540, 500, 'elfs'),
          ('Вампиры', 900, 500, 'vampires'), ('Адепты', 180, 230, 'adepts'),
          ('Элины', 540, 230, 'poly'), ('Нежить', 900, 230, 'castle_death')]
with root.canvas:
    Color(1, 1, 1, 1)
    Rectangle(source='files/map/generate/map_1.png', pos=(0, 0), size=root.size)
    Color(.02, .025, .04, .28)
    Rectangle(pos=(0, 0), size=root.size)
    for name, x, y, sprite in cities:
        Color(1, 1, 1, 1)
        Rectangle(source=f'files/buildings/{sprite}.png', pos=(x, y), size=(77, 77))
        subtitle = 'После боя · ход 1 из 2' if name in ('Вампиры', 'Элины') else 'Герой в гарнизоне'
        label = CoreLabel(text=name + '\n' + subtitle, font_size=18,
                          color=(1, .94, .8, 1), halign='center',
                          outline_width=2, outline_color=(0, 0, 0, 1))
        label.refresh()
        Rectangle(texture=label.texture, pos=(x + 38 - label.texture.width / 2, y - 58),
                  size=label.texture.size)
layer = MapAtmosphere()
layer.configure((0, 0), 1)
root.add_widget(layer)
layer.stop()
# Render the real military overlay over the standards, as in the game.
tree = ast.parse((ROOT / 'game_process.py').read_text(encoding='utf-8'))
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GameScreen')
method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'draw_army_stars_on_map')
namespace = dict(globals())
exec(compile(ast.Module(body=[method], type_ignores=[]), 'game_process.py', 'exec'), namespace)
overlay = Widget()
root.add_widget(overlay)
host = SimpleNamespace(city_star_levels={name: (2, x, y, name, True, None, 0, False)
                                        for name, x, y, _ in cities},
                       _prev_star_levels=None, game_area=overlay, _check_file=lambda path: True)
namespace[method.name](host)
layer.city_effects.attach_standards(overlay)
states = {name: CityWarState(name, 1, 'battle', 5, name, False, 7, None)
          for name in ('Вампиры', 'Элины')}
layer.city_effects.sync([(name, x, y, name) for name, x, y, _ in cities], states, 5,
                        [(name, name) for name, *_ in cities])
frames = []
intensities = []
for frame in range(60):
    layer.update(1 / 12)
    rendered = root.export_as_image().texture
    frames.append(PILImage.frombytes('RGBA', rendered.size, rendered.pixels).convert('RGB'))
    intensities.append(sum(burst['intensity'] for burst in layer.city_effects.battle_clouds))
output = ROOT / 'assets'
peak = max(range(len(frames)), key=lambda index: intensities[index])
frames[peak].save(output / 'faction-standards.png')
palette = frames[peak].quantize(colors=128)
indexed = [frame.quantize(palette=palette, dither=PILImage.Dither.NONE) for frame in frames]
indexed[0].save(output / 'faction-standards.gif', save_all=True, append_images=indexed[1:],
                duration=85, loop=0, optimize=True)
layer.stop()
print('Saved faction-standards.png and faction-standards.gif')
