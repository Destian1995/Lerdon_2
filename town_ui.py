"""Town panorama and construction controls that stay usable on small screens."""
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color,RoundedRectangle,Line
from otherworld_ui import WorldPopup,_button
from mirror_readable_ui import ReadableText
from mirror_readable_ui import compact_number
from mirror_layout import FitLabel
from strategy_ui import FACTIONS,GOLD,MUTED,TEXT
from city_construction import CATALOG,building_counts,construction_allowed,city_owner,building_name,HOSPITAL_GROWTH,FACTORY_YIELD,DEFENSE_BONUS
from town_scene import TownScene
from town_art import building_path
from utils.helpers import format_number


BUILDING_SUMMARIES={
    'Больница':(f'+{HOSPITAL_GROWTH} жителей и рабочих/ход',(.45,.88,.56,1)),
    'Фабрика':(f'+{FACTORY_YIELD} кристаллов/ход',(.35,.78,1,1)),
    'Стена':(f'+{DEFENSE_BONUS*100:g}% защиты гарнизона',(.45,.88,.56,1)),
    'Рынок':('+10% дохода крон',GOLD),
    'Кузница':('−5% расхода кристаллов гарнизона',(.35,.78,1,1)),
    'Цитадель':('+500 к лимиту армии',(.45,.88,.56,1)),
}


class SummaryLabel(Label):
    """Keep the resource strip to one line, including on narrow phones."""
    def __init__(self,**kwargs):
        super().__init__(halign='left',valign='middle',**kwargs)
        self.bind(size=self.fit,text=self.fit)

    def fit(self,*_):
        font=sp(14)
        measure=CoreLabel(text=self.text,font_size=font,font_name=self.font_name)
        measure.refresh()
        self.font_size=max(1,int(min(font,font*max(1,self.width-2)/max(1,measure.texture.width),
                                    font*max(1,self.height-2)/max(1,measure.texture.height)))-1)
        self.text_size=(self.width,self.height)


class BuildingRow(ButtonBehavior,BoxLayout):
    def __init__(self,town,name):
        super().__init__(size_hint_y=None,padding=dp(8),spacing=dp(8))
        self.name=name;self.is_built=False;self.town=town
        self.compact_mode=False;self.natural_height=dp(76)
        with self.canvas.before:
            self.fill_color=Color(.065,.085,.12,1)
            self.fill=RoundedRectangle(radius=[dp(7)])
        with self.canvas.after:
            self.border_color=Color(*GOLD[:3],.3)
            self.border=Line(width=dp(.8))
        self.art=Image(size_hint=(None,None),size=(dp(40),dp(40)),pos_hint={'center_y':.5},fit_mode='contain')
        self.add_widget(self.art)
        copy=BoxLayout(orientation='vertical',spacing=dp(2),size_hint_y=None,pos_hint={'center_y':.5})
        self.copy=copy
        copy.bind(minimum_height=copy.setter('height'))
        self.title=ReadableText(name,size=15,bold=True)
        self.effect=ReadableText(CATALOG[name]['desc'],size=13,color=MUTED)
        self.status=ReadableText('',size=13,color=GOLD)
        for label in (self.title,self.effect,self.status):copy.add_widget(label)
        self.add_widget(copy)
        copy.bind(height=self.measure)
        self.compact_label=FitLabel(maximum=sp(13),minimum=sp(11),halign='center',bold=True)
        self.bind(pos=self.layout_frame,size=self.layout_frame,
                  on_release=lambda *_:town.choose(name))

    def measure(self,_,height):
        previous=self.natural_height
        self.natural_height=max(dp(76),height+dp(16))
        if not self.compact_mode:self.height=self.natural_height
        if abs(previous-self.natural_height)>.5:self.town._layout_event()

    def set_compact(self,enabled):
        if enabled!=self.compact_mode:
            self.compact_mode=enabled
            self.clear_widgets()
            for child in ((self.compact_label,) if enabled else (self.art,self.copy)):self.add_widget(child)
        self.padding=dp(4 if enabled else 8)
        self.spacing=0 if enabled else dp(8)
        self.size_hint_y=1 if enabled else None
        if not enabled:self.height=self.natural_height
        self.compact_label.maximum=sp(13);self.compact_label.minimum=sp(11)

    def layout_frame(self,*_):
        self.fill.pos=self.pos;self.fill.size=self.size
        self.border.rounded_rectangle=(*self.pos,*self.size,dp(7))

    def refresh(self,town):
        display_name=building_name(town.scene.faction,self.name)
        self.title.text=display_name
        self.is_built=bool(town.scene.counts.get(self.name,0))
        self.art.source=building_path(town.scene.faction,self.name)
        grey=(.48,.50,.53,1)
        self.art.color=(.48,.48,.48,.65) if self.is_built else (1,1,1,1)
        self.title.color=grey if self.is_built else TEXT
        self.effect.color=grey if self.is_built else MUTED
        self.status.color=grey if self.is_built else GOLD
        self.status.text='Построено' if self.is_built else format_number(CATALOG[self.name]['cost'])+' крон'
        price=compact_number(CATALOG[self.name]['cost']).replace('.0т','т').replace('.0м','м')
        self.compact_label.text=display_name+'\n'+('Построено' if self.is_built else price+' кр.')
        self.compact_label.color=grey if self.is_built else TEXT
        self.fill_color.rgba=(.085,.09,.105,1) if self.is_built else (.065,.085,.12,1)
        self.border_color.rgba=(*GOLD[:3],.9) if self.name==town.selected else (*grey[:3],.3)


