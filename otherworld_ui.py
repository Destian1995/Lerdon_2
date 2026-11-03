"""Portal expedition map and foreign-city garrison/merchant windows."""
import math

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle,Canvas
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.stencilview import StencilView
from kivy.uix.image import Image
from kivy.uix.popup import Popup

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
    from mirror_layout import compact_frame
    compact_frame(result)
    result.bind(on_release=callback)
    return result


class WorldPopup(Popup):
    def __init__(self,title,accent=PURPLE,**kwargs):
        self.accent=accent
        self.root=surface(BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(8)),INK,accent)
        from mirror_layout import compact_frame
        compact_frame(self.root)
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
        self._layout_event=Clock.create_trigger(self._layout,-1)
        self.root.bind(size=self._layout_event)
        self.fit()

    def fit(self,*_):
        self.size=(min(dp(1200),Window.width-dp(16)),min(dp(820),Window.height-dp(16)))
        center_after_resize(self)
        if hasattr(self,'_layout_event'):self._layout_event()

    def _layout(self,*_):
        if hasattr(self,'layout_content'):self.layout_content()

    def _opened(self,*_):
        Window.bind(on_resize=self.fit)
        self.fit()

    def _closed(self,*_):
        Window.unbind(on_resize=self.fit)
        self._layout_event.cancel()


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


class WorldMapCanvas(StencilView):
    def __init__(self,owner,**kwargs):
        super().__init__(**kwargs)
        self.owner=owner
        self.nodes=worlds.cities(owner.conn,owner.faction)
        self.hits=[]
        from map_camera import MapCamera
        self.camera=MapCamera(self.size,(0,0,*self.size))
        self.touches={}
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
        x,y=self.camera.project(x*self.width/1200,y*self.height/800)
        return self.x+x,self.y+y

    def draw(self,*_):
        from kivy.core.text import Label as CoreLabel
        from map_roads import TransportNetwork,draw_transport_layer
        self._base.clear();self.hits=[]
        self.camera.configure(self.size,(0,0,*self.size))
        zoom=self.camera.zoom
        s=min(self.width/1200,self.height/800)*zoom
        with self._base:
            Color(1,1,1,1)
            Rectangle(texture=self.texture,pos=self.point(0,0),size=(self.width*zoom,self.height*zoom))
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
                x,y=self.point(city['x'],city['y']);size=max(32,132*s)
                Color(.055,.035,.10,.35)
                Ellipse(pos=(x-size*.34,y-size*.22),size=(size*.68,size*.29))
                Color(1,1,1,1)
                texture=self.city_textures[city['id']]
                icon_height=size*texture.height/texture.width
                Rectangle(texture=texture,pos=(x-size/2,y-icon_height*.3),size=(size,icon_height))
                label=CoreLabel(text=city['name'],font_size=min(sp(24),max(12,self.width*.020))*(1+(zoom-1)*.6),bold=True,color=TEXT)
                label.refresh();w,h=label.texture.size
                for dx,dy in ((-1,-1),(1,-1),(-1,1),(1,1),(0,-2),(0,2),(-2,0),(2,0)):
                    Color(.025,.018,.05,.95)
                    Rectangle(texture=label.texture,pos=(x-w/2+dx,y-icon_height*.34-h+dy),size=(w,h))
                Color(1,1,1,1)
                Rectangle(texture=label.texture,pos=(x-w/2,y-icon_height*.34-h),size=(w,h))
                if self._current_city==city['id']:
                    caption=CoreLabel(text='Ваш отряд',font_size=min(sp(14),max(10,self.width*.0105)),bold=True,color=GREEN)
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
        # HUD surfaces must not start a map drag or open a city underneath.
        if any(widget.collide_point(*touch.pos) for name in
               ('header','resource_panel','status','action_bar','zoom_controls')
               if (widget:=getattr(self.owner,name,None)) is not None):
            return False
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        if _busy(self.owner.conn):
            return True
        if getattr(touch,'is_mouse_scrolling',False):
            self.change_zoom(.1 if touch.button=='scrollup' else -.1,(touch.x-self.x,touch.y-self.y))
            return True
        self.touches[touch.uid]={'touch':touch,'origin':touch.pos,'moved':False}
        touch.grab(self)
        if len(self.touches)>1:
            for item in self.touches.values():item['moved']=True
        return True

    def on_touch_move(self,touch):
        if touch.uid not in self.touches:return super().on_touch_move(touch)
        item=self.touches[touch.uid]
        if len(self.touches)>1:
            other=next(v['touch'] for k,v in self.touches.items() if k!=touch.uid)
            old=math.dist(touch.ppos,other.pos);new=math.dist(touch.pos,other.pos)
            if old>1:self.set_zoom(self.camera.zoom*new/old,((touch.x+other.x)/2-self.x,(touch.y+other.y)/2-self.y))
        elif math.dist(item['origin'],touch.pos)>7:
            item['moved']=True
            self.camera.move(touch.dx,touch.dy);self.redraw_camera()
        return True

    def on_touch_up(self,touch):
        item=self.touches.pop(touch.uid,None)
        if item is None:return super().on_touch_up(touch)
        touch.ungrab(self)
        if not item['moved'] and not _busy(self.owner.conn):
            for x,y,r,city in self.hits:
                if math.dist((x,y),touch.pos)<r:
                    ForeignCityPopup(self.owner,city).open();break
        return True

    def set_zoom(self,value,anchor=None):
        self.camera.set_zoom(value,anchor);self.redraw_camera()

    def change_zoom(self,amount,anchor=None):
        self.set_zoom(self.camera.zoom+amount,anchor)

    def redraw_camera(self):
        self.draw()
        if hasattr(self,'effects'):self.effects.update(0)
        self.owner.zoom_label.text=f'×{self.camera.zoom:.1f}'


