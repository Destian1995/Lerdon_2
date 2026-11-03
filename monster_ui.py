"""Monster map branches, illustrated encounters and persistent relic choice."""
import json
from functools import lru_cache

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from monster_sites import (monster_name,reward,encounter_reward,art_path,sites,ensure_schema,hunt_status,begin_hunt,
                           resolve_hunt,finish_hunt,expedition,progress,owned_artifacts,upgrade_artifact)
from strategy_ui import surface,text_label,StrategyButton,INK,SURFACE,GOLD,MUTED,TEXT
from city_war import current_turn


@lru_cache(maxsize=14)
def _art(tier,variant=1):
    from kivy.core.image import Image as CoreImage
    return CoreImage(str(art_path(tier,variant)),mipmap=True).texture


def project_path(widget,site,reverse=False):
    points=[(widget.map_pos[0]+x*widget.map_scale,widget.map_pos[1]+y*widget.map_scale)
            for x,y in json.loads(site['road'])]
    return list(reversed(points)) if reverse else points


def draw_monsters(widget):
    from kivy.graphics import Color,InstructionGroup,Rectangle,RoundedRectangle
    from kivy.core.text import Label as CoreLabel
    from map_roads import draw_road_layer
    previous=getattr(widget,'_monster_group',None)
    if previous is not None and previous in widget.canvas.children:
        widget.canvas.remove(previous)
    group=widget._monster_group=InstructionGroup()
    widget.canvas.add(group)
    widget._monster_hits=[]
    for site in sites(widget.conn):
        group.add(draw_road_layer([(site['parent_city'],-site['id'],project_path(widget,site))],widget.map_scale))
        x=widget.map_pos[0]+site['x']*widget.map_scale
        y=widget.map_pos[1]+site['y']*widget.map_scale
        size=72*widget.map_scale
        ready=site['ready_turn']<=current_turn(widget.conn)
        group.add(Color(1,1,1,1 if ready else .45))
        group.add(Rectangle(texture=_art(site['tier'],site.get('variant',1)),pos=(x-size/2,y-size*.38),size=(size,size)))
        title=f'Логово · {reward(site["tier"])["defense"]//1_000_000} млн'
        if not ready:
            title=f'Возрождение: {site["ready_turn"]-current_turn(widget.conn)} х.'
        label=CoreLabel(text=title,font_size=11,bold=True,color=(1,.87,.63,1))
        label.refresh();w,h=label.texture.size
        group.add(Color(.035,.025,.04,.9))
        group.add(RoundedRectangle(pos=(x-w/2-3,y+size*.64-2),size=(w+6,h+4),radius=[3]))
        group.add(Color(1,1,1,1))
        group.add(Rectangle(texture=label.texture,pos=(x-w/2,y+size*.64),size=(w,h)))
        widget._monster_hits.append((x,y,size,site))


def inspect_monster(widget,touch):
    for x,y,size,site in getattr(widget,'_monster_hits',[]):
        if abs(touch.x-x)<=max(24,size/2) and y-size*.38<=touch.y<=y+size*.8:
            MonsterPopup(widget,site).open()
            return True
    return False


def _sync(widget):
    from utils.resource_payments import sync_resources
    sync_resources(widget.conn,widget.current_player_kingdom)
    widget.update_cities()


def play_hunt(widget,site,eid,completed):
    """Real camp is removed from the source before the march; reward on arrival."""
    from troop_movement import MarchRoute,_screen
    from utils.movement_rules import army_size_level
    screen=_screen(widget)
    layer=getattr(getattr(widget,'_map_atmosphere',None),'marches',None)
    row=expedition(widget.conn,eid)
    count=widget.conn.execute('SELECT COALESCE(SUM(unit_count),0) FROM garrisons WHERE city_name=?',(row['camp'],)).fetchone()[0]
    def release():
        if screen:
            screen._troop_movement_busy=False
        _sync(widget)
    def return_home(result):
        def home():
            finish_hunt(widget.conn,eid)
            release()
            completed(result)
        if layer:
            provider=lambda:MarchRoute(project_path(widget,site,True),[True]*(len(json.loads(site['road']))-1))
            layer.play_batch([(provider,army_size_level(count,count),row['faction'],count,True)],home,home)
        else:
            home()
    def arrived():
        result=resolve_hunt(widget.conn,eid)
        _sync(widget)
        if layer:
            MonsterClashPopup(widget,site,result,lambda:return_home(result)).open()
        else:
            return_home(result)
    def cancelled():
        finish_hunt(widget.conn,eid)
        release()
    if screen:
        screen._troop_movement_busy=True
    if layer:
        provider=lambda:MarchRoute(project_path(widget,site),[True]*(len(json.loads(site['road']))-1))
        try:
            layer.play_batch([(provider,army_size_level(count,count),row['faction'],count,True)],arrived,cancelled)
        except Exception:
            cancelled()
            raise
    else:
        arrived()