class TownPopup(WorldPopup):
    def __init__(self,city_popup,**kwargs):
        self.owner=city_popup;self.conn=city_popup.conn;self.city=city_popup.city_name
        self.faction=city_owner(self.conn,self.city) or 'Нейтрал'
        self.player=city_popup.player_fraction
        self.selected='Больница'
        super().__init__(self.city,accent=FACTIONS.get(self.faction,GOLD),**kwargs)
        self.root._responsive_keep_geometry=True
        self.body=BoxLayout(spacing=dp(8));self.root.add_widget(self.body)
        self.scene_panel=BoxLayout(orientation='vertical',spacing=dp(4))
        self.scene=TownScene(self.conn,self.city,self.faction,self.choose)
        self.scene_panel.add_widget(self.scene);self.body.add_widget(self.scene_panel)
        self.controls=BoxLayout(orientation='vertical',spacing=dp(6))
        self.selector=ReadableText('',size=16,color=GOLD,bold=True)
        self.controls.add_widget(self.selector)
        self.building_area=BoxLayout()
        self.building_list=GridLayout(cols=1,spacing=dp(5),padding=dp(2))
        self.selectors={name:BuildingRow(self,name) for name in CATALOG}
        for row in self.selectors.values():self.building_list.add_widget(row)
        self.building_area.add_widget(self.building_list)
        self.controls.add_widget(self.building_area)
        self.build=_button('Построить',self.purchase,size_hint_y=None,height=dp(44))
        self.controls.add_widget(self.build);self.body.add_widget(self.controls)
        self.resource_strip=BoxLayout(size_hint_y=None,height=dp(24),spacing=dp(10))
        self.message=SummaryLabel(color=GOLD,size_hint_x=None,width=dp(100))
        self.budget=self.message
        self.effect_summary=SummaryLabel()
        self.resource_strip.add_widget(self.message)
        self.resource_strip.add_widget(self.effect_summary)
        self.root.add_widget(self.resource_strip)
        self.building_area.bind(size=self.fit_catalog)
        self.choose(self.selected);self.fit()

    def layout_content(self):
        if not hasattr(self,'controls'):return
        compact=self.root.height<dp(300)
        self.root.padding=dp(4 if compact else 6);self.root.spacing=dp(2 if compact else 5)
        self.header.height=dp(36 if compact else 40)
        self.heading.font_size=sp(18)
        self.header.children[0].width=dp(36 if compact else 40)
        portrait=self.root.height>self.root.width
        self.emergency=not portrait and self.root.width<dp(440) and compact
        self.body.orientation='vertical' if portrait or self.emergency else 'horizontal'
        scene_share=.50 if self.root.width<dp(750) else .75
        self.controls.orientation='horizontal' if self.emergency else 'vertical'
        if self.emergency:
            if self.selector.parent:self.controls.remove_widget(self.selector)
            self.scene_panel.size_hint=(1,1)
            self.controls.size_hint=(1,None);self.controls.height=dp(96)
            self.build.size_hint=(None,1);self.build.width=dp(88)
        else:
            if self.selector.parent is None:self.controls.add_widget(self.selector,index=len(self.controls.children))
            self.scene_panel.size_hint=(1,.45) if portrait else (scene_share,1)
            self.controls.size_hint=(1,.55) if portrait else (1-scene_share,1)
            self.build.size_hint=(1,None)
        self.selector.opacity=0 if compact else 1
        self.selector.height=0 if compact else max(dp(20),self.selector.texture_size[1]+dp(2))
        self.resource_strip.height=dp(22 if compact else 24)
        self.message.width=min(dp(120),self.root.width*.28)
        self.heading.text=self.city+(' · '+compact_number(getattr(self,'money',0))+' кр.' if compact else '')
        if not self.emergency:self.build.height=dp(44)
        self.build.text=(building_name(self.faction,self.selected)+' · ' if compact else '')+getattr(self,'build_caption','Построить')
        self.controls.spacing=dp(2 if compact else 6)
        self.fit_catalog()

    def fit_catalog(self,*_):
        if not hasattr(self,'building_area'):return
        rows=list(self.selectors.values())
        for row in rows:row.copy.width=max(1,self.building_area.width-dp(72))
        required=sum(row.natural_height for row in rows)+dp(5)*5+dp(4)
        compact=getattr(self,'emergency',False) or required>self.building_area.height
        three_columns=(getattr(self,'emergency',False) or
                       self.building_area.width>=dp(220) and self.building_area.height<dp(230) or
                       self.building_area.width>=dp(144) and self.building_area.height<dp(146))
        self.building_list.cols=(3 if three_columns else 2) if compact else 1
        self.building_list.spacing=dp(4 if compact else 5)
        for row in rows:row.set_compact(compact)

    def choose(self,name):
        if name:self.selected=name
        self.scene.selected=self.selected;self.scene.refresh()
        self.faction=self.scene.faction
        counts=self.scene.counts;info=CATALOG[self.selected]
        row=self.conn.execute("SELECT amount FROM resources WHERE faction=? AND resource_type='Кроны'",(self.player,)).fetchone() if self.conn.execute("SELECT 1 FROM sqlite_master WHERE name='resources'").fetchone() else None
        money=row[0] if row else 0
        self.money=money
        owned=construction_allowed(self.conn,self.city,self.player)
        self.budget.text=compact_number(money)+' крон' if owned else 'Осмотр'
        self.budget.color=GOLD
        self.effect_summary.text,self.effect_summary.color=BUILDING_SUMMARIES[self.selected]
        self.selector.text=building_name(self.scene.faction,self.selected)
        for row in self.selectors.values():row.refresh(self)
        self.build.disabled=not owned or bool(counts.get(self.selected,0)) or money<info['cost']
        self.build.text='Только осмотр' if not owned else 'Уже построено' if counts.get(self.selected,0) else 'Недостаточно крон' if money<info['cost'] else 'Построить · '+compact_number(info['cost']).replace('.0т','т').replace('.0м','м')
        self.build_caption=self.build.text
        self._layout_event()

    def purchase(self,*_):
        if self.owner._build_building(self.selected,CATALOG[self.selected]['cost']):
            self.choose(self.selected)
        else:
            self.choose(self.selected)
            self.message.color=(1,.5,.4,1);self.message.text=getattr(self.owner,'_construction_error','Строительство недоступно.')
