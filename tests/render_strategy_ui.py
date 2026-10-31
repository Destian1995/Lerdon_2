"""Generate review images from actual city/HUD code, without reading a game save."""
import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from strategy_ui_fixture import city_fixture, hud_fixture, cleanup_hud, Window, Image, Clock
from kivy.base import EventLoop


def screenshot(name):
    target = ROOT / 'assets' / name
    captured = Path(Window.screenshot(name=str(target)))
    if captured != target:
        captured.replace(target)


Window.size = (1280, 720)
background = Image(source='files/map/generate/map_1.png', size=Window.size,
                   allow_stretch=True, keep_ratio=False)
Window.add_widget(background)
hud = hud_fixture()
Window.add_widget(hud)
for _ in range(5):
    EventLoop.idle()
screenshot('strategy-hud.png')
popup, db = city_fixture(populated=True)
popup.open(animation=False)
for _ in range(5):
    EventLoop.idle()
screenshot('strategy-city.png')
popup.dismiss(animation=False)
db.close()
Window.size = (640, 360)
for _ in range(8):
    time.sleep(0.03)
    EventLoop.idle()
popup, db = city_fixture()
popup.open(animation=False)
for _ in range(5):
    EventLoop.idle()
print('Phone viewport:', Window.size, 'Popup:', popup.size, 'City body:', popup.city_columns.size)
screenshot('strategy-city-phone.png')
popup.city_columns.select(1)
for _ in range(3):
    EventLoop.idle()
screenshot('strategy-city-phone-buildings.png')
popup.dismiss(animation=False)
db.close()
cleanup_hud(hud)
Window.remove_widget(hud)
Window.remove_widget(background)
print('Rendered HUD, city and compact phone previews')
