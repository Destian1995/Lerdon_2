import sys,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from kivy.metrics import Metrics
from otherworld_ui import OtherworldMap,ForeignCityPopup
from otherworld_quest_ui import QuestJournal
from window_theme import install_window_theme
import otherworlds as w
import otherworld_quests as q

out=Path('assets/mirror-architecture');out.mkdir(exist_ok=True)
install_window_theme()
def shot(name):
    settle();settle()
    target=out/(name+'.png');saved=Path(Window.screenshot(name=str(target)))
    if saved!=target:saved.replace(target)

for size,density,scale,key in (((640,360),1,1,'phone'),((1280,576),2,1,'android'),((1280,576),2.5,1.2,'small-android'),((392,844),1,1,'portrait')):
    Window.size=size;Metrics.density=density;Metrics.fontscale=scale;settle()
    db=fixture();w.enter(db,'Север','Home');w.recruit(db,'Север',1,45)
    owner=OtherworldMap(db,'Север');owner.open(animation=False);shot('map-'+key)
    city=ForeignCityPopup(owner,w.cities(db,'Север')[0]);city.open(animation=False);shot('city-'+key)
    q.begin(db,'Север',random.Random(54))
    journal=city.open_tasks();shot('quests-'+key)
    journal.cards.select(1);shot('war-'+key)
    journal.dismiss(animation=False);city.dismiss(animation=False);owner.dismiss(animation=False);settle();db.close()
