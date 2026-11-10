"""Illustrated forest/swamp inspection with the real waiting garrisons."""
import os
import sqlite3

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView

from strategy_ui import surface,text_label,StrategyButton,INK,SURFACE,TEXT,MUTED,GOLD,FACTIONS
from terrain_icons import icon_path,icon_name,site_palette
from terrain_journeys import waiting_armies


def waiting_groups(conn,feature_id,moving=()):
    """Merge identical destinations/waits; preserve different unit experience."""
    columns={r[1] for r in conn.execute('PRAGMA table_info(garrisons)')}
    experience='COALESCE(experience,0)' if 'experience' in columns else '0'
    groups={}
    for camp in waiting_armies(conn):
        if camp['feature']['id']!=feature_id or camp['camp'] in moving:
            continue
        key=(camp['faction'],camp['destination'],camp['remaining'],camp['returning'])
        group=groups.setdefault(key,dict(faction=key[0],destination=key[1],remaining=key[2],returning=key[3],units={}))
        for name,count,image,exp in conn.execute(
                f'SELECT unit_name,unit_count,unit_image,{experience} FROM garrisons WHERE city_name=? AND unit_count>0',
                (camp['camp'],)):
            unit=group['units'].setdefault((name,exp),dict(name=name,count=0,image=image or '',experience=exp,training_city=camp['camp']))
            unit['count']+=count
    result=[]
    for group in groups.values():
        units=sorted(group['units'].values(),key=lambda u:(u['name'],u['experience']))
        if units:
            result.append(dict(group,units=units))
    return sorted(result,key=lambda g:(g['faction'],g['remaining'],g['destination']))


