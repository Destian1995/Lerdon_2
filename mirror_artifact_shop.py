"""Compact relic inventory beside the ordinary five-slot hero equipment view."""
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.label import Label
from mirror_readable_ui import ReadableText,compact_number
from strategy_ui import surface,SURFACE,GOLD
from otherworld_ui import _button
import otherworlds as worlds
import portal_items


class MirrorArtifactShop(BoxLayout):
    def __init__(self,city,**kwargs):
        super().__init__(spacing=dp(8),**kwargs)
        self.city=city;self.conn=city.conn;self.faction=city.faction
        self.inventory=ScrollView(do_scroll_x=False,bar_width=dp(4))
        self.rows=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(6))
        self.rows.bind(minimum_height=self.rows.setter('height'));self.inventory.add_widget(self.rows)
        self.hero_area=BoxLayout(orientation='vertical',spacing=dp(4))
        self.hero_selector=Spinner(text='Нет героя 3 класса',size_hint_y=None,height=dp(44),font_size=sp(14))
        self.hero_area.add_widget(self.hero_selector)
        self.hero_panel=surface(FloatLayout(),SURFACE,GOLD)
        self.hero_panel._responsive_keep_geometry=True
        self.hero_portrait=Image(size_hint=(None,None),fit_mode='contain')
        self.stats=Label(text='',font_size=sp(14),size_hint=(None,None),halign='center',valign='middle')
        self.stats.bind(size=self.stats.setter('text_size'))
        self.hero_panel.add_widget(self.hero_portrait);self.hero_panel.add_widget(self.stats)
        self.equipment_slots={};self.slot_labels={};self.slot_images={}
        for index,caption in enumerate(('Оружие','Голова','Ноги','Туловище','Аксессуар')):
            key=str(index)
            button=_button('',lambda *_,k=key:self.inspect_slot(k),size_hint=(None,None),accent=GOLD)
            picture=Image(fit_mode='contain');button.add_widget(picture)
            def fit_image(b,_,image=picture):
                image.pos=(b.x+dp(4),b.y+dp(4));image.size=(max(1,b.width-dp(8)),max(1,b.height-dp(8)))
            button.bind(pos=fit_image,size=fit_image)
            label=Label(text=caption,font_size=sp(12),size_hint=(None,None),halign='center',valign='middle')
            label.bind(size=label.setter('text_size'))
            self.equipment_slots[key]=button;self.slot_labels[key]=label;self.slot_images[key]=picture
            self.hero_panel.add_widget(button);self.hero_panel.add_widget(label)
        self.hero_area.add_widget(self.hero_panel)
        self.add_widget(self.inventory);self.add_widget(self.hero_area)
        from equipment_ui import configure_artifact_shop
        configure_artifact_shop(self,self.inventory,self.hero_area)
        self.hero_panel.bind(pos=self.arrange,size=self.arrange)
        self.hero_selector.bind(text=self.load_hero)
        self.refresh()

    def arrange(self,*_):
        from equipment_ui import layout_equipment
        layout_equipment(self.hero_panel,self.hero_portrait,self.stats,self.equipment_slots,self.slot_labels)
        p=self.hero_panel
        if p.height<dp(170):
            inset=dp(4);cell=max(1,(p.width-inset*2)/5)
            size=max(1,min(dp(44),cell-dp(4),p.height*.36))
            caption=dp(18);belt=size+caption+inset*2
            top=max(1,p.height-belt-inset*2)
            self.hero_portrait.pos=(p.x+inset,p.y+belt)
            self.hero_portrait.size=(p.width*.32,top)
            self.stats.pos=(p.x+p.width*.34,p.y+belt)
            self.stats.size=(p.width*.64-inset,top);self.stats.font_size=sp(12)
            for index,key in enumerate(self.equipment_slots):
                slot=self.equipment_slots[key];label=self.slot_labels[key]
                slot.size=(size,size);slot.pos=(p.x+inset+index*cell+(cell-size)/2,p.y+caption+inset)
                label.pos=(p.x+inset+index*cell,p.y+inset)
                label.size=(cell,caption);label.font_size=sp(10)

    def refresh(self):
        heroes=portal_items.champions(self.conn,self.faction)
        self.hero_selector.height=dp(44) if len(heroes)>1 else 0
        self.hero_selector.opacity=1 if len(heroes)>1 else 0
        self.hero_selector.disabled=len(heroes)<=1
        present=self.city.present()
        self.eligible=portal_items.champions(self.conn,self.faction,present['camp']) if present else []
        self.hero_selector.values=heroes
        hero=self.hero_selector.text
        if hero not in heroes:self.hero_selector.text=(self.eligible or heroes or ['Нет героя 3 класса'])[0]
        self.load_hero()

    def load_hero(self,*_):
        hero=self.hero_selector.text
        row=self.conn.execute('SELECT image_path,attack,defense FROM units WHERE unit_name=?',(hero,)).fetchone()
        self.hero_portrait.source=(row[0] if row and row[0] else 'files/pict/hero/default_image.png')
        self.stats.text=hero+(f'\nАТК {compact_number(row[1])} · ЗАЩ {compact_number(row[2])}' if row else '')
        gear=self.conn.execute('''SELECT slot_type,artifact_id,image_url FROM hero_equipment
            WHERE faction_name=? AND hero_name=?''',(self.faction,hero)).fetchall()
        self.by_slot={str(slot):(aid,image) for slot,aid,image in gear if aid is not None}
        for slot,button in self.equipment_slots.items():
            item=self.by_slot.get(slot);source=item[1] if item else ''
            self.slot_images[slot].source=source or '';self.slot_images[slot].opacity=1 if source else 0
            button.text='' if source else '—';button.disabled=item is None
        self.rows.clear_widgets();self.buy_buttons=[]
        for item in worlds.artifact_offers(self.conn,self.faction):
            row=surface(BoxLayout(size_hint_y=None,height=dp(98),padding=dp(6),spacing=dp(6)),SURFACE,GOLD)
            row.add_widget(Image(source=item['image_url'],size_hint_x=None,width=dp(36),mipmap=True))
            active=self.conn.execute('SELECT artifact_id FROM portal_artifacts WHERE faction=? AND catalog_id=?',
                                     (self.faction,item['id'])).fetchone()
            left=portal_items.remaining(self.conn,active[0]) if active else 0
            text=(item['name']+f'\nАТК +{item["attack"]}% · ЗАЩ +{item["defense"]}%\n'+
                  compact_number(worlds.price(self.city.city,item['cost']))+f' крон · {item["duration"]} х.')
            label=ReadableText(text,size=14)
            row.add_widget(label)
            label.bind(height=lambda _,h,r=row:setattr(r,'height',max(dp(98),h+dp(12))))
            button=_button(f'Ещё {left} х.' if left else 'Купить',
                lambda *_,a=item:self.city.artifact(a,self.hero_selector.text),
                size_hint=(None,None),width=dp(82),height=dp(44),font_size=sp(14),pos_hint={'center_y':.5})
            button.disabled=bool(left) or hero not in self.eligible
            if left:button.text=f'Действует · {left} х.'
            row.add_widget(button);self.rows.add_widget(row);self.buy_buttons.append(button)
        self.city.offer_buttons=self.buy_buttons
        self.city.feedback.text=('Получатель: '+hero+' [3 класс]') if hero in self.eligible else (
            'Для покупки нужен герой 3 класса в отряде этого города.')
        self.city._market_hint=self.city.feedback.text
        self.arrange()

    def inspect_slot(self,key):
        item=self.by_slot.get(key)
        if not item:return
        row=self.conn.execute('SELECT name,attack,defense FROM artifacts WHERE id=?',(item[0],)).fetchone()
        if row:
            from ui_components import show_message
            left=portal_items.remaining(self.conn,item[0])
            show_message(row[0],f'Атака: +{row[1]}%\nЗащита: +{row[2]}%'+
                         (f'\nОсталось: {left} ходов' if left is not None else ''))
