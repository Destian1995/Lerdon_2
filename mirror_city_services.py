"""City garrison list and the Mirror Realm's separate market and tavern."""
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import Image
from otherworld_ui import WorldPopup,_button,_busy
from mirror_layout import FitLabel,compact_frame
from strategy_ui import surface,INK,SURFACE,GOLD,MUTED,bind_row_tap
from otherworld_themes import image_path,resolve_unit_image,theme
from utils.helpers import format_number


class ExpeditionRoster(ScrollView):
    def __init__(self,**kwargs):
        super().__init__(do_scroll_x=False,bar_width=dp(4),**kwargs)
        self.rows=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(8))
        self.rows.bind(minimum_height=self.rows.setter('height'))
        self.add_widget(self.rows)

    def clear_cards(self):self.rows.clear_widgets()
    def add_card(self,card):self.rows.add_widget(card)


class ExpeditionUnitRow(BoxLayout):
    def __init__(self,city,name,count,image,experience,profile,**kwargs):
        super().__init__(size_hint_y=None,height=dp(48),padding=dp(4),spacing=dp(8),**kwargs)
        self.city,self.name,self.count,self.profile=city,name,count,profile
        self.experience=experience
        columns=[r[1] for r in city.conn.execute('PRAGMA table_info(units)')]
        row=city.conn.execute('SELECT * FROM units WHERE unit_name=?',(name,)).fetchone()
        self.unit=dict(zip(columns,row)) if row else {}
        cls=str(self.unit.get('unit_class','1')).split()[0]
        surface(self,(.09,.12,.17,1) if cls=='1' else (.17,.13,.08,1),city.accent if cls=='1' else GOLD)
        compact_frame(self)
        self.art=Image(source=resolve_unit_image(image or self.unit.get('image_path','')),size_hint_x=None,width=dp(42),mipmap=True,fit_mode='contain')
        from portrait_ui import style_portrait_image
        style_portrait_image(self.art,enabled=True)
        self.add_widget(self.art)
        from frontend_ui import NaturalList
        from mirror_readable_ui import ReadableText,compact_number
        copy=NaturalList(spacing=dp(1),pos_hint={'center_y':.5})
        from utils.unit_names import unit_display_name
        label=unit_display_name(name)
        self.title=ReadableText(label+(' · '+format_number(count) if cls=='1' else ''),size=15,bold=True,color=GOLD)
        self.stats=ReadableText('АТК '+compact_number(profile.get('attack',0)*count)+' · ЗАЩ '+compact_number(profile.get('defense',0)*count),size=14)
        self.summary=self.stats
        for w in (self.title,self.stats):copy.add_widget(w)
        self.add_widget(copy)
        copy.bind(minimum_height=lambda _,h:setattr(self,'height',max(dp(48),h+dp(8))))
        bind_row_tap(self,lambda *_:self.inspect())

    def inspect(self):
        if _busy(self.city.conn):return
        from unit_stats_ui import UnitStatsPanel
        popup=WorldPopup(self.title.text,accent=self.city.accent)
        body=BoxLayout(spacing=dp(12))
        multiplier=' × '+format_number(self.count) if str(self.unit.get('unit_class','1')).split()[0]=='1' else ''
        stats=[('Урон','files/pict/hire/sword.png',format_number(self.profile.get('attack',0))+multiplier),
               ('Защита','files/pict/hire/shield.png',format_number(self.profile.get('defense',0))+multiplier),
               ('Живучесть','files/pict/hire/health.png',format_number(self.unit.get('durability',0))),
               ('Опыт','files/pict/hire/class.png',str(self.experience)),
               ('Расход','files/pict/hire/consumption.png',str(self.unit.get('consumption',0)))]
        body.add_widget(UnitStatsPanel(stats,size_hint_x=.55))
        art=Image(source=self.art.source,mipmap=True,fit_mode='contain',size_hint_x=.45)
        from portrait_ui import style_portrait_image
        style_portrait_image(art,enabled=True)
        body.add_widget(art);popup.root.add_widget(body)
        from companion_form_ui import form_button
        def refresh_form_card():
            popup.dismiss();self.city.refresh()
        form_action=form_button(self.city.conn,self.city.faction,self.name,refresh_form_card)
        if form_action:popup.root.add_widget(form_action)
        popup.open();self.details_popup=popup