class OtherworldMap(WorldPopup):
    def __init__(self,conn,faction,**kwargs):
        self.conn,self.faction=conn,faction
        worlds.upgrade_world(conn)
        worlds.finish_beam(conn,faction)
        super().__init__('ДРУГОЙ МИР  /  '+theme(faction)['name'],accent=theme(faction)['accent'],**kwargs)
        from mirror_layout import FitLabel
        self.root.remove_widget(self.header)
        self.stage=FloatLayout()
        self.root.add_widget(self.stage)
        self.map=WorldMapCanvas(self)
        self.stage.add_widget(self.map)
        self.header.size_hint=(None,None)
        self.header.pos_hint={'top':1}
        self.header.padding=5
        surface(self.header,INK,self.accent)
        self.map_close=self.header.children[0]
        self.header.remove_widget(self.map_close)
        self.map_close.size_hint=(None,None)
        self.stage.add_widget(self.map_close)
        self.heading.text=theme(faction)['name']
        self.status=FitLabel(text='',maximum=22,color=GREEN,size_hint=(None,None),halign='center')
        surface(self.status,INK,self.accent)
        self.stage.add_widget(self.status)
        self.stage.add_widget(self.header)
        self.resource_panel=surface(BoxLayout(orientation='vertical',size_hint=(None,None),padding=8,spacing=4),INK,self.accent)
        self.resource_labels={}
        for resource,icon in [('Кроны','coin'),('Кристаллы','crystal')]:
            row=BoxLayout(spacing=8)
            row.add_widget(Image(source=f'files/status/resource_box/{icon}.png',size_hint_x=.24))
            label=FitLabel(text='',maximum=23,bold=True)
            self.resource_labels[resource]=label;row.add_widget(label)
            self.resource_panel.add_widget(row)
        self.stage.add_widget(self.resource_panel)
        from mirror_layout import compact_frame
        for panel in (self.header,self.status,self.resource_panel):compact_frame(panel)
        self.message=FitLabel(text='',maximum=sp(13),color=GREEN,size_hint=(None,None))
        self.stage.add_widget(self.message)
        bar=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(8))
        self.action_bar=bar
        bar.size_hint=(None,None)
        self.return_button=_button('Вернуться через портал',self.home)
        bar.add_widget(self.return_button)
        self.quest_button=_button('Задания',self.quests,accent=self.accent)
        bar.add_widget(self.quest_button)
        self.next_turn_button=_button('Завершить ход',self.next_turn)
        bar.add_widget(self.next_turn_button)
        bar.add_widget(_button('Основная карта',self.dismiss))
        self.stage.add_widget(bar)
        self.zoom_controls=surface(BoxLayout(size_hint=(None,None),spacing=4,padding=4),accent=self.accent)
        self.zoom_label=_button('×1.0',lambda *_:self.map.set_zoom(1),accent=self.accent)
        self.zoom_minus=_button('−',lambda *_:self.map.change_zoom(-.1),accent=self.accent)
        self.zoom_plus=_button('+',lambda *_:self.map.change_zoom(.1),accent=self.accent)
        for button in (self.zoom_minus,self.zoom_label,self.zoom_plus):self.zoom_controls.add_widget(button)
        self.stage.add_widget(self.zoom_controls)
        compact_frame(self.zoom_controls)
        self.stage.bind(size=self._layout_event,pos=self._layout_event)
        self._poll=Clock.schedule_interval(self.refresh,.5)
        self.bind(on_dismiss=lambda *_:self._poll.cancel())
        self.bind(on_open=self.map.effects.start,on_dismiss=self.map.effects.stop)
        self.bind(on_dismiss=self.close_beam)
        self.refresh()
        self._layout_event()

    def fit(self,*_):
        self.size=(max(1,Window.width-8),max(1,Window.height-8))
        center_after_resize(self)
        if hasattr(self,'_layout_event'):self._layout_event()

    def layout_content(self):
        if not hasattr(self,'zoom_controls'):return
        self.root.padding=3;self.root.spacing=0
        x,y=self.stage.pos;w,h=self.stage.size
        portrait=w<h
        resource_width=min(230,w*.30 if not portrait else w*.46)
        self.resource_panel.size=(resource_width,min(132,max(82,h*.23)))
        self.resource_panel.pos=(x+8,y+h-self.resource_panel.height-8)
        for label in self.resource_labels.values():label.maximum=min(24,max(16,h*.04))
        self.header.size=(min(500,w-resource_width-90),min(64,max(44,h*.115)))
        self.header.pos=(max(self.resource_panel.right+10,x+(w-self.header.width)/2),y+h-self.header.height-8)
        self.heading.font_size=min(28,max(18,h*.046),self.header.width*.063)
        self.map_close.size=(self.header.height,self.header.height)
        self.map_close.pos=(x+w-self.map_close.width-8,y+h-self.map_close.height-8)
        self.status.size=(resource_width,min(62,max(44,h*.11)))
        self.status.pos=(self.resource_panel.x,self.resource_panel.y-self.status.height-6)
        if portrait:
            self.header.size=(w-self.map_close.width-24,self.header.height)
            self.header.pos=(x+8,y+h-self.header.height-8)
            self.heading.font_size=min(25,max(18,w*.055))
            self.resource_panel.pos=(x+8,self.header.y-self.resource_panel.height-8)
            self.status.size=(max(1,w-resource_width-24),self.resource_panel.height)
            self.status.pos=(self.resource_panel.right+8,self.resource_panel.y)
        self.status.maximum=min(22,max(14,h*.035))
        self.action_bar.pos=(x+8,y+8);self.action_bar.width=w-16
        self.action_bar.height=min(68,max(46,h*.115));self.action_bar.spacing=8
        self.return_button.text='Вернуться через портал' if w>850 else 'Портал'
        for button in self.action_bar.children:button.font_size=min(21,max(14,h*.033))
        self.zoom_controls.size=(min(234,max(160,w*.20)),min(60,max(42,h*.10)))
        self.zoom_controls.pos=(x+(w-self.zoom_controls.width)/2,self.action_bar.top+10)
        for button in self.zoom_controls.children:button.font_size=min(23,max(17,h*.038))
        self.message.pos=(x+8,self.action_bar.top+10)
        self.message.size=(max(1,(w-self.zoom_controls.width)/2-20),self.zoom_controls.height)

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
        for resource,label in self.resource_labels.items():
            label.text=resource+'\n'+format_number(resources.get(resource,0))
        self.status.text=f'{c["name"]} · Действий: {row[0] if row else 0}'
        self.return_button.disabled=p['city_id']!=1 or _busy(self.conn)
        self.next_turn_button.disabled=_busy(self.conn)
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
        for item in self.map.touches.values():item['touch'].ungrab(self.map)
        self.map.touches.clear()
        beam=getattr(self.map,'beam',None)
        if beam and not beam.finished:beam.finish()


