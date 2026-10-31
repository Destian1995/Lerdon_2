"""Capture real release 7.0 dialogs without using the player's saved campaign."""
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dialog700_fixture import market, taxes, equipment, council_event
from test_dialog_layout import settle
from strategy_ui_fixture import Window, Image, FloatLayout, city_fixture
from kivy.metrics import Metrics
from kivy.uix.popup import Popup
from recruitment_ui import RecruitmentSession
from window_theme import install_window_theme

install_window_theme()
folder = ROOT / '.release' / 'previews-7.0.0'
folder.mkdir(exist_ok=True)
background = Image(source='files/map/generate/map_1.png', fit_mode='cover')
Window.add_widget(background)


def capture(name):
    settle()
    target = folder / (name + '.png')
    saved = Path(Window.screenshot(name=str(target)))
    if saved != target:
        saved.replace(target)


for width, height, density, scale, suffix in ((1280, 576, 1, 1, 'wide'), (640, 360, 1, 1, 'phone'),
                                             (1280, 576, 2, 1.2, 'android')):
    Metrics.density, Metrics.fontscale = density, scale
    Window.size = (width, height)
    settle()
    for name, show in (('equipment', equipment), ('market', market), ('taxes', taxes), ('council', council_event)):
        db = show()
        capture(name + '-' + suffix)
        for popup in list(Window.children):
            if isinstance(popup, Popup):
                popup.dismiss(animation=False)
        if db:
            db.close()
    units = {'Паладины': dict(image='files/army/adepts/paladin.jpg', cost=(150, 2),
                 stats={'Класс юнита': '1 класс', 'Урон': 145, 'Защита': 320,
                        'Живучесть': 210, 'Потребление Кристаллов': 5})}
    host = FloatLayout()
    Window.add_widget(host)
    hire = SimpleNamespace(class_faction=SimpleNamespace(get_resource_now=lambda name: 50000))
    session = RecruitmentSession('Адепты', hire, units, lambda *args: None)
    host.add_widget(session)
    session.open()
    capture('recruitment-' + suffix)
    session.release()
    Window.remove_widget(host)
    owner, db = city_fixture(populated=True)
    owner._show_unit_stats_popup('Стражи рассвета', 145, 120, 240, 4500, '1', 'files/army/adepts/paladin.jpg')
    capture('garrison-' + suffix)
    for popup in list(Window.children):
        if isinstance(popup, Popup):
            popup.dismiss(animation=False)
    db.close()
Window.remove_widget(background)
print('Rendered 18 production dialog previews')
