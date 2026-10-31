"""Render real recruitment/tax/city windows with the production Popup hook."""
import ast
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from strategy_ui_fixture import *
from kivy.base import EventLoop
from recruitment_ui import RecruitmentSession
from window_theme import install_window_theme

install_window_theme()

def settle():
    for _ in range(10):
        time.sleep(0.025)
        EventLoop.idle()

def screenshot(name):
    target = ROOT / 'assets' / name
    captured = Path(Window.screenshot(name=str(target)))
    if captured != target:
        captured.replace(target)

Window.size = (1000, 600)
settle()
background = Image(source='files/map/generate/map_1.png', allow_stretch=True, keep_ratio=False)
Window.add_widget(background)
popup, db = city_fixture(populated=True)
popup.open(animation=False)
settle()
screenshot('unified-city.png')
popup.dismiss(animation=False)
db.close()
area = FloatLayout()
Window.add_widget(area)
units = {}
for name, image, cls, cost in [('Паладины', 'paladin', 1, (150, 2)), ('Агилар', 'agilar', 2, (25000, 1))]:
    units[name] = dict(image=f'files/army/adepts/{image}.jpg', cost=cost,
                       stats={'Класс юнита': f'{cls} класс', 'Урон': 145, 'Защита': 320,
                              'Живучесть': 210, 'Потребление Кристаллов': 5})
hire = SimpleNamespace(class_faction=SimpleNamespace(get_resource_now=lambda name: 50000))
session = RecruitmentSession('Адепты', hire, units, lambda *args: None)
area.add_widget(session)
session.open()
settle()
screenshot('unified-recruitment.png')
Window.size = (640, 360)
settle()
screenshot('unified-recruitment-phone.png')
session.release()
Window.size = (1000, 600)
settle()
tree = ast.parse((ROOT / 'economic.py').read_text(encoding='utf-8'))
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'open_tax_popup')
namespace = dict(globals(), platform='android')
exec(compile(ast.Module(body=[function], type_ignores=[]), 'economic.py', 'exec'), namespace)
faction = SimpleNamespace(current_tax_rate='15%', tax_set=False, tax_effect=lambda rate: 0,
                          set_taxes=lambda rate: None, apply_tax_effect=lambda rate: None)
namespace['open_tax_popup'](faction)
settle()
screenshot('unified-tax.png')
for child in list(Window.children):
    if isinstance(child, Popup):
        child.dismiss(animation=False)
Window.remove_widget(area)
Window.remove_widget(background)
print('Rendered city, recruitment, phone recruitment and real tax dialog')
