"""Portal expedition map and foreign-city garrison/merchant windows."""
import math

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle,Canvas
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget

import otherworlds as worlds
from otherworld_content import city_art
from otherworld_themes import theme
from strategy_ui import surface, text_label, StrategyButton, INK, SURFACE, GOLD, MUTED, TEXT
from utils.helpers import format_number
from utils.resource_payments import sync_resources
from window_theme import prepare_custom_popup, center_after_resize

PURPLE=(.7,.5,1,1)
GREEN=(.38,.87,.57,1)


def _screen(conn):
    import sys
    screen=getattr(sys.modules.get('game_process'),'_active_game_screen',None)
    return screen if screen and getattr(screen,'conn',None) is conn else None


def _busy(conn):
    screen=_screen(conn)
    overlay=getattr(screen,'_turn_overlay',None)
    import sqlite3
    selected=getattr(screen,'selected_faction',None)
    try:
        in_beam=bool(conn.execute('SELECT 1 FROM portal_beam_journeys WHERE faction=?',(selected,)).fetchone()) if selected else bool(conn.execute('SELECT 1 FROM portal_beam_journeys LIMIT 1').fetchone())
    except sqlite3.OperationalError:in_beam=False
    return in_beam or bool(screen and (getattr(screen,'_troop_movement_busy',False) or
                            (overlay is not None and overlay.parent is not None)))


def _button(text,callback,**kwargs):
    result=StrategyButton(text=text,**kwargs)
    result.bind(on_release=callback)
    return result


class WorldPopup(Popup):
    def __init__(self,title,accent=PURPLE,**kwargs):
        self.accent=accent
        self.root=surface(BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(8)),INK,accent)
        self.root._strategy_fixed_layout=True
        header=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(8))
        self.header=header
        self.heading=text_label(title,22,accent,bold=True)
        header.add_widget(self.heading)
        header.add_widget(_button('×',self.dismiss,size_hint_x=None,width=dp(48),accent=accent))
        self.root.add_widget(header)
        super().__init__(title='',content=self.root,size_hint=(None,None),auto_dismiss=False,**kwargs)
        prepare_custom_popup(self)
        self.bind(on_open=self._opened,on_dismiss=self._closed)
        self.fit()

    def fit(self,*_):
        self.size=(min(dp(1200),Window.width-dp(16)),min(dp(820),Window.height-dp(16)))
        center_after_resize(self)

    def _opened(self,*_):
        Window.bind(on_resize=self.fit)
        self.fit()

    def _closed(self,*_):
        Window.unbind(on_resize=self.fit)


def open_portal(city_popup):
    """Any owned city can open a gate; reopening resumes the existing party."""
    conn,faction=city_popup.conn,city_popup.player_fraction
    if _busy(conn):
        return
    if worlds.party(conn,faction):
        city_popup.dismiss()
        OtherworldMap(conn,faction).open()
        return
    from portal_entry_ui import PortalEntryPopup
    gate=PortalEntryPopup(city_popup)
    gate.open()
    return gate


def _refresh_main(conn,faction):
    # Main map watches garrisons once a second; only its resource HUD is cached.
    sync_resources(conn,faction)