class ForeignCityPopup(WorldPopup):
    def __init__(self,owner,city,**kwargs):
        self.owner,self.city=owner,city
        self.conn,self.faction=owner.conn,owner.faction
        self.mode='resources'
        super().__init__(city['name'],accent=theme(self.faction)['accent'],**kwargs)
        self.header.height=dp(64)
        self.city_image=Image(source=city_art(city['id'],self.faction),size_hint_x=None,width=dp(72),mipmap=True)
        self.header.add_widget(self.city_image,
                               index=len(self.header.children))
        from mirror_layout import FitLabel
        self.info=FitLabel(text='',maximum=sp(14),color=GOLD,size_hint_y=None,height=dp(28))
        self.root.add_widget(self.info)
        body=self.body=BoxLayout(spacing=dp(10))
        left=surface(BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(8)),SURFACE,self.accent)
        self.army_panel=left
        from mirror_layout import FitLabel
        self.army_title=FitLabel(text='Гарнизон экспедиции',color=self.accent,bold=True,size_hint_y=None)
        self.army_totals=FitLabel(text='',color=GREEN,size_hint_y=None)
        self.guard_label=FitLabel(text='',color=GOLD,size_hint_y=None)
        left.add_widget(self.army_title);left.add_widget(self.army_totals)
        from mirror_layout import CardPager
        self.army_box=CardPager(accent=self.accent)
        left.add_widget(self.army_box);left.add_widget(self.guard_label)
        self.market=surface(BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(8)),SURFACE,GOLD)
        from mirror_layout import compact_frame
        compact_frame(left);compact_frame(self.market)
        self.market_title=FitLabel(text='Торговец Зазеркалья',color=GOLD,bold=True,size_hint_y=None)
        self.market.add_widget(self.market_title)
        tabs=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(5))
        self.tabs=tabs;self.tab_buttons={}
        for key,title in [('resources','Ресурсы'),('artifacts','Артефакты'),('units','Юниты · 5')]:
            button=_button(title,lambda *_,k=key:self.show_market(k))
            self.tab_buttons[key]=button;tabs.add_widget(button)
        self.market.add_widget(tabs)
        from mirror_layout import CardPager
        self.offers=CardPager(accent=GOLD)
        self.market.add_widget(self.offers)
        body.add_widget(left);body.add_widget(self.market);self.root.add_widget(body)
        self.feedback=FitLabel(text='',maximum=sp(14),color=GREEN,size_hint_y=None,height=dp(24))
        self.feedback.bind(text=self._layout_event)
        self.root.add_widget(self.feedback)
        bar=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(8))
        self.action_bar=bar
        self.travel_button=_button('Перейти · 1 действие',self.go)
        self.battle_button=_button('Сразиться со стражей',self.battle)
        bar.add_widget(self.travel_button);bar.add_widget(self.battle_button)
        bar.add_widget(_button('Задания',lambda *_:self.owner.quests()))
        self.root.add_widget(bar)
        self.refresh()
        self.body.bind(size=self._layout_event)
        self.offers.bind(size=self._layout_event)
        self.army_box.bind(size=self._layout_event)
        self._layout_event()

    def layout_content(self):
        if not hasattr(self,'action_bar'):return
        h,w=self.root.height,self.root.width
        gap=min(dp(8),h*.012)
        self.root.padding=min(dp(12),h*.018);self.root.spacing=gap
        self.header.height=min(dp(58),h*.10)
        self.heading.font_size=min(sp(24),self.header.height*.55,w*.04)
        self.header.children[0].width=self.header.height
        self.city_image.width=self.header.height*1.15
        self.info.height=min(dp(30),h*.052);self.info.maximum=min(sp(14),self.info.height*.7)
        hint=getattr(self,'_market_hint','')
        self.feedback.height=min(dp(32),h*.063) if self.feedback.text and self.feedback.text!=hint else 0
        self.action_bar.height=min(64,max(42,h*.12))
        self.action_bar.spacing=gap
        for button in self.action_bar.children:button.font_size=min(20,self.action_bar.height*.36)
        portrait=w<h*.9
        self.body.orientation='vertical' if portrait else 'horizontal';self.body.spacing=gap
        self.army_panel.size_hint=(1,.35) if portrait else (.34,1)
        self.market.size_hint=(1,.65) if portrait else (.66,1)
        for panel in (self.army_panel,self.market):
            panel.padding=max(8,min(dp(10),h*.018));panel.spacing=gap*.6
        self.army_title.height=self.market_title.height=min(dp(28),h*.052)
        self.army_title.maximum=self.market_title.maximum=min(sp(18),h*.042)
        self.army_totals.height=min(dp(32),self.army_panel.height*.10)
        self.army_totals.maximum=min(sp(17),h*.036)
        self.guard_label.height=min(dp(58),self.army_panel.height*.18)
        self.guard_label.maximum=min(sp(14),h*.03)
        self.tabs.height=min(dp(40),h*.08)
        for button in self.tabs.children:button.font_size=min(sp(15),self.tabs.height*.4)

    def present(self):
        p=worlds.party(self.conn,self.faction)
        return p if p and p['city_id']==self.city['id'] else None

    def refresh(self):
        from utils.garrison_stats import garrison_profiles,garrison_totals
        selected=self.army_box.page_index
        p=self.present();self.army_box.clear_cards()
        self.info.text=('Чужой город · '+('Ваш отряд здесь' if p else 'Отряд в другом городе')+f' · Цены: {self.city["price"]}%')
        if p:
            profiles=garrison_profiles(self.conn,p['camp'],faction=self.faction)
            totals=garrison_totals(self.conn,p['camp'],profiles)
            self.army_totals.text='АТК '+format_number(totals['attack'])+'  ·  ЗАЩ '+format_number(totals['defense'])
            for name,count,image,exp,*_ in worlds._camp_units(self.conn,p['camp']):
                from mirror_layout import ArmyCard
                label=name.removeprefix('Странник: ').split(' / ')[0]
                self.army_box.add_card(ArmyCard(label,format_number(count),image,exp,self.accent))
        else:
            from mirror_layout import FitLabel
            self.army_totals.text='Ваш отряд в другом городе'
            self.army_box.add_card(FitLabel(text='Независимый город\n'+format_number(self.city['guards'])+' бойцов',color=GOLD))
        self.army_box.select(selected)
        guard,target=worlds.guard_profile(self.conn,self.faction,self.city)
        self.guard_label.text=((target or 'Стража')+': '+format_number(guard['unit_count'])+' бойцов\n'+
            f'АТК {guard["attack"]}  /  ЗАЩ {guard["defense"]} · Общая защита '+format_number(guard['defense']*guard['unit_count'])+'\n'+
            'Победа: +'+format_number(10_000+self.city['id']*5000)+' крон, опыт +1')
        party=worlds.party(self.conn,self.faction)
        edge=tuple(sorted((party['city_id'],self.city['id']))) if party else (0,0)
        connected=bool(self.conn.execute('SELECT 1 FROM portal_roads WHERE city1=? AND city2=?',edge).fetchone())
        self.travel_button.disabled=bool(p) or not connected
        cooldown=worlds.battle_ready(self.conn,self.faction) if p else 0
        self.battle_button.disabled=not p or cooldown>0
        self.battle_button.text=f'Отдых стражи: {cooldown} х.' if cooldown else ('Атаковать двор' if target else 'Бой со стражей')
        self.show_market(self.mode)

    def show_market(self,mode):
        selected=self.offers.page_index if mode==self.mode else 0
        if mode!=self.mode:self.feedback.text=''
        self._market_hint=''
        self.info.text=('Чужой город · '+('Ваш отряд здесь' if self.present() else 'Отряд в другом городе')+f' · Цены: {self.city["price"]}%')
        self.mode=mode;self.offers.clear_cards()
        self.offer_buttons=[]
        for key,button in self.tab_buttons.items():button.set_selected(key==mode)
        def offer(title,subtitle,callback,image=None):
            from mirror_layout import MarketCard
            card=MarketCard(title,subtitle,callback,image,caption='Продать' if title.startswith('Продать') else 'Купить')
            button=card.button
            button.disabled=not bool(self.present())
            self.offer_buttons.append(button)
            self.offers.add_card(card)
        if mode=='resources':
            for buy,title,base in [(True,'Купить 10 тыс. кристаллов',15000),(False,'Продать 10 тыс. кристаллов',10000)]:
                offer(title,('Цена: ' if buy else 'Вы получите: ')+format_number(worlds.price(self.city,base))+' крон',
                      lambda *_,b=buy:self.act(lambda:worlds.trade_crystals(self.conn,self.faction,b)))
        elif mode=='units':
            for unit in worlds.unit_offers(self.conn,self.faction):
                cost=worlds.price(self.city,max(1,unit['cost_money'])*2)*100
                offer(unit['unit_name'],f'АТК{unit["attack"]} · ЗАЩ{unit["defense"]}\n100: '+format_number(cost)+' кр.',
                      lambda *_,u=unit:self.act(lambda:worlds.recruit(self.conn,self.faction,u['id'])),unit['image_path'])
        else:
            from portal_items import champions
            p=self.present()
            eligible=champions(self.conn,self.faction,p['camp']) if p else []
            for artifact in worlds.artifact_offers(self.conn,self.faction):
                offer(artifact['name'],f'АТК+{artifact["attack"]}% ЗАЩ+{artifact["defense"]}%\n'+
                      format_number(worlds.price(self.city,artifact['cost']))+f' крон · {artifact["duration"]} х.',
                      lambda *_,a=artifact:self.artifact(a),artifact['image_url'])
                self.offer_buttons[-1].disabled=not eligible
                from portal_items import remaining
                active=self.conn.execute('SELECT artifact_id FROM portal_artifacts WHERE faction=? AND catalog_id=?',(self.faction,artifact['id'])).fetchone()
                left=remaining(self.conn,active[0]) if active else 0
                if left:
                    self.offer_buttons[-1].text=f'Действует · {left} х.'
                    self.offer_buttons[-1].disabled=True
            self.feedback.text=('Получатель: '+eligible[0]+' [3 класс] · Сила ×3,3') if eligible else 'Артефакты доступны только героям 3 класса в отряде.'
            self._market_hint=self.feedback.text
            self.info.text+=' · '+('Герой 3: '+eligible[0]+' · Сила ×3,3' if eligible else 'Нужен герой 3 класса')
        self.offers.select(selected)
        self._layout_event()

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
