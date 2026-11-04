"""Main HUD shortcut at desktop, phone and Android density with an isolated save."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import Window,Image,hud_fixture,cleanup_hud
from test_dialog_layout import settle
from test_otherworlds import fixture
from kivy.metrics import Metrics
from portal_shortcut_ui import PortalShortcut
import otherworlds as worlds

out=Path('assets/portal-shortcut');out.mkdir(exist_ok=True)
for size,density,name in (((1920,1080),1,'desktop'),((640,360),1,'phone'),((1280,576),2,'android'),((392,844),1,'portrait')):
    Window.size=size;Metrics.density=density;settle()
    db=fixture();worlds.enter(db,'Север','Home')
    background=Image(source='files/map/generate/map_1.png',fit_mode='contain',size=Window.size)
    Window.add_widget(background)
    host=hud_fixture();host.portal_shortcut.close()
    host.conn=db;host.selected_faction='Север';host.faction_label.text='Север'
    host.portal_shortcut=PortalShortcut(host)
    Window.add_widget(host);settle();host._hud_fit();host.portal_shortcut.refresh();settle()
    target=out/(name+'.png');saved=Path(Window.screenshot(name=str(target)))
    if saved!=target:saved.replace(target)
    cleanup_hud(host);Window.remove_widget(host);Window.remove_widget(background);db.close()
