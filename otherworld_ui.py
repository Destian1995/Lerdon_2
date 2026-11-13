"""Portal expedition map and foreign-city garrison/merchant windows."""
import math

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, Ellipse, Line, Rectangle,Canvas,InstructionGroup
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
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
    from tactical_battle_bridge import operation_busy
    if operation_busy(conn):return True
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
    from mirror_readable_ui import ReadableButton
    result=ReadableButton(text=text,**kwargs)
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
        self._resize_fit=Clock.create_trigger(self.fit,0)
        self.root.bind(size=self._layout_event)
        self.fit()

    def fit(self,*_):
        self.size=(min(dp(1200),Window.width-dp(16)),min(dp(820),Window.height-dp(16)))
        center_after_resize(self)
        if hasattr(self,'_layout_event'):self._layout_event()

    def _layout(self,*_):
        if hasattr(self,'layout_content'):self.layout_content()

    def _opened(self,*_):
        Window.bind(on_resize=self._resize_fit)
        self.fit()

    def _closed(self,*_):
        Window.unbind(on_resize=self._resize_fit)
        self._resize_fit.cancel()
        self._layout_event.cancel()


def open_portal(city_popup):
    """Any owned city can open a gate; reopening resumes the existing party."""
    conn,faction=city_popup.conn,city_popup.player_fraction
    if _busy(conn):
        return
    from premium_access import allowed,require,return_from_mirror
    if worlds.party(conn,faction):
        if not allowed('mirror'):return return_from_mirror(conn,faction)
        city_popup.dismiss()
        OtherworldMap(conn,faction).open()
        return
    from portal_entry_ui import PortalEntryPopup
    gate=PortalEntryPopup(city_popup)
    gate.open()
    return gate


def _refresh_main(conn,faction):
    sync_resources(conn,faction)
    from otherworld_quest_ui import refresh_open_journals
    refresh_open_journals(conn,faction)
    # Military badges are event-driven, unlike the map's hero-flag polling.
    if _screen(conn):
        from game_process import refresh_map
        refresh_map()


