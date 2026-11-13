"""Render the real five realm maps against disposable in-memory campaigns."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from otherworld_ui import OtherworldMap
from otherworld_themes import THEMES
from window_theme import install_window_theme
from kivy.metrics import Metrics
import otherworlds as worlds

out=Path('.release/mirror-depth');out.mkdir(parents=True,exist_ok=True)
install_window_theme();Metrics.density=1
for faction,theme in THEMES.items():
    db=fixture();worlds.enter(db,'Север','Home')
    for table in ('portal_parties','resources','turn_check_move'):
        db.execute('UPDATE '+table+' SET faction=?',(faction,))
    owner=OtherworldMap(db,faction);owner.open(animation=False)
    for size,name in (((1200,800),'desktop'),((640,360),'phone')):
        Window.size=size;settle();owner.fit();settle()
        owner.map.draw();owner.map.effects.update(.1);settle()
        owner.export_to_png(str(out/(theme['key']+'-'+name+'.png')))
    owner.dismiss(animation=False);settle();db.close()
print(out.resolve())