from monster_battle_ui import MonsterClashPopup


class MonsterPopup(Popup):
    def __init__(self,widget,site,**kwargs):
        super().__init__(title=monster_name(site),size_hint=(None,None),**kwargs)
        self.widget,self.site,self.conn=widget,dict(site),widget.conn
        self.faction=widget.current_player_kingdom
        self.prize=reward(site['tier'])
        self.root_panel=BoxLayout(orientation='vertical',spacing=dp(8),padding=dp(8))
        self.root_panel._responsive_keep_geometry=True
        self.body=BoxLayout(spacing=dp(12))
        self.art=Image(source=str(art_path(site['tier'],site.get('variant',1))),size_hint_x=.42,mipmap=True)
        self.body.add_widget(self.art)
        self.details=BoxLayout(orientation='vertical',spacing=dp(6))
        from monster_stats_ui import MonsterStatsPanel
        self.summary=MonsterStatsPanel(size_hint_y=.75)
        self.details.add_widget(self.summary)
        self.garrison_scroll=ScrollView(do_scroll_x=False,size_hint_y=.25)
        self.cards=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(5))
        self.cards.bind(minimum_height=self.cards.setter('height'))
        self.garrison_scroll.add_widget(self.cards)
        self.details.add_widget(self.garrison_scroll)
        self.body.add_widget(self.details)
        self.root_panel.add_widget(self.body)
        self.status=text_label('',13,MUTED,size_hint_y=None,height=dp(40))
        self.root_panel.add_widget(self.status)
        self.actions=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(6))
        self.hunt=StrategyButton(text='Отправить гарнизон с героем')
        self.hunt.bind(on_release=self.send)
        self.actions.add_widget(self.hunt)
        self.relic=StrategyButton(text='Улучшить артефакт')
        self.relic.bind(on_release=lambda *_:open_relic_choice(widget,self.refresh))
        self.actions.add_widget(self.relic)
        close=StrategyButton(text='Закрыть',size_hint_x=.4)
        close.bind(on_release=self.dismiss)
        self.actions.add_widget(close)
        self.root_panel.add_widget(self.actions)
        self.content=self.root_panel
        self.bind(on_open=self.opened,on_dismiss=self.closed)
        self.refresh()

    def opened(self,*_):
        Window.bind(on_resize=self.fit)
        self.fit()

    def closed(self,*_):
        Window.unbind(on_resize=self.fit)

    def fit(self,*_):
        self.size=(max(1,min(dp(1100),Window.width-dp(16))),max(1,min(dp(780),Window.height-dp(16))))
        self.center=(Window.width/2,Window.height/2)
        stacked=Window.height>Window.width
        self.body.orientation='vertical' if stacked else 'horizontal'
        self.art.size_hint=(1,.4) if stacked else (.42,1)
        self.details.size_hint=(1,.6) if stacked else (.58,1)
        self.hunt.font_size=self.relic.font_size=sp(12 if Window.width<dp(700) else 15)
        self.actions.height=dp(64 if stacked else 48)

    def refresh(self,*_):
        from utils.helpers import format_number
        from utils.garrison_stats import garrison_totals
        self.site=next((s for s in sites(self.conn) if s['id']==self.site['id']),self.site)
        self.prize=encounter_reward(self.site)
        allowed,message=hunt_status(self.conn,self.site,self.faction)
        city=self.conn.execute('SELECT name,faction FROM cities WHERE id=?',(self.site['parent_city'],)).fetchone()
        city_name=city[0] if city else '—'
        p=self.prize
        self.summary.set_prize(p)
        owned=bool(city and city[1]==self.faction)
        self.summary.size_hint_y=.75 if owned else 1
        self.garrison_scroll.size_hint_y=.25 if owned else None
        self.garrison_scroll.height=0 if not owned else self.garrison_scroll.height
        self.garrison_scroll.opacity=1 if owned else 0
        self.garrison_scroll.disabled=not owned
        self.cards.clear_widgets()
        if city and city[1]==self.faction:
            attack=garrison_totals(self.conn,city_name)['attack']
            heading=text_label(f'Гарнизон · атака {format_number(attack)}',15,GOLD,
                               size_hint_y=None,height=dp(32))
            self.cards.add_widget(heading)
            from terrain_site_ui import TerrainSitePopup
            from monster_sites import effective_experience
            self.unit_cards=[];self._compact=Window.height<dp(480)
            for name,count,image,exp in self.conn.execute('''SELECT unit_name,unit_count,unit_image,COALESCE(experience,0)
                        FROM garrisons WHERE city_name=? AND unit_count>0''',(city_name,)):
                unit=dict(name=name,count=count,image=image or '',experience=effective_experience(self.conn,self.faction,exp,city_name,name))
                self.cards.add_widget(TerrainSitePopup.unit_card(self,unit,GOLD))
        self.status.text='Можно отправляться.' if allowed else message
        self.hunt.disabled=not allowed
        state=progress(self.conn,self.faction)
        self.relic.disabled=not(state['relic_earned'] and not state['relic_used'])

    def send(self,*_):
        from troop_movement import movement_busy
        if movement_busy(self.widget):
            return
        try:
            eid=begin_hunt(self.conn,self.site['id'],self.faction)
        except ValueError as exc:
            self.status.text=str(exc)
            self.refresh()
            return
        self.dismiss()
        _sync(self.widget)
        play_hunt(self.widget,self.site,eid,lambda result:None)



