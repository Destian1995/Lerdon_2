"""Render real redesigned screens without opening the player's database."""
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import Window, ROOT
from test_frontend_ui import frontend_classes, settle
from dialog700_fixture import market
from development_ui import open_development
from kivy.metrics import Metrics
from kivy.uix.popup import Popup
from window_theme import install_window_theme

install_window_theme()
output = ROOT / 'assets' / 'mobile-redesign'
output.mkdir(exist_ok=True)
db = sqlite3.connect(':memory:')
db.execute('CREATE TABLE diplomacies_default(faction1 TEXT)')
db.executemany('INSERT INTO diplomacies_default VALUES (?)',
               [(name,) for name in ('Север', 'Эльфы', 'Адепты', 'Вампиры', 'Элины')])


def capture(name):
    settle()
    path = output / (name + '.png')
    saved = Path(Window.screenshot(name=str(path)))
    if saved != path:
        saved.replace(path)


for size, density, suffix in (((800, 600), 1, 'desktop'), ((1280, 576), 2, 'android'), ((640, 360), 1, 'phone'),
                              ((320, 568), 1, 'portrait')):
    Metrics.density, Metrics.fontscale = density, 1.2
    Window.size = size
    settle()
    with patch('kivy.app.App.get_running_app', return_value=SimpleNamespace(selected_kingdom=None)):
        campaign = frontend_classes()['KingdomSelectionWidget'](db)
        Window.add_widget(campaign)
        campaign.kingdom_button_widgets['Эльфы'].dispatch('on_release')
        capture('campaign-' + suffix)
        Window.remove_widget(campaign)
    faction = SimpleNamespace(auto_build_ratio=(2, 1), auto_build_enabled=True,
                              hospitals=12, factories=11, money_up=150000,
                              save_auto_build_settings=lambda: None)
    from test_unique_development import fixture as development_fixture
    development_db=development_fixture();faction.conn=development_db;faction.faction='Север'
    popup = open_development(faction, lambda *_: None)
    capture('development-' + suffix)
    popup.dismiss(animation=False)
    development_db.close()
    market()
    popup = next(w for w in Window.children if isinstance(w, Popup))
    capture('market-' + suffix)
    popup.dismiss(animation=False)
db.close()
