"""Render the real Mirror map while its main-map AI overlay reports progress."""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from kivy.metrics import Metrics
from otherworld_ui import OtherworldMap
import otherworlds as worlds

out=Path('assets/mirror-turn');out.mkdir(exist_ok=True)
for size,density,name in (((640,360),1,'phone'),((1280,576),2,'android'),((392,844),1,'portrait')):
    Window.size=size;Metrics.density=density;settle()
    db=fixture();worlds.enter(db,'Север','Home')
    screen=SimpleNamespace(conn=db,selected_faction='Север',_turn_overlay=SimpleNamespace(
        parent=object(),_bar_progress=.6,_status_label=SimpleNamespace(text='Ход фракции: Эльфы')))
    with patch.dict(sys.modules,game_process=SimpleNamespace(_active_game_screen=screen)):
        popup=OtherworldMap(db,'Север');popup.open(animation=False);settle();settle()
        target=out/(name+'.png');saved=Path(Window.screenshot(name=str(target)))
        if saved!=target:saved.replace(target)
        popup.dismiss(animation=False);settle()
    db.close()
