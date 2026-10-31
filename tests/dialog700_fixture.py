"""Real dialog functions, isolated from the game's global SQLite connection."""
import ast
import os
import sqlite3
from types import SimpleNamespace

from strategy_ui_fixture import *
from strategy_ui_fixture import __dict__ as base
from kivy.uix.checkbox import CheckBox
from kivy.uix.spinner import Spinner


def function(file, name, **overrides):
    tree = ast.parse((ROOT / file).read_text(encoding='utf-8'))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    namespace = dict(base, os=os, platform='android', CheckBox=CheckBox, Spinner=Spinner)
    namespace.update(overrides)
    exec(compile(ast.Module(body=[node], type_ignores=[]), file, 'exec'), namespace)
    return namespace[name]


def market(calls=None):
    game = SimpleNamespace(get_resources=lambda: None, generate_raw_material_price=lambda: None,
        current_raw_material_price=120, _get_trade_bonus=lambda: 1,
        resources={'Кроны': 20000, 'Кристаллы': 10000},
        get_available_raw_material_lots=lambda: 100, raw_material_price_history=[110, 120])
    function('economic.py', 'open_trade_popup',
             handle_trade=lambda *args: calls.append(args) if calls is not None else None)(game)


def taxes(calls=None):
    faction = SimpleNamespace(current_tax_rate='15%', tax_set=False, tax_effect=lambda rate: 10 - rate,
        set_taxes=lambda rate: calls.append(rate) if calls is not None else None,
        apply_tax_effect=lambda rate: None)
    function('economic.py', 'open_tax_popup')(faction)


def equipment():
    artifacts = [dict(id=i, name=name, attack=20, defense=15, health=0, cost=1500 * i,
                      artifact_type=(i-1) % 5, is_created=0, season_name='Весна, Лето',
                      image_url='files/pict/hire/sword.png')
                 for i, name in enumerate(('Клинок рассвета', 'Корона мудрости', 'Сапоги странника',
                                            'Доспех защитника', 'Звезда севера'), 1)]
    faction = SimpleNamespace(resources={'Кроны': 50000})
    function('heroes.py', 'open_artifacts_popup',
        load_artifacts_from_db=lambda f: artifacts,
        load_hero_equipment_from_db=lambda f: {'0': {'id': 1}},
        load_hero_image_from_db=lambda f: 'files/army/people/vlad.jpg',
        load_hero_stats_from_db=lambda f: dict(attack=237, defense=146, durability=400),
        format_artifact_description=lambda art: 'Атака +20%, защита +15%\nВесна, Лето',
        style_rounded_spinner=lambda *args, **kwargs: None,
        style_rounded_button=lambda *args, **kwargs: None)(faction, None)


def council_event(calls=None):
    db = sqlite3.connect(':memory:')
    db.execute('CREATE TABLE nobles(id, name, ideology, status)')
    db.execute('INSERT INTO nobles VALUES (1,"Леонид","greed","active")')
    cash = SimpleNamespace(load_resources=lambda: None, resources={'Кроны': 50000},
                           deduct_resources=lambda value: calls.append(value) if calls is not None else True)
    function('nobles.py', 'show_event_popup',
        UIStyles=SimpleNamespace(is_android=lambda: True),
        get_event_type_by_season=lambda s: 'Рыцарский турнир',
        get_season_name_by_index=lambda s: 'Осень',
        calculate_event_cost=lambda s: 18200,
        get_noble_traits=lambda s: dict(type='greed', demand=3100))(db, 'Север', 3, lambda: None, cash)
    return db


def crafting():
    from create_artifacts import workshop
    workshop(SimpleNamespace(money=100000, faction='Север'), None)