class WorldMapCanvas(Widget):
    def __init__(self,owner,**kwargs):
        super().__init__(**kwargs)
        self.owner=owner
        self.nodes=worlds.cities(owner.conn,owner.faction)
        self.hits=[]
        self._base=Canvas();self.canvas.add(self._base)
        from kivy.core.image import Image as CoreImage
        self.texture=CoreImage(worlds.world(owner.conn,owner.faction)['background']).texture
        self.city_textures={c['id']:CoreImage(city_art(c['id'],owner.faction),mipmap=True).texture for c in self.nodes}
        from map_roads import build_transport_network
        from map_terrain import load_terrain,TerrainView
        terrain=load_terrain(worlds.world(owner.conn)['background'])
        self.network=build_transport_network(
            {c['id']:(c['x']-38.5,c['y']-30) for c in self.nodes},
            list(owner.conn.execute('SELECT city1,city2 FROM portal_roads')),{},(30,30,1170,770),
            terrain=TerrainView(terrain) if terrain else None,movement_limit=None)
        self.bind(pos=self.draw,size=self.draw)
        self.draw()
        from otherworld_effects import MirrorEffects
        self.effects=MirrorEffects(self)
        self.add_widget(self.effects)

    def point(self,x,y):
        return (self.x+x*self.width/1200,self.y+y*self.height/800)

    def draw(self,*_):
        from kivy.core.text import Label as CoreLabel
        from map_roads import TransportNetwork,draw_transport_layer
        self._base.clear();self.hits=[]
        s=min(self.width/1200,self.height/800)
        with self._base:
            Color(1,1,1,1)
            Rectangle(texture=self.texture,pos=self.pos,size=self.size)
        convert=lambda paths:[(a,b,[self.point(*p) for p in path]) for a,b,path in paths]
        network=TransportNetwork(land=convert(self.network.land),sea=convert(self.network.sea),
                                 bridges=convert(self.network.bridges),
                                 docks=[(self.point(*p),self.point(*direction)) for p,direction in self.network.docks])
        self._base.add(draw_transport_layer(network,s))
        p=worlds.party(self.owner.conn,self.owner.faction)
        self._current_city=p['city_id'] if p else None
        from otherworld_quests import objectives
        targets=objectives(self.owner.conn,self.owner.faction)
        with self._base:
            for city in self.nodes:
                x,y=self.point(city['x'],city['y']);size=max(dp(66),132*s)
                Color(.055,.035,.10,.35)
                Ellipse(pos=(x-size*.34,y-size*.22),size=(size*.68,size*.29))
                Color(1,1,1,1)
                texture=self.city_textures[city['id']]
                icon_height=size*texture.height/texture.width
                Rectangle(texture=texture,pos=(x-size/2,y-icon_height*.3),size=(size,icon_height))
                label=CoreLabel(text=city['name'],font_size=min(dp(19),max(13,self.width*.016)),bold=True,color=TEXT)
                label.refresh();w,h=label.texture.size
                for dx,dy in ((-1,-1),(1,-1),(-1,1),(1,1),(0,-2),(0,2),(-2,0),(2,0)):
                    Color(.025,.018,.05,.95)
                    Rectangle(texture=label.texture,pos=(x-w/2+dx,y-icon_height*.34-h+dy),size=(w,h))
                Color(1,1,1,1)
                Rectangle(texture=label.texture,pos=(x-w/2,y-icon_height*.34-h),size=(w,h))
                caption=CoreLabel(text='Ваш отряд' if self._current_city==city['id'] else 'Торговый город',
                                  font_size=min(dp(12),max(10,self.width*.0105)),bold=True,
                                  color=GREEN if self._current_city==city['id'] else (.89,.81,1,1))
                caption.refresh();cw,ch=caption.texture.size
                Color(.025,.018,.05,.8)
                Rectangle(pos=(x-cw/2-3,y-icon_height*.34-h-ch-2),size=(cw+6,ch+3))
                Color(1,1,1,1)
                Rectangle(texture=caption.texture,pos=(x-cw/2,y-icon_height*.34-h-ch),size=(cw,ch))
                self.hits.append((x,y,max(dp(30),size*.6),city))
                if city['id'] in targets:
                    marker=CoreLabel(text='!',font_size=20,bold=True,color=(1,.85,.36,1));marker.refresh()
                    Color(.04,.025,.07,.9);Ellipse(pos=(x+size*.28,y+icon_height*.45),size=(22,24))
                    Color(1,1,1,1);Rectangle(texture=marker.texture,pos=(x+size*.28+6,y+icon_height*.45+1),size=marker.texture.size)

    def on_touch_down(self,touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        if _busy(self.owner.conn):
            return True
        for x,y,r,city in self.hits:
            if math.dist((x,y),touch.pos)<r:
                ForeignCityPopup(self.owner,city).open();return True
        return True


class OtherworldMap(WorldPopup):
    def __init__(self,conn,faction,**kwargs):
        self.conn,self.faction=conn,faction
        worlds.upgrade_world(conn)
        worlds.finish_beam(conn,faction)
        super().__init__('ДРУГОЙ МИР  /  '+theme(faction)['name'],accent=theme(faction)['accent'],**kwargs)
        self.status=text_label('',14,GREEN,size_hint_y=None,height=dp(36))
        self.root.add_widget(self.status)
        self.map=WorldMapCanvas(self)
        self.root.add_widget(self.map)
        self.message=text_label('Нажмите город: торговля, бой или переход по дороге.',13,MUTED,
                                size_hint_y=None,height=dp(28))
        self.root.add_widget(self.message)
        bar=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(8))
        self.return_button=_button('Вернуться через портал',self.home)
        bar.add_widget(self.return_button)
        self.quest_button=_button('Задания',self.quests,accent=self.accent)
        bar.add_widget(self.quest_button)
        bar.add_widget(_button('Завершить ход',self.next_turn))
        bar.add_widget(_button('Основная карта',self.dismiss))
        self.root.add_widget(bar)
        self._poll=Clock.schedule_interval(self.refresh,.5)
        self.bind(on_dismiss=lambda *_:self._poll.cancel())
        self.bind(on_open=self.map.effects.start,on_dismiss=self.map.effects.stop)
        self.bind(on_dismiss=self.close_beam)
        self.refresh()

    def refresh(self,*_):
        from portal_items import expire
        if expire(self.conn):
            screen=_screen(self.conn)
            if screen:screen.season_manager.apply_artifact_bonuses(self.conn)
            else:self.conn.commit()
        p=worlds.party(self.conn,self.faction)
        if not p:
            self.dismiss();return
        c=next(c for c in self.map.nodes if c['id']==p['city_id'])
        resources=dict(self.conn.execute('SELECT resource_type,amount FROM resources WHERE faction=?',(self.faction,)))
        row=self.conn.execute('SELECT moves_left FROM turn_check_move WHERE faction=?',(self.faction,)).fetchone()
        self.status.text=f'{c["name"]} · Действий: {row[0] if row else 0}  |  Кроны: {format_number(resources.get("Кроны",0))}  |  Кристаллы: {format_number(resources.get("Кристаллы",0))}'
        self.return_button.disabled=p['city_id']!=1 or _busy(self.conn)
        if self.map._current_city!=p['city_id']:self.map.draw()
        from otherworld_quests import state,cap_turns
        run=state(self.conn,self.faction)
        self.quest_button.text='Задания '+str(int(run['detective']==3)+int(run['war']==3))+'/2' if run else 'Задания'
        left=cap_turns(self.conn,self.faction)
        if left:self.message.text=f'Награда Зазеркалья: лимиты ресурсов +35%, ещё {left} х.'

    def home(self,*_):
        if _busy(self.conn):
            return
        try:
            worlds.return_home(self.conn,self.faction)
        except ValueError as exc:
            self.message.text=str(exc);return
        _refresh_main(self.conn,self.faction)
        self.dismiss()

    def next_turn(self,*_):
        screen=_screen(self.conn)
        if screen and not _busy(self.conn):
            screen.process_turn(None)

    def quests(self,*_):
        if not _busy(self.conn):
            from otherworld_quest_ui import QuestJournal
            QuestJournal(self).open()

    def play_beam(self,source,destination):
        from troop_movement import rendered_route
        from otherworld_beam import BeamTravel
        centers={c['id']:(c['x'],c['y']) for c in self.map.nodes}
        route=rendered_route(self.map.network,[source,destination],centers)
        points=route.points if route else [centers[source],centers[destination]]
        screen=_screen(self.conn)
        if screen:
            screen._troop_movement_busy=True
            screen.end_turn_button.disabled=True
        def arrived():
            worlds.finish_beam(self.conn,self.faction)
            if screen:
                screen._troop_movement_busy=False
                screen.end_turn_button.disabled=False
            self.map.draw();self.refresh()
        self.map.beam=BeamTravel(self.map,points,self.accent,arrived)
        self.map.add_widget(self.map.beam)

    def close_beam(self,*_):
        beam=getattr(self.map,'beam',None)
        if beam and not beam.finished:beam.finish()