class MirrorMarketPopup(WorldPopup):
    def __init__(self,city,**kwargs):
        self.city=city
        super().__init__('Рынок · '+city.city['name'],accent=city.accent,**kwargs)
        market=city.market
        if market.parent:market.parent.remove_widget(market)
        market.size_hint=(1,1)
        self.root.add_widget(market)
        self.feedback=FitLabel(text='',size_hint_y=None,height=0,color=GOLD,maximum=sp(14))
        self.root.add_widget(self.feedback)
        self.header.height=dp(48)
        city.offers.external_navigation=True
        city.offers.nav.opacity=0
        city.offers.previous.text='‹';city.offers.next.text='›'
        for button in (city.offers.previous,city.offers.next):
            if button.parent:button.parent.remove_widget(button)
            button.size_hint=(None,1);button.width=dp(48)
            self.header.add_widget(button,index=1)
        city.offers.fit()
        def feedback(_,text):
            message='' if text==getattr(city,'_market_hint','') else text
            self.feedback.text=message
            self.feedback.height=dp(32) if message else 0
        self._feedback=feedback
        city.feedback.bind(text=self._feedback)
        self.bind(on_dismiss=self.closed)
        city.show_market(city.mode)

    def layout_content(self):
        self.header.height=dp(48)
        self.heading.text='Рынок'
        self.city.market_title.height=0
        self.city.market_title.opacity=0
        pager=self.city.offers
        for button in (pager.previous,pager.next):
            button.width=0
            button.opacity=0
            button.disabled=True

    def closed(self,*_):
        self.city.feedback.unbind(text=self._feedback)
        self.city.refresh()


class MirrorTavernPopup(WorldPopup):
    def __init__(self,city,**kwargs):
        self.city=city
        super().__init__('Таверна · '+city.city['name'],accent=city.accent,**kwargs)
        self.body=BoxLayout(spacing=dp(12))
        self.art=Image(source=image_path(city.faction,'women','bartender'),mipmap=True,fit_mode='contain')
        from portrait_ui import style_portrait_image
        style_portrait_image(self.art,enabled=True)
        self.body.add_widget(self.art)
        self.copy=BoxLayout(orientation='vertical',spacing=dp(12))
        self.greeting=FitLabel(text='Хозяйка таверны\n'+theme(city.faction)['name'],color=GOLD,bold=True,maximum=sp(24))
        self.story=FitLabel(text='Здесь сходятся слухи и чужие тайны. Расскажите, что ищете, — найдётся работа для вашего отряда.',maximum=sp(18))
        self.tasks=_button('Задания',self.quests,accent=city.accent,size_hint_y=None,height=dp(54))
        for w in (self.greeting,self.story,self.tasks):self.copy.add_widget(w)
        self.body.add_widget(self.copy);self.root.add_widget(self.body)
        self.root.add_widget(_button('Вернуться в город',self.dismiss,accent=city.accent,size_hint_y=None,height=dp(48)))

    def layout_content(self):
        if not hasattr(self,'body'):return
        self.body.orientation='vertical' if self.root.width<self.root.height*.8 else 'horizontal'
        self.art.size_hint=(1,.52) if self.body.orientation=='vertical' else (.48,1)
        self.copy.size_hint=(1,.48) if self.body.orientation=='vertical' else (.52,1)

    def quests(self,*_):
        if _busy(self.city.conn):return
        from otherworld_quest_ui import QuestJournal
        journal=QuestJournal(self.city.owner,tavern_city=self.city.city['id'])
        journal.heading.text='Задания таверны · '+self.city.city['name']
        journal.close_button.text='Вернуться в таверну'
        journal.open();self.journal=journal
