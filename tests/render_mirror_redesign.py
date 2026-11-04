"""Render the real expedition and council widgets against disposable databases."""
import random
import sqlite3
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from kivy.metrics import Metrics
from kivy.uix.popup import Popup
from window_theme import install_window_theme
from otherworld_ui import OtherworldMap,ForeignCityPopup
from otherworld_quest_ui import QuestJournal
from nobles import show_nobles_window
import otherworlds as w
import otherworld_quests as q

output=Path('assets/mirror-redesign');output.mkdir(exist_ok=True)
install_window_theme()
def capture(name):
    settle();settle()
    target=output/(name+'.png')
    saved=Path(Window.screenshot(name=str(target)))
    if saved!=target:saved.replace(target)

for size,density,suffix in (((640,360),1,'phone'),((1280,576),2,'android'),((392,844),1,'portrait'),((1192,824),1,'desktop')):
    Window.size=size;Metrics.density=density;settle()
    db=fixture();w.enter(db,'Север','Home')
    owner=OtherworldMap(db,'Север');owner.open(animation=False);capture('map-'+suffix)
    city=ForeignCityPopup(owner,w.cities(db,'Север')[0]);city.open(animation=False);capture('city-'+suffix)
    city.show_market('artifacts');capture('city-artifact-'+suffix)
    city.open_recruitment();capture('recruit-'+suffix)
    city.recruitment.popup.dismiss(animation=False);city.dismiss(animation=False)
    q.begin(db,'Север',random.Random(54))
    journal=QuestJournal(owner);journal.open(animation=False);capture('quest-'+suffix)
    journal.dismiss(animation=False);owner.dismiss(animation=False);db.close()
    db=sqlite3.connect(':memory:')
    db.executescript('''CREATE TABLE user_faction(faction_name TEXT); INSERT INTO user_faction VALUES('Север');
        CREATE TABLE season(id INTEGER,season_index INTEGER); INSERT INTO season VALUES(1,0);
        CREATE TABLE nobles(id INTEGER,priority INTEGER,loyalty REAL,status TEXT,name TEXT,ideology TEXT,attendance_history TEXT);
        INSERT INTO nobles VALUES(1,1,80,'active','Николай','Смирение','1,1,1'),
        (2,2,61.6,'active','Генрих','{"type":"greed","demand":3159}','1,0,1'),
        (3,3,25,'active','Иван','Любит Эльфы','0,0,0');
        CREATE TABLE resources(faction TEXT,resource_type TEXT,amount REAL);
        INSERT INTO resources VALUES('Север','Кроны',500000),('Север','Рабочие',500);''')
    popup=show_nobles_window(db,'Север',SimpleNamespace(conn=db,resources={}))
    capture('council-'+suffix);popup.dismiss(animation=False);settle();db.close()
for popup in list(Window.children):
    if isinstance(popup,Popup):popup.dismiss(animation=False)
