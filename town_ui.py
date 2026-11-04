"""Town panorama and construction controls that stay usable on small screens."""
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.dropdown import DropDown
from otherworld_ui import WorldPopup,_button
from mirror_readable_ui import ReadableText
from mirror_readable_ui import compact_number
from strategy_ui import FACTIONS,GOLD,MUTED
from city_construction import CATALOG,building_counts,construction_allowed,city_owner
from town_scene import TownScene
from utils.helpers import format_number


class TownPopup(WorldPopup):
    def __init__(self,city_popup,**kwargs):
        self.owner=city_popup;self.conn=city_popup.conn;self.city=city_popup.city_name
        self.faction=city_owner(self.conn,self.city) or 'Нейтрал'
        self.player=city_popup.player_fraction
        self.selected='Больница'
        super().__init__(self.city,accent=FACTIONS.get(self.faction,GOLD),**kwargs)
        self.root._responsive_keep_geometry=True
        self.body=BoxLayout(spacing=dp(8));self.root.add_widget(self.body)
        self.scene=TownScene(self.conn,self.city,self.faction,self.choose)
        self.body.add_widget(self.scene)
        self.controls=BoxLayout(orientation='vertical',spacing=dp(6))
        self.chooser=DropDown(max_height=dp(264))
        self.selector=_button('Выбрать здание',lambda *_:self.chooser.open(self.selector),
                              size_hint_y=None,height=dp(48),font_size=sp(14))
        self.controls.add_widget(self.selector)
        self.selectors={}
        for name in CATALOG:
            button=_button(name,lambda *_,n=name:self.choose(n),height=dp(44),size_hint_y=None,font_size=sp(14))
            self.chooser.add_widget(button);self.selectors[name]=button
        self.detail_scroll=ScrollView(do_scroll_x=False,bar_width=dp(3))
        self.detail=ReadableText('',size=14);self.detail_scroll.add_widget(self.detail)
        self.controls.add_widget(self.detail_scroll)
        self.build=_button('Построить',self.purchase,size_hint_y=None,height=dp(44))
        self.controls.add_widget(self.build);self.body.add_widget(self.controls)
        self.message=ReadableText('',size=14,color=MUTED)
        self.budget=self.message
        self.root.add_widget(self.message)
        self.choose(self.selected);self.fit()

    def layout_content(self):
        if not hasattr(self,'controls'):return
        compact=self.root.height<dp(300)
        self.root.padding=dp(4 if compact else 6);self.root.spacing=dp(4 if compact else 5)
        self.header.height=dp(36 if compact else 40)
        self.heading.font_size=sp(18)
        self.header.children[0].width=dp(36 if compact else 40)
        portrait=self.root.height>self.root.width
        self.body.orientation='vertical' if portrait else 'horizontal'
        scene_share=.66 if self.root.width<dp(750) else .75
        self.scene.size_hint=(1,.45) if portrait else (scene_share,1)
        self.controls.size_hint=(1,.55) if portrait else (1-scene_share,1)
        self.selector.height=dp(44 if compact else 48);self.build.height=dp(44)
        self.controls.spacing=dp(4 if compact else 6)
        self.chooser.max_height=dp(264)
        for button in self.selectors.values():button.height=dp(44)

    def choose(self,name):
        self.chooser.dismiss()
        if name:self.selected=name
        self.scene.selected=self.selected;self.scene.refresh()
        counts=self.scene.counts;info=CATALOG[self.selected]
        row=self.conn.execute("SELECT amount FROM resources WHERE faction=? AND resource_type='Кроны'",(self.player,)).fetchone() if self.conn.execute("SELECT 1 FROM sqlite_master WHERE name='resources'").fetchone() else None
        money=row[0] if row else 0
        owned=construction_allowed(self.conn,self.city,self.player)
        built=sum(bool(counts.get(n,0)) for n in CATALOG)
        self.budget.text=f'Построено: {built} из {len(CATALOG)}'+(f' · {format_number(money)} крон' if owned else ' · Осмотр')
        self.selector.text=f'{self.selected} · {counts.get(self.selected,0)}/{info["max"]}'
        for key,button in self.selectors.items():
            button.text=f'{key} · {counts.get(key,0)}/{CATALOG[key]["max"]}'
            button.set_selected(key==self.selected)
        is_built=bool(counts.get(self.selected,0))
        self.detail.text=info['desc']+('\nПостроено' if is_built else '')
        self.detail_scroll.scroll_y=1
        if not is_built and (not owned or money<info['cost']):self.detail.text+=f'\nЦена: {format_number(info["cost"])} крон'
        self.build.disabled=not owned or bool(counts.get(self.selected,0)) or money<info['cost']
        self.build.text='Только осмотр' if not owned else 'Уже построено' if counts.get(self.selected,0) else 'Недостаточно крон' if money<info['cost'] else 'Построить · '+compact_number(info['cost']).replace('.0т','т').replace('.0м','м')
        if getattr(self.owner,'_is_undead_city',False):
            self.build.text='История города';self.build.disabled=False

    def purchase(self,*_):
        if getattr(self.owner,'_is_undead_city',False):
            from strategy_ui import show_city_lore
            image='files/city/death/'+{'Некрополь':'nekropolis','Горгум':'gorgum','Морготар':'morgotar'}.get(self.city,'city')+'.png'
            show_city_lore(self.owner,image);return
        if self.owner._build_building(self.selected,CATALOG[self.selected]['cost']):
            self.choose(self.selected)
            self.message.color=(.4,.9,.6,1);self.message.text='Построено: '+self.selected
        else:
            self.choose(self.selected)
            self.message.color=(1,.5,.4,1);self.message.text=getattr(self.owner,'_construction_error','Строительство недоступно.')