def open_relic_choice(widget,changed=lambda:None):
    conn=widget.conn;faction=widget.current_player_kingdom
    panel=BoxLayout(orientation='vertical',spacing=dp(8),padding=dp(8))
    panel.add_widget(text_label('Один артефакт навсегда: +550 процентных пунктов\nк атаке или защите. Выберите характеристику.',15,
                                size_hint_y=None,height=dp(56)))
    scroll=ScrollView(do_scroll_x=False)
    rows=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(8))
    rows.bind(minimum_height=rows.setter('height'))
    scroll.add_widget(rows);panel.add_widget(scroll)
    popup=Popup(title='Дар бездны',content=panel,size_hint=(.92,.9))
    def choose(item,stat):
        from ui_components import show_message
        try:
            data=upgrade_artifact(conn,faction,item['table'],item['id'],stat,item['hero'],item['slot'])
        except ValueError as exc:
            show_message('Улучшение недоступно',str(exc));return
        from troop_movement import _screen
        screen=_screen(widget)
        if screen and getattr(screen,'season_manager',None):
            screen.season_manager.apply_artifact_bonuses(conn)
        popup.dismiss();changed()
        show_message('Артефакт улучшен',f'{data["name"]}: {"атака" if stat=="attack" else "защита"} +{data[stat]:g}%')
    for item in owned_artifacts(conn,faction):
        row=surface(BoxLayout(orientation='vertical',size_hint_y=None,height=dp(118),padding=dp(8),spacing=dp(6)),SURFACE)
        row.add_widget(text_label(f'{item["name"]} · {item["hero"]}',14,GOLD))
        buttons=BoxLayout(spacing=dp(6))
        for stat,caption in (('attack','Атака'),('defense','Защита')):
            button=StrategyButton(text=f'{caption}: {item[stat]:g}% → {item[stat]+550:g}%')
            button.bind(on_release=lambda _,a=item,s=stat:choose(a,s))
            buttons.add_widget(button)
        row.add_widget(buttons);rows.add_widget(row)
    if not rows.children:
        rows.add_widget(text_label('У героев пока нет экипированных артефактов.\nНаграда сохранена: вернитесь после покупки.',15,
                                   size_hint_y=None,height=dp(90)))
    close=StrategyButton(text='Выбрать позже',size_hint_y=None,height=dp(48))
    close.bind(on_release=popup.dismiss);panel.add_widget(close)
    popup.open()
    return popup