class WorldMapCanvas(StencilView):
    def __init__(self,owner,**kwargs):
        super().__init__(**kwargs)
        self.owner=owner
        self.nodes=worlds.cities(owner.conn,owner.faction)
        self.hits=[]
        from map_camera import MapCamera
        self.camera=MapCamera(self.size,(0,0,*self.size))
        self.camera.minimum=self.camera.maximum=1.0
        self.touches={}
        from city_army_drag import CityArmyDrag
        self.army_drag=CityArmyDrag(self,self.city_at,self.army_at,self.send_army,
                                   faction=lambda:self.owner.faction)
        self._base=Canvas();self.canvas.add(self._base)
        self._water_layer=InstructionGroup()
        from kivy.core.image import Image as CoreImage
        self.texture=CoreImage(worlds.world(owner.conn,owner.faction)['background']).texture
        self.city_textures={c['id']:CoreImage(city_art(c['id'],owner.faction),mipmap=True).texture for c in self.nodes}
        from mirror_city_visuals import soft_shadow_texture,aerial_texture
        self._city_shadow=soft_shadow_texture()
        self._aerial=aerial_texture()
        self._city_labels={}
        from map_roads import TransportNetwork
        from map_terrain import load_terrain
        self.terrain=load_terrain(worlds.world(owner.conn,owner.faction)['background'])
        # Legacy road rows stay in saves; travel and rendering no longer use them.
        self.network=TransportNetwork()
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
        from mirror_city_visuals import city_scale,depth_order
        self._base.clear();self.hits=[];self.city_bounds=[]
        self.camera.configure(self.size,(0,0,*self.size))
        zoom=self.camera.zoom
        if len(self._city_labels)>64:self._city_labels.clear()
        s=min(self.width/1200,self.height/800)*zoom
        with self._base:
            Color(1,1,1,1)
            Rectangle(texture=self.texture,pos=self.point(0,0),size=(self.width*zoom,self.height*zoom))
            Color(.65,.76,.90,1)
            Rectangle(texture=self._aerial,pos=self.point(0,0),size=(self.width*zoom,self.height*zoom))
        self._base.add(self._water_layer)
        p=worlds.party(self.owner.conn,self.owner.faction)
        self._current_city=p['city_id'] if p and not worlds.beam(self.owner.conn,self.owner.faction) else None
        from otherworld_quests import objectives
        targets=objectives(self.owner.conn,self.owner.faction)
        ordered=depth_order(self.nodes)
        # Paint every ground shadow first, then buildings from back to front.
        # These are cached textures; no extra per-city clocks or shaders.
        self.city_draw_order=[city['id'] for city in ordered]
        with self._base:
            for city in ordered:
                x,y=self.point(city['x'],city['y']);size=max(36,156*s*city_scale(city['id'],city['y']))
                Color(.025,.035,.055,.48)
                Rectangle(texture=self._city_shadow,pos=(x-size*.42,y-size*.25),size=(size*1.04,size*.43))
                Color(.015,.025,.04,.38)
                Rectangle(texture=self._city_shadow,pos=(x-size*.37,y-size*.23),size=(size*.74,size*.23))
            for city in ordered:
                x,y=self.point(city['x'],city['y']);size=max(36,156*s*city_scale(city['id'],city['y']))
                Color(1,1,1,1)
                texture=self.city_textures[city['id']]
                icon_height=size*texture.height/texture.width
                Rectangle(texture=texture,pos=(x-size/2,y-icon_height*.3),size=(size,icon_height))
                self.city_bounds.append((x-size/2,y-icon_height*.3,size,icon_height,city['id']))
                label_key=(city['name'],min(sp(19),max(sp(15),self.width*.020))*(1+(zoom-1)*.6))
                if label_key not in self._city_labels:
                    label=CoreLabel(text=label_key[0],font_size=label_key[1],bold=True,color=TEXT)
                    label.refresh();self._city_labels[label_key]=label
                label=self._city_labels[label_key];w,h=label.texture.size
                for dx,dy in ((-1,-1),(1,-1),(-1,1),(1,1),(0,-2),(0,2),(-2,0),(2,0)):
                    Color(.025,.018,.05,.95)
                    Rectangle(texture=label.texture,pos=(x-w/2+dx,y-icon_height*.34-h+dy),size=(w,h))
                Color(1,1,1,1)
                Rectangle(texture=label.texture,pos=(x-w/2,y-icon_height*.34-h),size=(w,h))
                stationed=bool(worlds._camp_units(self.owner.conn,worlds.city_camp(
                    self.owner.conn,self.owner.faction,city['id'])))
                if self._current_city==city['id'] or stationed:
                    caption=CoreLabel(text='Ваш отряд' if self._current_city==city['id'] else 'Ваш гарнизон',font_size=min(sp(14),max(10,self.width*.0105)),bold=True,color=GREEN)
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
               ('header','resource_panel','status','action_bar')
               if (widget:=getattr(self.owner,name,None)) is not None):
            return False
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        if _busy(self.owner.conn):
            return True
        if getattr(touch,'is_mouse_scrolling',False):
            return True
        self.touches[touch.uid]={'touch':touch,'origin':touch.pos,'moved':False}
        touch.grab(self)
        if len(self.touches)>1:
            self.army_drag.cancel()
            for item in self.touches.values():item['moved']=True
        else:self.army_drag.down(touch)
        return True

    def on_touch_move(self,touch):
        if touch.uid not in self.touches:return super().on_touch_move(touch)
        item=self.touches[touch.uid]
        if _busy(self.owner.conn):
            self.army_drag.cancel();item['moved']=True;return True
        if self.army_drag.move(touch):
            if self.army_drag.active:item['moved']=True
            return True
        if len(self.touches)>1:
            self.army_drag.cancel()
            for active in self.touches.values():active['moved']=True
        elif math.dist(item['origin'],touch.pos)>7:
            item['moved']=True
        return True

    def on_touch_up(self,touch):
        item=self.touches.pop(touch.uid,None)
        if item is None:return super().on_touch_up(touch)
        touch.ungrab(self)
        if _busy(self.owner.conn):
            self.army_drag.cancel();return True
        if self.army_drag.up(touch):return True
        if not item['moved'] and not _busy(self.owner.conn):
            selected=self.city_at(touch.pos)
            city=next((c for c in self.nodes if c['id']==selected),None)
            if city:ForeignCityPopup(self.owner,city).open()
        return True

    def city_at(self,pos):
        padding=dp(8)
        bounds=[(math.dist((x+w/2,y+h*.3),pos),cid)
                for x,y,w,h,cid in getattr(self,'city_bounds',())
                if x-padding<=pos[0]<=x+w+padding and y-padding<=pos[1]<=y+h+padding]
        if bounds:return min(bounds)[1]
        hits=[(math.dist((x,y),pos),city['id']) for x,y,r,city in self.hits
              if math.dist((x,y),pos)<r]
        return min(hits)[1] if hits else None

    def army_at(self,city_id):
        p=worlds.party(self.owner.conn,self.owner.faction)
        return bool(p and not _busy(self.owner.conn) and worlds._camp_units(
            self.owner.conn,worlds.city_camp(self.owner.conn,self.owner.faction,city_id)))

    def send_army(self,source,destination):
        if not self.army_at(source):return
        from mirror_army_transfer import send_from_map
        send_from_map(self.owner,source,destination)

    def set_zoom(self,value,anchor=None):
        self.camera.set_zoom(value,anchor);self.redraw_camera()

    def change_zoom(self,amount,anchor=None):
        self.set_zoom(self.camera.zoom+amount,anchor)

    def redraw_camera(self):
        self.draw()
        if hasattr(self,'effects'):self.effects.update(0)


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
        for resource,icon in [('Кроны','coin'),('Кристаллы','crystal'),('Рабочие','workers')]:
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
        bar=GridLayout(cols=4,size_hint_y=None,height=dp(48),spacing=dp(8))
        self.action_bar=bar
        bar.size_hint=(None,None)
        self.return_button=_button('Вернуться через портал',self.home)
        bar.add_widget(self.return_button)
        self.quest_button=_button('Задания',self.quests,accent=self.accent)
        bar.add_widget(self.quest_button)
        self.next_turn_button=_button('Завершить ход',self.next_turn)
        bar.add_widget(self.next_turn_button)
        bar.add_widget(_button('Основная карта',self.dismiss))
        from developer_access import unlimited_actions
        if unlimited_actions(self.conn,self.faction):
            from developer_tools_ui import show_tools
            bar.add_widget(_button('DEV · Ресурсы',lambda *_:show_tools(self.conn,self.faction,self.refresh)))
        self.stage.add_widget(bar)
        from mirror_turn_ui import MirrorTurnProgress
        self.turn_progress=MirrorTurnProgress(self.accent,size_hint=(None,None),opacity=0)
        self.stage.add_widget(self.turn_progress)
        self._turn_requested=False;self._turn_progress_active=False
        self.stage.bind(size=self._layout_event,pos=self._layout_event)
        self._poll=Clock.schedule_interval(self.refresh,.5)
        self.bind(on_dismiss=lambda *_:self._poll.cancel())
        self.bind(on_open=self.map.effects.start,on_dismiss=self.map.effects.stop)
        self.bind(on_dismiss=self.close_beam)
        self.bind(on_dismiss=self.map.army_drag.cancel)
        self.refresh()
        self.update_turn_progress(0)
        self._layout_event()

    def fit(self,*_):
        self.size=(max(1,Window.width-8),max(1,Window.height-8))
        center_after_resize(self)
        if hasattr(self,'_layout_event'):self._layout_event()

    def layout_content(self):
        if not hasattr(self,'turn_progress'):return
        self.root.padding=dp(3);self.root.spacing=0
        x,y=self.stage.pos;w,h=self.stage.size
        portrait=w<h
        margin=dp(6)
        self._compact_hud=not portrait and w<dp(800)
        resource_width=dp(112 if self._compact_hud else 150) if not portrait else min(dp(170),w*.46)
        self.resource_panel.size=(resource_width,dp(82 if self._compact_hud else 110))
        self.resource_panel.pos=(x+margin,y+h-self.resource_panel.height-margin)
        for label in self.resource_labels.values():
            label.maximum=sp(14);label.minimum=sp(13)
        self.header.size=(max(dp(100),min(dp(380),w-resource_width-dp(66))),dp(44 if self._compact_hud else 38))
        self.header.pos=(self.resource_panel.right+dp(6),y+h-self.header.height-margin)
        self.heading.font_size=sp(14 if self._compact_hud else 18)
        self.heading.text=theme(self.faction)['name']+(
            '\n'+getattr(self,'_realm_city_name','') if self._compact_hud else '')
        self.map_close.size=(dp(40),dp(40))
        self.map_close.pos=(x+w-dp(40)-margin,y+h-dp(40)-margin)
        self.map_close.font_size=sp(24)
        self.status.size=(0,0) if self._compact_hud else (resource_width,dp(38))
        self.status.opacity=0 if self._compact_hud else 1
        self.status.pos=(self.resource_panel.x,self.resource_panel.y-dp(42))
        self.status.maximum=sp(14);self.status.minimum=sp(13)
        if portrait:
            self.header.size=(w-dp(58),dp(38))
            self.header.pos=(x+margin,y+h-dp(38)-margin)
            self.resource_panel.pos=(x+margin,self.header.y-dp(116))
            self.status.size=(max(1,w-resource_width-dp(18)),dp(110))
            self.status.pos=(self.resource_panel.right+dp(6),self.resource_panel.y)
        self.action_bar.cols=(3 if len(self.action_bar.children)>4 else 2) if portrait else len(self.action_bar.children)
        self.action_bar.size=(w-2*margin,dp(94 if portrait else 44))
        self.action_bar.pos=(x+margin,y+margin);self.action_bar.spacing=dp(6)
        self.return_button.text='Портал'
        for button in self.action_bar.children:button.font_size=sp(15)
        self.message.pos=(x+margin,self.action_bar.top+dp(4))
        self.message.size=(w-2*margin,dp(28));self.message.maximum=sp(13);self.message.minimum=sp(13)
        self.turn_progress.pos=(x+margin,self.action_bar.top+dp(4))
        self.turn_progress.size=(w-2*margin,dp(36))

    def update_turn_progress(self,dt):
        screen=_screen(self.conn)
        overlay=getattr(screen,'_turn_overlay',None)
        active=self._turn_requested or bool(overlay is not None and overlay.parent is not None)
        was_active=self._turn_progress_active
        self._turn_progress_active=active
        self.turn_progress.opacity=1 if active else 0
        self.message.opacity=0 if active else 1
        if active:
            progress=getattr(overlay,'_bar_progress',0) if overlay else 0
            label=getattr(overlay,'_status_label',None)
            status=getattr(label,'text','').removeprefix('Ход фракции: ')
            self.turn_progress.update(dt,progress,status)
            self.next_turn_button.disabled=True
            self.return_button.disabled=True
            self.quest_button.disabled=True
        elif was_active:
            self.quest_button.disabled=False
            self.refresh()

    def refresh(self,*_):
        # The battle worker owns a separate SQLite transaction while waiting
        # for tactical input. Expiry/schema writes here can otherwise block
        # the UI and throw "database is locked" behind the battle popup.
        if _busy(self.conn):return
        from portal_items import expire
        from campaign_guard import finish_portal_campaign
        screen=_screen(self.conn)
        if finish_portal_campaign(self.conn,self.faction,screen):return
        if expire(self.conn):
            screen=_screen(self.conn)
            if screen:screen.season_manager.apply_artifact_bonuses(self.conn)
            else:self.conn.commit()
        p=worlds.party(self.conn,self.faction)
        if not p:
            self.dismiss();return
        c=next(c for c in self.map.nodes if c['id']==p['city_id'])
        self._realm_city_name=c['name']
        if getattr(self,'_compact_hud',False):
            self.heading.text=theme(self.faction)['name']+'\n'+c['name']
        resources=dict(self.conn.execute('SELECT resource_type,amount FROM resources WHERE faction=?',(self.faction,)))
        row=self.conn.execute('SELECT moves_left FROM turn_check_move WHERE faction=?',(self.faction,)).fetchone()
        for resource,label in self.resource_labels.items():
            label.text=resource+'\n'+format_number(resources.get(resource,0))
        from developer_access import unlimited_actions
        actions='∞' if unlimited_actions(self.conn,self.faction) else str(row[0] if row else 0)
        self.status.text=f'{c["name"]} · Действий: {actions}'
        self.return_button.disabled=p['city_id']!=1 or _busy(self.conn)
        self.next_turn_button.disabled=_busy(self.conn)
        if self.map._current_city!=p['city_id']:self.map.draw()
        from otherworld_quests import state,cap_turns,pending
        run=state(self.conn,self.faction)
        self.quest_button.text='Задания '+str(int(run['detective']==3)+int(run['war']==3))+'/2' if run else 'Задания'
        left=cap_turns(self.conn,self.faction)
        if left:self.message.text=f'Награда Зазеркалья: лимиты ресурсов +35%, ещё {left} х.'
        else:
            rewards=pending(self.conn,self.faction)
            if rewards:self.message.text='Доступны награды: '+str(len(rewards))+'. Откройте задания, чтобы забрать.'
            elif self.message.text.startswith(('Доступны награды:','Награда Зазеркалья:')):self.message.text=''

    def home(self,*_):
        if _busy(self.conn):
            return
        try:
            worlds.return_home(self.conn,self.faction)
        except ValueError as exc:
            self.message.text=str(exc);return
        _refresh_main(self.conn,self.faction)
        self.dismiss()
        from morgana_covenant_ui import schedule_offer
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt:schedule_offer(self.conn,self.faction),0)

    def next_turn(self,*_):
        screen=_screen(self.conn)
        if screen and not self._turn_requested and not _busy(self.conn):
            self._turn_requested=True
            self.update_turn_progress(0)
            try:screen.process_turn(None)
            finally:
                self._turn_requested=False
                self.update_turn_progress(0)

    def quests(self,*_):
        if not _busy(self.conn):
            from otherworld_quest_ui import QuestJournal
            QuestJournal(self).open()

    def play_beam(self,source,destination):
        from otherworld_beam import BeamTravel
        centers={c['id']:(c['x'],c['y']) for c in self.map.nodes}
        points=[centers[source],centers[destination]]
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
        from mirror_readable_ui import ReadableText
        self.info=ReadableText('',size=14,color=GOLD)
        self.header.remove_widget(self.heading)
        self.city_titles=BoxLayout(orientation='vertical')
        self.city_titles.add_widget(self.heading);self.city_titles.add_widget(self.info)
        self.header.add_widget(self.city_titles,index=1)
        body=self.body=BoxLayout(spacing=dp(10))
        left=surface(BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(8)),SURFACE,self.accent)
        self.army_panel=left
        from mirror_layout import FitLabel
        self.army_title=ReadableText('Гарнизон',size=15,color=self.accent,bold=True)
        self.army_totals=ReadableText('',size=14,color=GREEN)
        self.guard_label=ReadableText('',size=14,color=GOLD)
        left.add_widget(self.army_title);left.add_widget(self.army_totals)
        from mirror_city_services import ExpeditionRoster
        self.army_box=ExpeditionRoster()
        left.add_widget(self.army_box)
        self.market=surface(BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(8)),SURFACE,GOLD)
        from mirror_layout import compact_frame
        compact_frame(left);compact_frame(self.market)
        self.market_title=FitLabel(text='Рынок Зазеркалья',color=GOLD,bold=True,size_hint_y=None)
        self.market.add_widget(self.market_title)
        tabs=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(5))
        self.tabs=tabs;self.tab_buttons={}
        for key,title in [('resources','Ресурсы'),('artifacts','Артефакты')]:
            button=_button(title,lambda *_,k=key:self.show_market(k))
            self.tab_buttons[key]=button;tabs.add_widget(button)
        self.market.add_widget(tabs)
        from mirror_layout import CardPager
        self.offers=CardPager(accent=GOLD)
        self.market.add_widget(self.offers)
        self.service_panel=surface(BoxLayout(orientation='vertical',padding=dp(6),spacing=dp(6)),SURFACE,self.accent)
        compact_frame(self.service_panel)
        self.city_titles.add_widget(self.guard_label)
        from otherworld_themes import image_path
        self.art_frame=StencilView()
        self.bartender=Image(source=image_path(self.faction,'women','bartender'),mipmap=True,fit_mode='contain')
        self.art_frame.add_widget(self.bartender)
        def fit_art(*_):
            self.bartender.pos=self.art_frame.pos;self.bartender.size=self.art_frame.size
        self.art_frame.bind(pos=fit_art,size=fit_art)
        self.service_panel.add_widget(self.art_frame)
        self.services=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(4))
        self.tavern_button=_button('Задания',self.open_tasks,accent=self.accent)
        self.market_button=_button('Рынок',self.open_market,accent=GOLD)
        self.recruit_button=_button('Найм',self.open_recruitment,accent=self.accent)
        self.tavern_button.size_hint_x=.40
        self.market_button.size_hint_x=.32
        self.recruit_button.size_hint_x=.28
        for widget in (self.tavern_button,self.market_button,self.recruit_button):self.services.add_widget(widget)
        self.service_panel.add_widget(self.services)
        body.add_widget(left);body.add_widget(self.service_panel);self.root.add_widget(body)
        self.feedback=ReadableText('',size=14,color=GREEN)
        self.feedback.bind(text=self._layout_event)
        self.root.add_widget(self.feedback)
        self.action_bar=BoxLayout(size_hint_y=None,height=dp(48))
        self.travel_button=_button('Телепортироваться',self.go)
        self.battle_button=_button('Напасть · +3% / 9 х.',self.battle)
        self.action_bar.add_widget(self.battle_button)
        left.add_widget(self.action_bar)
        self.refresh()
        self.body.bind(size=self._layout_event)
        self._layout_event()

    def layout_content(self):
        if not hasattr(self,'action_bar'):return
        self.root.padding=dp(6);self.root.spacing=dp(5)
        self.header.height=dp(76)
        self.heading.font_size=sp(18)
        self.header.children[0].width=dp(40)
        self.header.children[0].size_hint_y=None
        self.header.children[0].height=dp(44)
        self.header.children[0].pos_hint={'center_y':.5}
        self.city_image.width=dp(40)
        self.info.height=max(dp(22),self.info.texture_size[1]+dp(2))
        hint=getattr(self,'_market_hint','')
        self.feedback.height=max(dp(22),self.feedback.texture_size[1]+dp(2)) if self.feedback.text and self.feedback.text!=hint else 0
        portrait=self.root.width<dp(500) and self.root.height>self.root.width
        compact=self.root.height<dp(250) and not portrait
        self.body.orientation='vertical' if portrait else 'horizontal'
        self.body.spacing=dp(6)
        self.army_panel.size_hint=(1,1) if portrait else (.5,1)
        self.service_panel.size_hint=(1,None) if portrait else (.5,1)
        if portrait:self.service_panel.height=dp(240)
        self.army_panel.padding=dp(4);self.army_panel.spacing=dp(3)
        for index,widget in enumerate((self.army_title,self.army_totals)):
            if compact and widget.parent is self.army_panel:self.army_panel.remove_widget(widget)
            elif not compact and widget.parent is None:
                self.army_panel.add_widget(widget,index=len(self.army_panel.children)-index)
        self.info.text=getattr(self,'_city_info',self.info.text)
        self.guard_label.font_size=sp(12)
        self.guard_label.height=max(dp(18),self.guard_label.texture_size[1]+dp(2))
        self.header.height=max(dp(76),self.info.height+self.guard_label.height+dp(28))
        self.services.height=dp(44);self.action_bar.height=dp(44)
        self.market_title.height=0
        self.market_title.opacity=0
        self.market_title.maximum=sp(17)
        self.tabs.height=dp(44)
        for button in (*self.services.children,*self.tabs.children,self.travel_button,self.battle_button):
            button.font_size=sp(15)

    def open_tasks(self,*_):
        if _busy(self.conn) or not self.present():return
        from otherworld_quest_ui import QuestJournal
        self.journal=QuestJournal(self.owner,tavern_city=self.city['id'])
        self.journal.heading.text='Задания · '+self.city['name']
        self.journal.close_button.text='Вернуться в таверну'
        self.journal.open()
        return self.journal

    def present(self):
        p=worlds.party(self.conn,self.faction)
        return p if p and p['city_id']==self.city['id'] else None

    def open_market(self,*_):
        if _busy(self.conn):return
        from mirror_city_services import MirrorMarketPopup
        self.market_popup=MirrorMarketPopup(self);self.market_popup.open()

    def open_tavern(self,*_):
        if _busy(self.conn) or not self.present():return
        from mirror_city_services import MirrorTavernPopup
        self.tavern_popup=MirrorTavernPopup(self);self.tavern_popup.open()

    def open_recruitment(self,*_):
        if not self.present() or _busy(self.conn):return
        from otherworld_recruitment_ui import MirrorRecruitment
        self.recruitment=MirrorRecruitment(self)
        self.recruitment.open()

    def refresh(self):
        from utils.garrison_stats import garrison_profiles,garrison_totals
        from mirror_readable_ui import compact_number
        p=self.present();self.army_box.clear_cards()
        self.recruit_button.disabled=not bool(p)
        self.tavern_button.disabled=not bool(p)
        self.info.text=f'Найм и артефакты: {self.city["price"]}%'
        self._city_info=self.info.text
        camp=worlds.city_camp(self.conn,self.faction,self.city['id'])
        if worlds._camp_units(self.conn,camp):
            profiles=worlds.expedition_profiles(self.conn,self.faction,camp)
            totals=garrison_totals(self.conn,camp,profiles)
            self.army_totals.text='АТК '+compact_number(totals['attack'])+' · ЗАЩ '+compact_number(totals['defense'])
            rows=worlds._camp_units(self.conn,camp)
            rows.sort(key=lambda row:(str(row[7]).split()[0]=='1',row[0]))
            for name,count,image,exp,*_ in rows:
                from mirror_city_services import ExpeditionUnitRow
                self.army_box.add_card(ExpeditionUnitRow(self,name,count,image,exp,profiles.get(name,{})))
        else:
            from mirror_readable_ui import ReadableText
            self.army_totals.text=''
            self.army_box.add_card(ReadableText('Гарнизон пуст',size=14,color=MUTED))
        guard,target=worlds.guard_profile(self.conn,self.faction,self.city)
        self.guard_label.text=('Стража '+compact_number(guard['unit_count'])+' · ЗАЩ '+compact_number(guard['defense']*guard['unit_count'])+
                               ' · Победа: +3% урона на 9 ходов')
        party=worlds.party(self.conn,self.faction)
        connected=bool(party and party['city_id']!=self.city['id'])
        self.travel_button.disabled=bool(p) or not connected
        cooldown=worlds.battle_ready(self.conn,self.faction) if p else 0
        self.battle_button.disabled=not p or cooldown>0
        self.battle_button.text=f'Отдых стражи: {cooldown} х.' if cooldown else 'Напасть · +3% / 9 х.'
        self.action_bar.clear_widgets()
        self.action_bar.add_widget(self.battle_button if p else self.travel_button)
        self.show_market(self.mode)

    def show_market(self,mode):
        if mode=='units':
            return self.open_recruitment()
        if mode!=self.mode:self.feedback.text=''
        self._market_hint=''
        self.info.text=f'Найм и артефакты: {self.city["price"]}%'
        self._city_info=self.info.text
        self.mode=mode;self.offers.clear_cards()
        self.offer_buttons=[]
        for key,button in self.tab_buttons.items():button.set_selected(key==mode)
        crystals=getattr(self,'crystal_market',None)
        if crystals is not None and crystals.parent:crystals.parent.remove_widget(crystals)
        if mode=='artifacts':
            if self.offers.parent:self.offers.parent.remove_widget(self.offers)
            from mirror_artifact_shop import MirrorArtifactShop
            self.market_title.text='Артефакты'
            if not hasattr(self,'artifact_shop'):self.artifact_shop=MirrorArtifactShop(self)
            else:self.artifact_shop.refresh()
            if self.artifact_shop.parent is None:self.market.add_widget(self.artifact_shop)
            popup=getattr(self,'market_popup',None)
            if popup:popup._layout_event()
            self._layout_event();return
        shop=getattr(self,'artifact_shop',None)
        if shop is not None and shop.parent:shop.parent.remove_widget(shop)
        if self.offers.parent:self.offers.parent.remove_widget(self.offers)
        from mirror_crystal_market import MirrorCrystalMarket
        if not hasattr(self,'crystal_market'):self.crystal_market=MirrorCrystalMarket(self)
        else:self.crystal_market.refresh()
        self.market.add_widget(self.crystal_market)
        popup=getattr(self,'market_popup',None)
        if popup:popup._layout_event()
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

    def artifact(self,artifact,hero=None):
        def buy():
            worlds.buy_artifact(self.conn,self.faction,artifact['id'],hero=hero)
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
        from tactical_battle_bridge import launch_operation
        launch_operation(self.conn,
            lambda db:worlds.fight_guards(db,self.faction,tactical=True),
            self.battle_result,lambda error:setattr(self.feedback,'text',error))

    def battle_result(self,result):
        _refresh_main(self.conn,self.faction);self.refresh();self.owner.map.draw();self.owner.refresh()
        if result.get('quest_win'):
            self.feedback.text='Квест выполнен. Награда доступна в заданиях.'
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
        if result.get('tactical'):
            report()
            return
        ForeignBattle(result['rounds'],faction,defending,'attacker' if result['won'] else 'defender',
                      faction,'Экспедиция',result['city'],callback=report,
                      attacker_image=result.get('attacker_image'),
                      defender_image=result['guards'][0]['unit_image']).open()
