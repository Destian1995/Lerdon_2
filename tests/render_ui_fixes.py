"""Render the real fixed screens, including Android-density campaign geometry."""
import sys
import ast
import sqlite3
from pathlib import Path
from contextlib import closing
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from strategy_ui_fixture import *
from strategy_ui_fixture import __dict__ as fixture_globals
from test_frontend_ui import frontend_classes, settle
from kivy.metrics import Metrics
from kivy.uix.checkbox import CheckBox
from window_theme import install_window_theme
from event_ticker import EventQueue
from ai_models.advisor_view import AdvisorView

install_window_theme()
classes = frontend_classes()
db = sqlite3.connect(':memory:')
with closing(sqlite3.connect(f'file:{(ROOT / "game_data.db").as_posix()}?mode=ro', uri=True)) as source:
    source.backup(db)
for index, faction in enumerate(('Север', 'Эльфы', 'Адепты', 'Вампиры', 'Элины')):
    db.execute('INSERT INTO cities(name,faction,coordinates) VALUES (?,?,?)',
               (f'Test {index}', faction, str([index * 100, 100])))
db.commit()

def capture(name):
    settle()
    target = ROOT / 'assets' / name
    saved = Path(Window.screenshot(name=str(target)))
    if saved != target:
        saved.replace(target)

Metrics.density, Metrics.fontscale = 2, 1.2
Window.size = (1280, 576)
settle()
with patch('kivy.app.App.get_running_app', return_value=SimpleNamespace(selected_kingdom=None)):
    setup = classes['KingdomSelectionWidget'](db)
    Window.add_widget(setup)
    capture('frontend-campaign-android-fixed.png')
    Window.remove_widget(setup)
rating = classes['DossierScreen'](db)
Window.add_widget(rating)
capture('frontend-rating-android-fixed.png')
Window.remove_widget(rating)
Window.unbind(on_resize=rating.on_window_resize)
Metrics.density, Metrics.fontscale = 1, 1
Window.size = (640, 360)
settle()
background = Image(source='files/map/generate/map_1.png', allow_stretch=True, keep_ratio=False)
Window.add_widget(background)
host = FloatLayout()
Window.add_widget(host)
advisor = AdvisorView('Север', db)
host.add_widget(advisor)
settle()
next(iter(advisor.diplomacy_chat._faction_buttons.values())).dispatch('on_press')
capture('frontend-chat-selected-fixed.png')
advisor.close_window(None)
settle()
capture('frontend-chat-closed-fixed.png')

tree = ast.parse((ROOT / 'economic.py').read_text(encoding='utf-8'))
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'open_trade_popup')
namespace = dict(fixture_globals, platform='android', CheckBox=CheckBox)
exec(compile(ast.Module(body=[fn], type_ignores=[]), 'economic.py', 'exec'), namespace)
game = SimpleNamespace(get_resources=lambda: None, generate_raw_material_price=lambda: None,
                       current_raw_material_price=200, _get_trade_bonus=lambda: 1,
                       resources={'Кроны': 10000, 'Кристаллы': 1000},
                       get_available_raw_material_lots=lambda: 10, raw_material_price_history=[180, 200])
namespace[fn.name](game)
capture('frontend-market-fixed.png')
for child in list(Window.children):
    if isinstance(child, Popup):
        child.dismiss(animation=False)
screen = FloatLayout()
screen.resource_box = SimpleNamespace(width=dp(136))
host.add_widget(screen)
events = EventQueue(screen)
events.push('Благодарные жители организовали ополчение. Ваша армия пополнилась добровольцами.', 'passive')
capture('frontend-event-ticker-fixed.png')
Window.remove_widget(host)
Window.remove_widget(background)
db.close()
print('Rendered actual Android-density campaign/rating, selected/closed AI chat, market and ticker')
