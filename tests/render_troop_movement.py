"""Render all three dust levels using the real road drawing and march layer."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import ROOT, Window, Widget, Color, Rectangle, Label
from test_frontend_ui import settle
from kivy.core.text import Label as CoreLabel
from map_roads import TransportNetwork, draw_transport_layer
from map_atmosphere import MapAtmosphere
from troop_movement import MarchRoute
from PIL import Image as PILImage
import math

Window.size = (1000, 600)
root = Widget(size_hint=(None, None), size=(1000, 600))
with root.canvas:
    Color(1, 1, 1, 1)
    Rectangle(source='files/map/generate/map_1.png', pos=(0, 0), size=root.size)
    Color(.015, .025, .035, .28)
    Rectangle(pos=(0, 0), size=root.size)
paths = []
for level, y in enumerate((440, 300, 160), 1):
    points = [(120 + i * 760 / 60, y + math.sin(i * math.pi / 30) * 22) for i in range(61)]
    paths.append((level * 2, level * 2 + 1, points))
root.canvas.add(draw_transport_layer(TransportNetwork(land=paths), 1))
with root.canvas:
    for level, (_, _, points) in enumerate(paths, 1):
        for x, y in (points[0], points[-1]):
            Color(1, 1, 1, 1)
            Rectangle(source='files/buildings/people.png', pos=(x - 32, y - 25), size=(64, 64))
        label = CoreLabel(text=f'Уровень {level} · ' + ('лёгкая пыль', 'средняя пыль', 'густая пыль')[level - 1],
                          font_size=18, bold=True, color=(1, .93, .77, 1),
                          outline_width=2, outline_color=(0, 0, 0, 1))
        label.refresh()
        Color(1, 1, 1, 1)
        Rectangle(texture=label.texture, pos=(360, points[0][1] + 45), size=label.texture.size)
layer = MapAtmosphere()
layer.configure((0, 0), 1, (1000, 600))
root.add_widget(layer)
Window.add_widget(root)
settle()
layer.stop()
layer.marches.play_batch([(lambda points=points: MarchRoute(points, [True] * (len(points) - 1)),
                          level, 'Север', level * 1000)
                         for level, (_, _, points) in enumerate(paths, 1)], lambda: None, lambda: None)
frames = []
for _ in range(60):
    layer.update(1 / 12)
    texture = root.export_as_image().texture
    frames.append(PILImage.frombytes('RGBA', texture.size, texture.pixels).convert('RGB'))
frames[28].save(ROOT / 'assets/troop-movement.png')
palette = frames[28].quantize(colors=128)
indexed = [frame.quantize(palette=palette, dither=PILImage.Dither.NONE) for frame in frames]
indexed[0].save(ROOT / 'assets/troop-movement.gif', save_all=True, append_images=indexed[1:],
                duration=85, loop=0, optimize=True)
Window.remove_widget(root)
layer.marches.cancel_all()
print('Rendered troop-movement.png and troop-movement.gif')