class ForeignCityPopup(WorldPopup):
    def __init__(self,owner,city,**kwargs):
        self.owner,self.city=owner,city
        self.conn,self.faction=owner.conn,owner.faction
        self.mode='resources'
        super().__init__(city['name']+'  /  Чужие владения',accent=theme(self.faction)['accent'],**kwargs)
        self.header.height=dp(64)
        self.header.add_widget(Image(source=city_art(city['id'],self.faction),size_hint_x=None,width=dp(72),mipmap=True),
                               index=len(self.header.children))
        self.info=text_label('',14,GOLD,size_hint_y=None,height=dp(36))
        self.root.add_widget(self.info)
        body=BoxLayout(spacing=dp(10))
        left=surface(BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(8)),SURFACE,self.accent)
        left.add_widget(text_label('ГАРНИЗОН ЭКСПЕДИЦИИ',17,self.accent,bold=True,size_hint_y=None,height=dp(30)))
        self.army_box=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(7))
        self.army_box.bind(minimum_height=self.army_box.setter('height'))
        scroll=ScrollView(do_scroll_x=False);scroll.add_widget(self.army_box);left.add_widget(scroll)
        self.market=surface(BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(8)),SURFACE,GOLD)
        self.market.add_widget(text_label('ТОРГОВЕЦ ЗАЗЕРКАЛЬЯ',18,GOLD,bold=True,size_hint_y=None,height=dp(30)))
        tabs=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(5))
        for key,title in [('resources','Ресурсы'),('artifacts','Артефакты'),('units','Юниты · 5')]:
            tabs.add_widget(_button(title,lambda *_,k=key:self.show_market(k)))
        self.market.add_widget(tabs)
        self.offers=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(8))
        self.offers.bind(minimum_height=self.offers.setter('height'))
        market_scroll=ScrollView(do_scroll_x=False)
        market_scroll.add_widget(self.offers);self.market.add_widget(market_scroll)
        body.add_widget(left);body.add_widget(self.market);self.root.add_widget(body)
        self.feedback=text_label('',14,GREEN,size_hint_y=None,height=dp(40))
        self.root.add_widget(self.feedback)
        bar=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(8))
        self.travel_button=_button('Перейти · 1 действие',self.go)
        self.battle_button=_button('Сразиться со стражей',self.battle)
        bar.add_widget(self.travel_button);bar.add_widget(self.battle_button)
        bar.add_widget(_button('Задания',lambda *_:self.owner.quests()))
        self.root.add_widget(bar)
        self.refresh()

    def present(self):
        p=worlds.party(self.conn,self.faction)
        return p if p and p['city_id']==self.city['id'] else None

    def refresh(self):
        from utils.garrison_stats import garrison_profiles,garrison_totals
        p=self.present();self.army_box.clear_widgets()
        self.info.text=('Города нельзя захватить. ' + ('Ваш отряд здесь.' if p else 'Отряд находится в другом городе.')+
                        f'  Цены: {self.city["price"]}%')
        if p:
            profiles=garrison_profiles(self.conn,p['camp'],faction=self.faction)
            totals=garrison_totals(self.conn,p['camp'],profiles)
            self.army_box.add_widget(text_label('Атака: '+format_number(totals['attack'])+'  ·  Защита: '+format_number(totals['defense']),
                                                16,GREEN,size_hint_y=None,height=dp(44)))
            for name,count,image,exp,*_ in worlds._camp_units(self.conn,p['camp']):
                row=surface(BoxLayout(size_hint_y=None,height=dp(72),padding=dp(6),spacing=dp(8)),INK,PURPLE)
                row.add_widget(Image(source=image or 'files/status/army.png',size_hint_x=None,width=dp(58)))
                label=name.removeprefix('Странник: ').split(' / ')[0]
                row.add_widget(text_label(label+'\n'+format_number(count)+' бойцов · Побед: '+str(exp),15))
                self.army_box.add_widget(row)
        else:
            self.army_box.add_widget(text_label('Независимая стража\n'+format_number(self.city['guards'])+' бойцов',18,GOLD,
                                                size_hint_y=None,height=dp(80)))
        guard,target=worlds.guard_profile(self.conn,self.faction,self.city)
        self.army_box.add_widget(text_label((target or 'Стража города')+': '+format_number(guard['unit_count'])+' бойцов\n'+
            f'АТК {guard["attack"]}  /  ЗАЩ {guard["defense"]} · Общая защита '+format_number(guard['defense']*guard['unit_count'])+'\n'+
            'Победа: +'+format_number(10_000+self.city['id']*5000)+' крон, опыт +1',
            14,GOLD,size_hint_y=None,height=dp(76)))
        party=worlds.party(self.conn,self.faction)
        edge=tuple(sorted((party['city_id'],self.city['id']))) if party else (0,0)
        connected=bool(self.conn.execute('SELECT 1 FROM portal_roads WHERE city1=? AND city2=?',edge).fetchone())
        self.travel_button.disabled=bool(p) or not connected
        cooldown=worlds.battle_ready(self.conn,self.faction) if p else 0
        self.battle_button.disabled=not p or cooldown>0
        self.battle_button.text=f'Стража: отдых {cooldown} х.' if cooldown else ('Атаковать: '+target+' · 1 действие' if target else 'Сразиться со стражей · 1 действие')
        self.show_market(self.mode)

    def show_market(self,mode):
        self.mode=mode;self.offers.clear_widgets()
        self.offer_buttons=[]
        def offer(title,subtitle,callback,image=None):
            card=surface(BoxLayout(orientation='horizontal' if image else 'vertical',size_hint_y=None,
                                   height=dp(132 if image else 116),padding=dp(8),spacing=dp(10)),INK,GOLD)
            copy=BoxLayout(orientation='vertical',spacing=dp(4))
            if image:
                card.add_widget(Image(source=image,size_hint_x=None,width=dp(92),mipmap=True))
            copy.add_widget(text_label(title,16,GOLD,bold=True))
            copy.add_widget(text_label(subtitle,13,MUTED))
            button=_button('Купить' if mode!='resources' else title,callback,size_hint_y=None,height=dp(36))
            button.disabled=not bool(self.present())
            self.offer_buttons.append(button)
            copy.add_widget(button);card.add_widget(copy);self.offers.add_widget(card)
        if mode=='resources':
            for buy,title,base in [(True,'Купить 10 тыс. кристаллов',15000),(False,'Продать 10 тыс. кристаллов',10000)]:
                offer(title,('Цена: ' if buy else 'Вы получите: ')+format_number(worlds.price(self.city,base))+' крон',
                      lambda *_,b=buy:self.act(lambda:worlds.trade_crystals(self.conn,self.faction,b)))
        elif mode=='units':
            for unit in worlds.unit_offers(self.conn,self.faction):
                cost=worlds.price(self.city,max(1,unit['cost_money'])*2)*100
                offer(unit['unit_name']+' · 100 бойцов',f'АТК {unit["attack"]}  /  ЗАЩ {unit["defense"]} · '+format_number(cost)+' крон',
                      lambda *_,u=unit:self.act(lambda:worlds.recruit(self.conn,self.faction,u['id'])),unit['image_path'])
        else:
            from portal_items import champions
            p=self.present()
            eligible=champions(self.conn,self.faction,p['camp']) if p else []
            for artifact in worlds.artifact_offers(self.conn,self.faction):
                offer(artifact['name'],f'АТК +{artifact["attack"]}%  /  ЗАЩ +{artifact["defense"]}% · '+
                      format_number(worlds.price(self.city,artifact['cost']))+f' крон · {artifact["duration"]} х. · +230% к аналогу',
                      lambda *_,a=artifact:self.artifact(a),artifact['image_url'])
                self.offer_buttons[-1].disabled=not eligible
                from portal_items import remaining
                active=self.conn.execute('SELECT artifact_id FROM portal_artifacts WHERE faction=? AND catalog_id=?',(self.faction,artifact['id'])).fetchone()
                left=remaining(self.conn,active[0]) if active else 0
                if left:
                    self.offer_buttons[-1].text=f'Действует · ещё {left} х.'
                    self.offer_buttons[-1].disabled=True
            self.feedback.text=('Получатель: '+eligible[0]+' [3 класс]') if eligible else 'Артефакты доступны только героям 3 класса в отряде.'

    def act(self,callback,success='Готово'):
        if _busy(self.conn):
            return
        try:
            callback()
        except ValueError as exc:
            self.feedback.text=str(exc);return
        _refresh_main(self.conn,self.faction)
        self.feedback.text=success
        self.refresh();self.owner.refresh()

    def artifact(self,artifact):
        def buy():
            worlds.buy_artifact(self.conn,self.faction,artifact['id'])
            screen=_screen(self.conn)
            if screen:
                screen.season_manager.apply_artifact_bonuses(self.conn)
        self.act(buy,f'Артефакт действует {artifact["duration"]} ходов. Затем вернётся прежняя экипировка.')

    def go(self,*_):
        if _busy(self.conn):return
        try:
            source=worlds.party(self.conn,self.faction)['city_id']
            worlds.begin_beam(self.conn,self.faction,self.city['id'])
        except ValueError as exc:self.feedback.text=str(exc);return
        self.dismiss();self.owner.play_beam(source,self.city['id'])

    def battle(self,*_):
        if _busy(self.conn):
            return
        try:
            result=worlds.fight_guards(self.conn,self.faction)
        except ValueError as exc:
            self.feedback.text=str(exc);return
        _refresh_main(self.conn,self.faction);self.refresh();self.owner.refresh()
        from battle_ui import BattleViewer,BattleReport
        from fight import generate_battle_report
        faction=self.faction
        defending=result.get('quest_target') or 'Независимая стража'
        class ForeignBattle(BattleViewer):
            def reveal_result(view):
                super().reveal_result()
                view.result_detail.text=('Победа · +'+format_number(result['coins'])+' крон · Опыт +1'
                                        if result['won'] else 'Отряд отступает. Город остаётся чужим.')
                if result.get('quest_win'):view.result_detail.text+=' · Квест выполнен: награда в заданиях'
        def report():
            rows=generate_battle_report(result['army'],result['guards'],'attacker' if result['won'] else 'defender',
                                        faction,defending,faction,result['city'])
            BattleReport(rows,faction,faction,defending,rounds=result['rounds']).open()
        ForeignBattle(result['rounds'],faction,defending,'attacker' if result['won'] else 'defender',
                      faction,'Экспедиция',result['city'],callback=report,
                      defender_image=result['guards'][0]['unit_image']).open()
