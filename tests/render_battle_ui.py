"""Export real battle widgets and a short replay GIF without opening a game DB."""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update(KIVY_NO_ARGS='1', KIVY_NO_CONFIG='1', KIVY_NO_FILELOG='1',
                  KIVY_METRICS_DENSITY='1', KIVY_METRICS_FONTSCALE='1')
from kivy.config import Config
Config.set('graphics', 'window_state', 'hidden')
from kivy.base import EventLoop
from kivy.core.window import Window
from kivy.uix.image import Image
from PIL import Image as PILImage
from battle_ui import BattleViewer, BattleReport
from window_theme import install_window_theme

install_window_theme()

def settle():
    for _ in range(6):
        time.sleep(0.025)
        EventLoop.idle()

def screenshot(path):
    captured = Path(Window.screenshot(name=str(path)))
    if captured != path:
        captured.replace(path)

Window.size = (1000, 600)
settle()
background = Image(source='files/map/generate/map_1.png', allow_stretch=True, keep_ratio=False)
Window.add_widget(background)
rounds = [dict(round=i + 1, atk_max=48000, def_max=54000,
               atk_total=48000 - (i + 1) * 2200, def_total=54000 - (i + 1) * 6000,
               atk_crits=1 if i in (1, 4, 7) else 0, def_crits=1 if i in (2, 5) else 0,
               heroes=[dict(side='def', unit_name='Валерия')] if i == 7 else []) for i in range(9)]
view = BattleViewer(rounds, 'Адепты', 'Эльфы', 'attacker', 'Адепты', 'Виндгар', 'Ориона',
                    attacker_image='files/army/adepts/paladin.jpg', defender_image='files/army/elfs/valery.jpg')
view.open(animation=False)
settle()
view.clock_event.cancel()
view.clock_event = None
for _ in range(10):
    view.update(0.1)
EventLoop.idle()
screenshot(ROOT / 'assets/battle-replay.png')
Window.size = (640, 360)
settle()
screenshot(ROOT / 'assets/battle-replay-phone.png')
frames = []
with tempfile.TemporaryDirectory() as folder:
    for i in range(42):
        view.update(0.10)
        EventLoop.idle()
        path = Path(folder) / f'frame-{i}.png'
        screenshot(path)
        with PILImage.open(path) as image:
            frames.append(image.convert('RGB').copy())
    frames[0].save(ROOT / 'assets/battle-replay.gif', save_all=True,
                   append_images=frames[1:], duration=100, loop=0, optimize=True)
view.reveal_result()
EventLoop.idle()
screenshot(ROOT / 'assets/battle-victory-phone.png')
view.dismiss(animation=False)
rows = [dict(unit_name='Паладины', initial_count=48000, final_count=28200,
             losses=19800, healed=0, net_losses=19800, side='attacking', result='Победа', city='Ориона',
             unit_image='files/army/adepts/paladin.jpg'),
        dict(unit_name='Лучники', initial_count=53999, final_count=0, losses=53999, healed=0,
             side='defending', city='Ориона', unit_image='files/army/elfs/archer.jpg'),
        dict(unit_name='Валерия', initial_count=1, final_count=0, losses=1, healed=0,
             side='defending', city='Ориона', unit_image='files/army/elfs/valery.jpg')]
report = BattleReport(rows, 'Адепты', 'Адепты', 'Эльфы', ['[color=#75D89A]Оборона противника сломлена[/color]'])
report.open(animation=False)
settle()
screenshot(ROOT / 'assets/battle-report-phone.png')
Window.size = (1000, 600)
settle()
screenshot(ROOT / 'assets/battle-report.png')
report.dismiss(animation=False)
Window.remove_widget(background)
print('Rendered replay, victory, report and animated preview')
