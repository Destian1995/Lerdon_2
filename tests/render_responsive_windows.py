"""Render the real troop, campaign, diplomacy and event widgets at phone sizes."""
import ast
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from strategy_ui_fixture import *
from strategy_ui_fixture import __dict__ as fixture_globals
from kivy.base import EventLoop
from kivy.metrics import Metrics
from window_theme import install_window_theme
from troop_ui import show_troop_selection
from results_ui import show_campaign_results

install_window_theme()

def settle():
    for _ in range(15):
        time.sleep(0.018)
        EventLoop.idle()

def capture(name):
    settle()
    target = ROOT / 'assets' / name
    path = Path(Window.screenshot(name=str(target)))
    if path != target:
        path.replace(target)

Window.size = (640, 360)
settle()
background = Image(source='files/map/generate/map_1.png', allow_stretch=True, keep_ratio=False)
Window.add_widget(background)
owner, db = city_fixture()
owner.create_troop_group = lambda *args: None
owner.move_selected_group_to_city = lambda *args: None
troops = [('Лирандор', 'Паладины', 19800000, 'files/army/adepts/paladin.jpg'),
          ('Миреллия', 'Валерия', 1, 'files/army/elfs/valery.jpg'),
          ('Аргенвилль', 'Королевские лучники', 1500000, 'files/army/elfs/archer.jpg')]
popup = show_troop_selection(owner, troops)
capture('responsive-troops-phone.png')
Window.size = (360, 640)
capture('responsive-troops-portrait.png')
popup.dismiss(animation=False)

Window.size = (640, 360)
Metrics.fontscale = 1.4
settle()
result_owner = SimpleNamespace(exit_to_main_menu=lambda *_: None)
results = [dict(faction=faction, units_combat=123000000, units_destroyed=90000000,
                units_killed=100000000, army_efficiency_ratio=1.5) for faction in ('Адепты', 'Эльфы')]
popup = show_campaign_results(result_owner, 'Итоги кампании', 'Победа! Ваше королевство объединило эти земли.',
                              results, (0.9, 0.8, 0.5, 1))
capture('responsive-results-large-font.png')
popup.dismiss(animation=False)

tree = ast.parse((ROOT / 'event_manager.py').read_text(encoding='utf-8'))
function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'show_event_active_popup')
namespace = dict(fixture_globals, platform='android')
exec(compile(ast.Module(body=[function], type_ignores=[]), 'event_manager.py', 'exec'), namespace)
event_owner = SimpleNamespace()
namespace[function.name](event_owner, 'В столице собрались послы соседних королевств. Они предлагают провести общий праздник, '
                         'укрепить дружбу и открыть новые торговые пути.',
                         'Поддержать послов и устроить праздник', 'Отложить переговоры до следующего сезона', {})
popup = next(w for w in Window.children if isinstance(w, Popup))
capture('responsive-event-large-font.png')
popup.dismiss(animation=False)

tree = ast.parse((ROOT / 'ui_components.py').read_text(encoding='utf-8'))
cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'DiplomacyMessagePopup')
namespace = dict(fixture_globals)
exec(compile(ast.Module(body=[cls], type_ignores=[]), 'ui_components.py', 'exec'), namespace)
overlay = namespace[cls.name]('Эльфы', '[СОЮЗ] Наши народы могут защитить эти земли вместе. Предлагаем заключить союз '
                             'и открыть безопасные пути между нашими городами.', 'alliance')
Window.add_widget(overlay)
capture('responsive-diplomacy-large-font.png')
overlay._cleanup()
Metrics.fontscale = 1
db.close()
Window.remove_widget(background)
print('Rendered troop cards, campaign results, event and diplomatic message')
