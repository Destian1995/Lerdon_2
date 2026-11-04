"""Choose an equipped artifact around its hero, then spend the abyss gift."""
import sqlite3
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from otherworld_ui import WorldPopup,_button
from mirror_readable_ui import ReadableText
from frontend_ui import NaturalList
from strategy_ui import surface,SURFACE,GOLD
from monster_sites import owned_artifacts,upgrade_artifact


class RelicChoicePopup(WorldPopup):
    def __init__(self,widget,changed=lambda:None):
        self.widget=widget;self.conn=widget.conn;self.faction=widget.current_player_kingdom
        self.changed=changed;self.selected=None
        super().__init__('Дар бездны',accent=GOLD)
        self.items=owned_artifacts(self.conn,self.faction)
        heroes=list(dict.fromkeys(a['hero'] for a in self.items))
        self.hero_selector=Spinner(text=heroes[0] if heroes else 'Нет артефактов',values=heroes,
                                   size_hint_y=None,height=dp(44),font_size='15sp')
        self.root.add_widget(self.hero_selector)
        self.body=BoxLayout(spacing=dp(8));self.root.add_widget(self.body)
        self.hero_panel=surface(FloatLayout(),SURFACE,GOLD)
        self.hero_panel._responsive_keep_geometry=True
        self.hero_portrait=Image(size_hint=(None,None),fit_mode='contain')
        self.stats=ReadableText('',size=14,size_hint=(None,None),halign='center')
        self.hero_panel.add_widget(self.hero_portrait);self.hero_panel.add_widget(self.stats)
        self.equipment_slots={};self.slot_labels={};self.slot_images={}
        for key,caption in enumerate(('Оружие','Голова','Ноги','Туловище','Аксессуар')):
            key=str(key)
            button=_button('',lambda *_,k=key:self.select_slot(k),size_hint=(None,None),accent=GOLD)
            picture=Image(fit_mode='contain')
            button.add_widget(picture)
            def fit_image(b,_,image=picture):
                image.pos=(b.x+dp(4),b.y+dp(4));image.size=(b.width-dp(8),b.height-dp(8))
            button.bind(pos=fit_image,size=fit_image)
            label=ReadableText(caption,size=12,size_hint=(None,None),halign='center')
            self.equipment_slots[key]=button;self.slot_labels[key]=label;self.slot_images[key]=picture
            self.hero_panel.add_widget(button);self.hero_panel.add_widget(label)
        self.body.add_widget(self.hero_panel)
        self.detail_area=BoxLayout(orientation='vertical',spacing=dp(6))
        self.detail_scroll=ScrollView(do_scroll_x=False)
        detail=NaturalList(spacing=dp(10),padding=dp(8));self.detail_scroll.add_widget(detail)
        self.detail=ReadableText('',size=15);detail.add_widget(self.detail)
        self.detail_area.add_widget(self.detail_scroll)
        actions=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(6))
        self.upgrade_buttons={}
        for stat,title in (('attack','Улучшить\nатаку'),('defense','Улучшить\nзащиту')):
            button=_button(title,lambda *_,s=stat:self.choose(s),font_size=sp(14))
            self.upgrade_buttons[stat]=button;actions.add_widget(button)
        self.detail_area.add_widget(actions)
        self.body.add_widget(self.detail_area)
        self.root.add_widget(_button('Выбрать позже',self.dismiss,size_hint_y=None,height=dp(44)))
        self.hero_selector.bind(text=self.load_hero)
        self.hero_panel.bind(pos=self.arrange,size=self.arrange)
        self.load_hero();self.fit()

    def arrange(self,*_):
        from equipment_ui import layout_equipment
        layout_equipment(self.hero_panel,self.hero_portrait,self.stats,self.equipment_slots,self.slot_labels)

    def layout_content(self):
        if not hasattr(self,'body'):return
        portrait=self.root.height>self.root.width
        self.body.orientation='vertical' if portrait else 'horizontal'
        self.hero_panel.size_hint=(1,.6) if portrait else (.58,1)
        self.detail_area.size_hint=(1,.4) if portrait else (.42,1)
        self.arrange()

    def load_hero(self,*_):
        hero=self.hero_selector.text
        try:
            row=self.conn.execute('SELECT unit_image FROM garrisons WHERE unit_name=? AND unit_count>0 LIMIT 1',(hero,)).fetchone()
        except sqlite3.OperationalError:row=None
        self.hero_portrait.source=(row[0] if row and row[0] else 'files/pict/hero/default_image.png')
        self.stats.text=hero
        self.by_slot={str(a['slot']):a for a in self.items if a['hero']==hero}
        for key,button in self.equipment_slots.items():
            item=self.by_slot.get(key);button.disabled=item is None
            self.slot_images[key].source=item['image'] if item and item['image'] else ''
            self.slot_images[key].opacity=1 if item and item['image'] else 0
            button.text='' if item and item['image'] else '+' if item else '—'
        self.select_slot(next(iter(self.by_slot),None))

    def select_slot(self,key):
        self.selected=self.by_slot.get(key)
        for slot,button in self.equipment_slots.items():button.set_selected(slot==key)
        item=self.selected
        self.detail.text=(f'{item["name"]}\nАтака: {item["attack"]:g}% → {item["attack"]+550:g}%\n'
                          f'Защита: {item["defense"]:g}% → {item["defense"]+550:g}%\n'
                          'Выберите одну характеристику. Дар расходуется один раз.') if item else (
                          'У героев нет экипированных артефактов. Дар сохранён: вернитесь после покупки.')
        for button in self.upgrade_buttons.values():button.disabled=item is None

    def choose(self,stat):
        from ui_components import show_message
        item=self.selected
        if not item:return
        try:data=upgrade_artifact(self.conn,self.faction,item['table'],item['id'],stat,item['hero'],item['slot'])
        except ValueError as exc:
            show_message('Улучшение недоступно',str(exc));return
        from troop_movement import _screen
        screen=_screen(self.widget)
        if screen and getattr(screen,'season_manager',None):screen.season_manager.apply_artifact_bonuses(self.conn)
        self.dismiss();self.changed()
        show_message('Артефакт улучшен',f'{data["name"]}: {"атака" if stat=="attack" else "защита"} +{data[stat]:g}%')
