"""Preview the actual news ribbon over the game HUD, using isolated fixtures."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import Window, ROOT, FloatLayout, Image, dp, hud_fixture, cleanup_hud
from test_frontend_ui import settle
from event_ticker import EventQueue
from PIL import Image as PILImage

Window.size = (1000, 600)
root = FloatLayout()
root.add_widget(Image(source='files/map/generate/map_1.png', fit_mode='fill'))
hud = hud_fixture()
root.add_widget(hud)
Window.add_widget(root)
settle()
queue = EventQueue(hud)
queue.push('Рост торговли', changes=[('Кроны', 1200)])
queue.push('Саботаж на фабриках', changes=[('Кристаллы', -400)])
queue.push('Последствия решения', changes=[('Население', 500), ('Кроны', -200)])
settle()
ticker = queue.active
ticker.cancel()
ticker.offset = -dp(10)
ticker.layout_text()
frames = []
for frame in range(60):
    ticker.advance(1 / 12)
    texture = root.export_as_image().texture
    frames.append(PILImage.frombytes('RGBA', texture.size, texture.pixels).convert('RGB'))
frames[0].save(ROOT / 'assets' / 'event-news-ribbon.png')
palette = frames[0].quantize(colors=128)
indexed = [frame.quantize(palette=palette, dither=PILImage.Dither.NONE) for frame in frames]
indexed[0].save(ROOT / 'assets' / 'event-news-ribbon.gif', save_all=True,
                append_images=indexed[1:], duration=85, loop=0, optimize=True)
queue.active.finish()
cleanup_hud(hud)
Window.remove_widget(root)
print('Saved event-news-ribbon.png and event-news-ribbon.gif')
