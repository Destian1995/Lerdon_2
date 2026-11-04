"""Render the live-map HUD, army gesture and stack picker at phone sizes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from test_map_zoom import Touch
from otherworld_ui import OtherworldMap
from mirror_army_transfer import send_from_map
import otherworlds as w

out=Path('assets/mirror-life');out.mkdir(exist_ok=True)
def shot(name):
    settle()
    target=out/(name+'.png');saved=Path(Window.screenshot(name=str(target)))
    if saved!=target:saved.replace(target)

for size,name in (((640,360),'phone'),((392,844),'portrait')):
    Window.size=size;settle()
    db=fixture();db.execute("INSERT INTO resources VALUES('Север','Рабочие',12500)")
    w.enter(db,'Север','Home')
    owner=OtherworldMap(db,'Север');owner.open(animation=False);settle()
    owner.map.effects.age=8;owner.map.effects.update(0)
    shot('map-'+name)
    first=owner.map.nodes[0]
    dest=next(c for c in owner.map.nodes if c['id']==db.execute('SELECT city2 FROM portal_roads WHERE city1=1 LIMIT 1').fetchone()[0])
    t=Touch(*owner.map.point(first['x'],first['y']))
    owner.map.army_drag.down(t);owner.map.army_drag.activate()
    t.pos=owner.map.point(dest['x'],dest['y']);owner.map.army_drag.move(t)
    shot('drag-'+name);owner.map.army_drag.cancel()
    picker=send_from_map(owner,first['id'],dest['id']);shot('picker-'+name)
    picker.dismiss(animation=False);owner.dismiss(animation=False);settle();db.close()
