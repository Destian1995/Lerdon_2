"""Review real town layers and the construction window without opening a player's save."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import Window,city_fixture
from test_dialog_layout import settle
from kivy.metrics import Metrics
from kivy.uix.popup import Popup
from town_art import THEMES
from city_construction import CATALOG
from town_scene import TownScene
from window_theme import install_window_theme
from PIL import Image,ImageDraw

install_window_theme()
out=Path('.release/town-review');out.mkdir(exist_ok=True)
for faction,key in THEMES.items():
    Window.size=(1280,720);Metrics.density=Metrics.fontscale=1;settle()
    owner,db=city_fixture(owner=faction)
    db.execute('DELETE FROM buildings')
    db.executemany('INSERT INTO buildings VALUES(?,?,?,1)',[(owner.city_name,faction,n) for n in CATALOG])
    db.executescript("CREATE TABLE resources(faction,resource_type,amount); INSERT INTO resources VALUES('Адепты','Кроны',500000);")
    db.commit();owner.load_buildings();owner.open(animation=False);settle()
    town=owner._open_build_menu();settle();town.choose('Кузница');settle()
    town.export_to_png(str(out/(key+'-window.png')))
    town.scene.export_to_png(str(out/(key+'-scene.png')))
    town.dismiss(animation=False);owner.dismiss(animation=False);settle();db.close()

board=Image.new('RGB',(1280,768),(15,21,28));draw=ImageDraw.Draw(board)
for index,(faction,key) in enumerate(THEMES.items()):
    scene=Image.open(out/(key+'-scene.png')).convert('RGB');scene.thumbnail((320,340))
    x=index%4*320;y=index//4*384
    board.paste(scene,(x,y));draw.text((x+8,y+352),key,fill='white')
board.save(out/'town-gallery.jpg',quality=92)
print(out)
