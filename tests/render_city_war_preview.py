"""Render real map effects and assets without importing main or accessing a save."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update(KIVY_NO_ARGS='1', KIVY_NO_FILELOG='1', KIVY_NO_CONFIG='1',
                  KIVY_METRICS_DENSITY='1', KIVY_METRICS_FONTSCALE='1')
from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
Config.set('graphics', 'width', '1200')
Config.set('graphics', 'height', '800')
from kivy.base import EventLoop
from kivy.core.window import Window
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from city_war import CityWarState
from map_atmosphere import MapAtmosphere


root = FloatLayout(size=Window.size)
root.add_widget(Image(source='files/map/generate/map_1.png', size_hint=(1, 1),
                      allow_stretch=True, keep_ratio=False))
cities = [('Мирный город', 200, 420, 'Эльфы'),
          ('После боя', 430, 420, 'Север'),
          ('Разрушенный город', 680, 420, 'Север'),
          ('Некрополь', 930, 420, 'Нежить')]
sprites = ['elfs', 'default', 'ruined/town', 'ruined/undead']
for (name, x, y, faction), sprite in zip(cities, sprites):
    root.add_widget(Image(source=f'files/buildings/{sprite}.png', size_hint=(None, None),
                          pos=(x, y), size=(77, 77), mipmap=True))
    root.add_widget(Label(text=name, size_hint=(None, None), pos=(x - 65, y - 38),
                          size=(210, 36), bold=True, font_size=18,
                          outline_width=2, outline_color=(0, 0, 0, 1)))
layer = MapAtmosphere()
layer.configure((0, 0), 1)
root.add_widget(layer)
layer.stop()
states = {name: CityWarState(name, 1, 'battle', 5, faction, i >= 2, 7, None)
          for i, (name, x, y, faction) in enumerate(cities) if i > 0}
layer.city_effects.sync(cities, states, 5)
layer.city_effects.play('Мирный город', 'peace', 'Эльфы')
layer.city_effects.play('После боя', 'battle_capture', 'Север')
Window.add_widget(root)
for _ in range(25):
    layer.update(0.04)
    EventLoop.idle()
output = ROOT / 'assets/city-war-preview.png'
root.export_as_image().save(str(output))
Window.remove_widget(root)
layer.stop()
print(output)
