"""Animated previews of the actual map renderer, using disposable saves."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from otherworld_ui import OtherworldMap
from kivy.base import EventLoop
from kivy.metrics import Metrics
from window_theme import install_window_theme
import otherworlds as worlds

out=Path('.release/mirror-motion');out.mkdir(parents=True,exist_ok=True)
install_window_theme();Metrics.density=1;Window.size=(640,360);settle()
for faction,key in (('Эльфы','elves'),('Адепты','adepts')):
    db=fixture();worlds.enter(db,'Север','Home')
    for table in ('portal_parties','resources','turn_check_move'):
        db.execute('UPDATE '+table+' SET faction=?',(faction,))
    owner=OtherworldMap(db,faction);owner.open(animation=False);settle()
    owner.map.effects.stop();owner.fit();settle()
    frames=[];palette=None
    for frame in range(40):
        owner.map.effects.age=4+frame*.15
        owner.map.effects.update(0)
        owner.map.canvas.ask_update();EventLoop.idle()
        core=owner.export_as_image();texture=core.texture
        image=Image.frombytes('RGBA',tuple(map(int,texture.size)),texture.pixels)
        image=image.convert('RGB')
        if palette is None:palette=image.quantize(colors=256)
        frames.append(image.quantize(palette=palette,dither=Image.Dither.NONE))
        if frame==20:owner.export_to_png(str(out/(key+'-frame.png')))
    frames[0].save(out/(key+'.gif'),save_all=True,append_images=frames[1:],
                   duration=150,loop=0,optimize=True)
    owner.dismiss(animation=False);settle();db.close()
    print(out/(key+'.gif'))
