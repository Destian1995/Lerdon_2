"""Render the real tactical widget without loading or changing a campaign."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
from test_tactical_battle_ui import TacticalUITests,Window,settle
from test_tactical_combat import unit
from tactical_combat import TacticalBattle
from tactical_battle_ui import TacticalBattlePopup


def roster():
    a=[unit('Охотники',1400,'archer',initiative=100),unit('Ольга',1,'mage',cls=2),unit('Владислав',1,'infantry',cls=3)]
    a[0]['consumption']=2.1
    b=[unit('Паладины',1800,'cavalry'),unit('Агилар',1,'cavalry',cls=3),unit('Сёстры',120,'mage')]
    for u,path in zip(a,['people/predator.jpg','people/olga.jpg','people/vlad.jpg']):u['unit_image']='files/army/'+path
    for u,path in zip(b,['adepts/paladin.jpg','adepts/agilar.jpg','adepts/sestra.jpg']):u['unit_image']='files/army/'+path
    return a,b


case=TacticalUITests();case.setUp()
try:
    for size,name in [((1000,600),'desktop'),((640,360),'phone'),((360,640),'portrait')]:
        Window.size=size;settle()
        model=TacticalBattle(*roster(),seed=7,biome='forest',factions=('Север','Адепты'))
        for s,p in zip(model.stacks.values(),[(2,4),(1,6),(2,2),(5,4),(7,6),(6,2)]):
            s.pos=p;model.terrain[p]='plain'
        model.terrain[2,4]='hill';model.terrain[3,4]='plain';model.terrain[4,4]='plain'
        view=TacticalBattlePopup(model,'attacker',lambda result:None,'Виндгар')
        case.views.append(view)
        view.deploying=False
        view.open(animation=False);settle()
        view.clock_event.cancel();view.clock_event=None
        view.select((5,4));settle()
        target=ROOT/'assets'/f'tactical-battle-{name}.png'
        out=Path(Window.screenshot(name=str(target)))
        if out!=target:out.replace(target)
        view.dismiss(animation=False);settle()
    Window.size=(1000,600);settle()
    model=TacticalBattle(*roster(),seed=7,biome='snow',factions=('Север','Адепты'))
    hero=next(s for s in model.stacks.values() if s.name=='Владислав')
    hero.pos=(3,4)
    enemy=model.stacks['defender:0'];enemy.pos=(6,4)
    model.terrain.update({(4,4):'plain',(5,4):'plain'})
    model.queue.remove(hero.id);model.queue.insert(0,hero.id)
    view=TacticalBattlePopup(model,'attacker',lambda result:None,'Северный перевал')
    case.views.append(view);view.deploying=False
    view.open(animation=False);settle()
    if view.clock_event:view.clock_event.cancel();view.clock_event=None
    view.selected_skill='grenade';view.select(enemy.pos);settle()
    target=ROOT/'assets/tactical-hero-ability.png'
    out=Path(Window.screenshot(name=str(target)))
    if out!=target:out.replace(target)
    view.show_skills();settle()
    target=ROOT/'assets/tactical-hero-skills.png'
    out=Path(Window.screenshot(name=str(target)))
    if out!=target:out.replace(target)
finally:
    case.tearDown()
print('Rendered tactical battle at desktop, landscape phone and portrait phone sizes.')