class TerrainSitePopup(Popup):
    def __init__(self,map_widget,site,**kwargs):
        super().__init__(title='',size_hint=(None,None),auto_dismiss=False,**kwargs)
        self.map_widget,self.conn,self.site=map_widget,map_widget.conn,dict(site)
        self._refresh_event=None
        self._fit_event=Clock.create_trigger(self._fit_current,0)
        self._signature=None
        self.groups=[]
        self.unit_cards=[]
        palette=site.get('icon_palette') or site_palette(getattr(map_widget,'_map_terrain',None),site)
        self.site_name=icon_name(site['kind'],site['icon_variant'],palette)
        self.accent=(.43,.66,.38,1) if site['kind']=='forest' else (.57,.61,.36,1)
        self.background=''
        self.background_color=(0,0,0,0)
        self.padding=dp(4)
        from window_theme import prepare_custom_popup
        prepare_custom_popup(self)
        self.root_panel=surface(BoxLayout(orientation='vertical',padding=dp(16),spacing=dp(12)),INK,self.accent)
        self.root_panel._strategy_fixed_layout=True
        self.header=BoxLayout(size_hint_y=None,spacing=dp(16))
        self.art_panel=surface(BoxLayout(size_hint_x=None,padding=dp(5)),SURFACE,self.accent)
        self.art=Image(source=str(icon_path(site['kind'],site['icon_variant'],palette)),mipmap=True)
        self.art_panel.add_widget(self.art)
        self.header.add_widget(self.art_panel)
        captions=BoxLayout(orientation='vertical',spacing=dp(4))
        self.name_label=text_label(self.site_name,24,TEXT,bold=True,size_hint_y=.32)
        kind='Лес' if site['kind']=='forest' else 'Болото'
        self.delay_label=text_label(f'{kind} · Задержка: {site["delay"]} х.',14,self.accent,bold=True,size_hint_y=.20)
        self.description=text_label('После ожидания отряд автоматически продолжит путь.',14,MUTED,size_hint_y=.48)
        for label in (self.name_label,self.delay_label,self.description):
            captions.add_widget(label)
        self.header.add_widget(captions)
        self.root_panel.add_widget(self.header)
        self.garrison=surface(BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(8)),SURFACE,self.accent)
        heading=BoxLayout(size_hint_y=None,height=dp(32),spacing=dp(8))
        heading.add_widget(Image(source='files/status/army.png',size_hint_x=None,width=dp(28),mipmap=True))
        self.garrison_heading=text_label('Задержанный гарнизон',17,bold=True)
        heading.add_widget(self.garrison_heading)
        self.garrison.add_widget(heading)
        self.scroll=ScrollView(do_scroll_x=False,bar_width=dp(3))
        self.cards=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(10))
        self.cards.bind(minimum_height=self.cards.setter('height'))
        self.scroll.add_widget(self.cards)
        self.garrison.add_widget(self.scroll)
        self.root_panel.add_widget(self.garrison)
        self.close_button=StrategyButton(text='Закрыть',size_hint_y=None,height=dp(44),accent=self.accent)
        self.close_button.bind(on_release=self.dismiss)
        self.root_panel.add_widget(self.close_button)
        self.content=self.root_panel
        self.bind(on_open=self._opened,on_dismiss=self._closed)
        self.fit()
        self.refresh()

    def _opened(self,*args):
        Window.bind(on_resize=self.fit)
        self.fit()
        self.refresh()
        if self._refresh_event is None:
            self._refresh_event=Clock.schedule_interval(self.refresh,1)

    def _align_center(self,*args):
        if self._is_open:
            self.center=(Window.width/2,Window.height/2)

    def _closed(self,*args):
        Window.unbind(on_resize=self.fit)
        self._fit_event.cancel()
        if self._refresh_event:
            self._refresh_event.cancel()
            self._refresh_event=None

    def fit(self,*args):
        width,height=args[1:3] if len(args)>=3 else Window.size
        self._layout(width,height)
        if self._is_open:
            self._fit_event()

    def _fit_current(self,*args):
        if self._is_open:
            self._layout(*Window.size)

    def _layout(self,width,height):
        self.size=(max(dp(1),min(dp(1040),width-dp(16))),max(dp(1),min(dp(720),height-dp(16))))
        compact=height<dp(480)
        changed=getattr(self,'_compact',compact)!=compact
        self._compact=compact
        self.header.height=dp(80 if compact else 184 if width>=dp(600) else 160)
        self.art_panel.width=dp(88 if compact else 184 if width>=dp(600) else 112)
        self.root_panel.padding=dp(12 if compact else 16)
        self.root_panel.spacing=dp(8 if compact else 12)
        self.name_label.font_size=sp(20 if width>=dp(600) else 17)
        self.delay_label.font_size=sp(12 if compact or width<dp(600) else 14)
        self.description.font_size=sp(11 if compact else 13)
        self.garrison_heading.font_size=sp(14 if width<dp(600) else 17)
        self.close_button.height=dp(40 if compact else 44)
        # SDL can publish Window.center a frame later than its size.
        self.center=(width/2,height/2)
        if changed:
            self._signature=None
            self.refresh()

    def refresh(self,*args):
        from troop_movement import _screen
        screen=_screen(self.map_widget)
        moving=getattr(screen,'_terrain_moving_camps',())
        try:
            groups=waiting_groups(self.conn,self.site['id'],moving)
        except sqlite3.Error:
            return
        signature=repr(groups)
        if signature==self._signature:
            return
        self._signature=signature
        self.groups=groups
        self.cards.clear_widgets()
        self.unit_cards=[]
        total=sum(u['count'] for g in groups for u in g['units'])
        self.garrison_heading.text=f'Задержанный гарнизон · {total:,}'.replace(',',' ')
        if not groups:
            self.cards.add_widget(text_label('Здесь пока нет задержанных войск.',14,MUTED,
                                             size_hint_y=None,height=dp(64)))
            return
        for group in groups:
            accent=FACTIONS.get(group['faction'],GOLD)
            panel=surface(BoxLayout(orientation='vertical',size_hint_y=None,padding=dp(6),spacing=dp(4)),INK,accent)
            panel.bind(minimum_height=panel.setter('height'))
            direction='возврат в' if group['returning'] else 'в город'
            panel.add_widget(text_label(f'{group["faction"]} · {direction} {group["destination"]}\n'
                                        f'Продолжит путь через {group["remaining"]} х.',12,accent,
                                        size_hint_y=None,height=dp(38)))
            for unit in group['units']:
                from monster_sites import effective_experience
                unit=dict(unit,experience=effective_experience(self.conn,group['faction'],unit['experience'],unit.get('training_city'),unit['name']))
                panel.add_widget(self.unit_card(unit,accent))
            self.cards.add_widget(panel)

    def unit_card(self,unit,accent):
        image=unit['image']
        unit_class='1'
        columns={r[1] for r in self.conn.execute('PRAGMA table_info(units)')}
        if 'unit_class' in columns:
            image_column='image_path' if 'image_path' in columns else "''"
            row=self.conn.execute(f'SELECT unit_class,{image_column} FROM units WHERE unit_name=? LIMIT 1',
                                  (unit['name'],)).fetchone()
            if row:
                unit_class=str(row[0])
                image=image or row[1]
        if not image or not os.path.isfile(image):
            image='files/pict/hire/sword.png'
        card=surface(BoxLayout(size_hint_y=None,height=dp(64 if self._compact else 82),padding=dp(6),spacing=dp(8)),SURFACE,accent)
        card.add_widget(Image(source=image,size_hint_x=None,width=dp(46 if self._compact else 62),mipmap=True))
        labels=BoxLayout(orientation='vertical',spacing=dp(2))
        from utils.unit_names import unit_display_name
        labels.add_widget(text_label(unit_display_name(unit['name']),12 if self._compact else 14,bold=True,size_hint_y=.5))
        labels.add_widget(text_label(f'Бойцов: {unit["count"]:,}'.replace(',',' '),12 if self._compact else 14,GOLD,size_hint_y=.3))
        labels.add_widget(text_label(f'Опыт: {unit["experience"]}',10 if self._compact else 11,MUTED,size_hint_y=.2))
        card.add_widget(labels)
        self.unit_cards.append(card)
        return card


def open_terrain_site(widget,site):
    previous=getattr(widget,'_terrain_site_popup',None)
    if previous:
        previous.dismiss()
    popup=widget._terrain_site_popup=TerrainSitePopup(widget,site)
    def clear(*args):
        if getattr(widget,'_terrain_site_popup',None) is popup:
            widget._terrain_site_popup=None
    popup.bind(on_dismiss=clear)
    popup.open()
    return popup
