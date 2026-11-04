import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from kivy.metrics import Metrics
from otherworld_ui import OtherworldMap,ForeignCityPopup
from otherworld_themes import THEMES,theme
import otherworlds as w

out=Path('assets/mirror-town');out.mkdir(exist_ok=True)
def shot(name):
    settle();settle()
    target=out/(name+'.png');saved=Path(Window.screenshot(name=str(target)))
    if saved!=target:saved.replace(target)

for size,density,suffix in (((640,360),1,'phone'),((1280,576),2,'android'),((392,844),1,'portrait')):
    Window.size=size;Metrics.density=density;settle()
    db=fixture();w.enter(db,'Север','Home')
    for i in range(1,6):w.recruit(db,'Север',i,10)
    owner=OtherworldMap(db,'Север');owner.open(animation=False);settle()
    city=ForeignCityPopup(owner,w.cities(db,'Север')[0]);city.open(animation=False);shot('city-'+suffix)
    city.open_market();shot('market-'+suffix)
    city.market_popup.dismiss(animation=False);settle()
    city.open_tavern();shot('tavern-'+suffix)
    city.tavern_popup.dismiss(animation=False)
    city.open_recruitment();shot('recruit-'+suffix)
    city.recruitment.popup.dismiss(animation=False);city.dismiss(animation=False);owner.dismiss(animation=False);settle();db.close()
