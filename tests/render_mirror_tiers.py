"""Review all five ascending recruitment tiers using a disposable game save."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from otherworld_ui import OtherworldMap,ForeignCityPopup
from kivy.metrics import Metrics
import otherworlds as worlds

Metrics.density=1;Window.size=(1000,600);settle()
db=fixture();worlds.enter(db,'Север','Home')
owner=OtherworldMap(db,'Север');owner.open(animation=False);settle()
city=ForeignCityPopup(owner,worlds.cities(db,'Север')[0]);city.open(animation=False);settle()
city.open_recruitment();settle()
session=city.recruitment
out=Path('assets/mirror-tiers');out.mkdir(exist_ok=True)
for index in range(5):
    session.carousel.index=index;session.prepare_current(session.carousel,index);settle()
    target=out/f'tier-{index+1}.png';saved=Path(Window.screenshot(name=str(target)))
    if saved!=target:saved.replace(target)
session.popup.dismiss(animation=False);city.dismiss(animation=False);owner.dismiss(animation=False)
settle();db.close()
