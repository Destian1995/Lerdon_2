"""Render real map sprites and an animated review clip without editing assets."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from kivy.metrics import Metrics
from otherworld_ui import OtherworldMap
from otherworld_effects import LIGHTNING_INTERVAL
from PIL import Image
import otherworlds as w

out=Path('assets/mirror-sprites');out.mkdir(exist_ok=True)
Metrics.density=Metrics.fontscale=1;Window.size=(960,540);settle()

def screen(path):
    saved=Path(Window.screenshot(name=str(path)))
    if saved!=path:saved.replace(path)

for faction,key in (('Вампиры','vampires'),('Эльфы','elves'),('Север','north'),('Адепты','adepts'),('Элины','elines')):
    db=fixture()
    db.execute('UPDATE cities SET faction=? WHERE name=?',(faction,'Home'))
    db.execute("UPDATE units SET faction=? WHERE unit_name IN ('troop1','Hero')",(faction,))
    db.execute("UPDATE resources SET faction=? WHERE faction='Север'",(faction,))
    db.execute("UPDATE turn_check_move SET faction=? WHERE faction='Север'",(faction,))
    w.enter(db,faction,'Home')
    owner=OtherworldMap(db,faction);owner.open(animation=False);settle()
    effects=owner.map.effects;effects.stop()
    effects.age=.3 if key=='vampires' else 3.2;effects.update(0)
    Window.canvas.ask_update();Window.dispatch('on_draw');Window.flip()
    screen(out/(key+'.png'))
    # Capture full UI renders, then package those screenshots as a GIF preview.
    # The generated sprite PNG files themselves are never processed or changed.
    if key=='vampires':
        frames=[]
        frame_count=round(len(effects.lightning)*LIGHTNING_INTERVAL*8)
        for i in range(frame_count):
            effects.age=i/8;effects.update(0)
            Window.canvas.ask_update();Window.dispatch('on_draw');Window.flip()
            path=out/('frame-'+str(i)+'.png');screen(path)
            frames.append(Image.open(path).convert('RGB'))
        frames[0].save(out/'vampires-animation.gif',save_all=True,append_images=frames[1:],
                       duration=125,loop=0,optimize=False)
        for frame in frames:frame.close()
        for i in range(frame_count):(out/('frame-'+str(i)+'.png')).unlink()
    owner.dismiss(animation=False);settle();db.close()
print('Rendered painted weather for five factions and the vampire animation')
