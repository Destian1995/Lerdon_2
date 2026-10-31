import sys
import sqlite3
import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from test_frontend_ui import frontend_classes, settle
from strategy_ui_fixture import *
from strategy_ui_fixture import __dict__ as fixture_globals
from window_theme import install_window_theme
install_window_theme()
classes = frontend_classes()
db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE diplomacies_default(faction1 TEXT)')
db.executemany('INSERT INTO diplomacies_default VALUES (?)', [(name,) for name in ('Север', 'Эльфы', 'Адепты', 'Вампиры', 'Элины')])

def capture(name):
    settle()
    target = ROOT / 'assets' / name
    saved = Path(Window.screenshot(name=str(target)))
    if saved != target:
        saved.replace(target)

Window.size = (1000, 600)
settle()
for cls, name in [('MenuWidget', 'frontend-menu'), ('KingdomSelectionWidget', 'frontend-campaign'),
                   ('TutorialFactionScreen', 'frontend-tutorial'), ('AuthorScreen', 'frontend-author')]:
    with patch('kivy.app.App.get_running_app', return_value=SimpleNamespace(selected_kingdom=None)):
        widget = classes[cls](db)
        Window.add_widget(widget)
        capture(name + '.png')
        Window.size = (640, 360)
        capture(name + '-phone.png')
        Window.remove_widget(widget)
        Window.size = (1000, 600)
        settle()
tree = ast.parse((ROOT / 'economic.py').read_text(encoding='utf-8'))
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'open_development_popup')
ns = dict(fixture_globals, platform='android')
exec(compile(ast.Module(body=[fn], type_ignores=[]), 'economic.py', 'exec'), ns)
faction = SimpleNamespace(auto_build_ratio=(1, 1), auto_build_enabled=False,
                          hospitals=12, factories=11, money_up=150000,
                          get_resource_now=lambda *_: 0, save_auto_build_settings=lambda: None,
                          calculate_potential_income=lambda: 0, faction='Север')
ns[fn.name](faction)
capture('development-restored.png')
for widget in list(Window.children):
    if isinstance(widget, Popup):
        widget.dismiss(animation=False)
db.close()
print('Rendered front-end pages and restored development labels')
