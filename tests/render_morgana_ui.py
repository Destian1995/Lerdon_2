"""Render the actual guardian card and tax dialog plus representative portrait frames."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from strategy_ui_fixture import Window, Image, FloatLayout, city_fixture, dp
from dialog700_fixture import taxes
from test_dialog_layout import settle
from kivy.metrics import Metrics
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from strategy_ui import surface, text_label, INK
from window_theme import install_window_theme
from unit_updates import MORGANA_IMAGE

install_window_theme()
folder = ROOT / '.release' / 'previews-7.0.2'
folder.mkdir(exist_ok=True)
background = Image(source='files/map/generate/map_1.png', fit_mode='cover')
Window.add_widget(background)


def capture(name):
    settle()
    target = folder / (name + '.png')
    saved = Path(Window.screenshot(name=str(target)))
    if saved != target:
        saved.replace(target)


for size, density, scale, suffix in (((1280, 576), 1, 1, 'wide'), ((640, 360), 1, 1, 'phone'),
                                    ((1280, 576), 2, 1.2, 'android')):
    Metrics.density, Metrics.fontscale = density, scale
    Window.size = size
    settle()
    owner, db = city_fixture(owner='Нежить')
    owner._show_unit_stats_popup('Моргана', 208, 800, 50, 1, '2', MORGANA_IMAGE)
    capture('morgana-' + suffix)
    for widget in list(Window.children):
        if isinstance(widget, Popup):
            widget.dismiss(animation=False)
    db.close()
    taxes()
    capture('taxes-' + suffix)
    for widget in list(Window.children):
        if isinstance(widget, Popup):
            widget.dismiss(animation=False)

Metrics.density, Metrics.fontscale = 1, 1
Window.size = (1280, 576)
gallery = surface(BoxLayout(padding=dp(24), spacing=dp(24)), INK)
for name, source in (('Моргана', MORGANA_IMAGE), ('Герой Севера', 'files/army/people/vlad.jpg'),
                     ('Советник', 'files/sov/adept.jpg'), ('Фракция', 'files/buildings/elfs.png')):
    cell = BoxLayout(orientation='vertical', spacing=dp(10))
    cell.add_widget(Image(source=source, fit_mode='contain'))
    cell.add_widget(text_label(name, 18, size_hint_y=None, height=dp(36)))
    gallery.add_widget(cell)
Window.add_widget(gallery)
capture('portrait-frames')
Window.remove_widget(gallery)
Window.remove_widget(background)
print('Rendered Morgana, centered taxes and unit/hero/faction frames')
