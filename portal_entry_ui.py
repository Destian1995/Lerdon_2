"""Illustrated, faction-specific entrance to the other world."""
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image

from otherworld_ui import WorldPopup,OtherworldMap,_busy,_refresh_main
import otherworlds as worlds
from strategy_ui import surface,text_label,StrategyButton,INK,MUTED,TEXT
from utils.helpers import format_number

# All five playable factions have separately painted gateway illustrations.
PORTALS={
    'Север':('north','Ледяные врата',(.46,.79,1,1)),
    'Эльфы':('elves','Врата древолесья',(.43,.90,.63,1)),
    'Вампиры':('vampires','Багровые врата',(.97,.43,.67,1)),
    'Адепты':('adepts','Астральный разлом',(1,.70,.34,1)),
    'Элины':('elines','Солнечные врата',(1,.86,.48,1)),
}


def portal_art(faction):
    key=PORTALS.get(faction,PORTALS['Адепты'])[0]
    return 'files/portals/portal_'+key+'.png'


class PassageRule(BoxLayout):
    def __init__(self,title,description,icon,accent,**kwargs):
        super().__init__(spacing=dp(10),padding=dp(10),**kwargs)
        background=tuple(.035+v*.045 for v in accent[:3])+(1,)
        surface(self,background,accent)
        self.icon=Image(source=icon,size_hint=(None,None),pos_hint={'center_y':.5},mipmap=True)
        self.add_widget(self.icon)
        self.copy=BoxLayout(orientation='vertical',size_hint_y=None,pos_hint={'center_y':.5},spacing=dp(3))
        self.title=text_label(title,18,accent,bold=True,size_hint_y=None)
        self.description=text_label(description,14,TEXT,size_hint_y=None)
        self.copy.add_widget(self.title);self.copy.add_widget(self.description)
        self.add_widget(self.copy)
        self.bind(size=self.fit)

    def fit(self,*_):
        inset=min(dp(12),self.height*.12)
        self.padding=inset
        self.spacing=min(dp(12),self.width*.025)
        self.icon.size=(min(dp(42),self.height*.62),)*2
        self.title.font_size=min(sp(19),self.height*.27,max(11,self.width/17))
        self.description.font_size=min(sp(14),self.height*.21,max(10,self.width/23))
        self.title.height=self.title.font_size*1.35
        lines=self.description.text.count('\n')+1
        self.description.height=self.description.font_size*(1.4*lines if lines>1 else 1.6)
        self.copy.spacing=min(dp(4),self.height*.04)
        needed=self.title.height+self.description.height+self.copy.spacing
        scale=min(1,max(1,self.height-2*inset)/max(1,needed))
        self.title.font_size*=scale;self.title.height*=scale
        self.description.font_size*=scale;self.description.height*=scale
        self.copy.height=self.title.height+self.description.height+self.copy.spacing


class PortalEntryPopup(WorldPopup):
    def __init__(self,city_popup,**kwargs):
        self.city_popup=city_popup
        self.conn,self.faction=city_popup.conn,city_popup.player_fraction
        self.portal_key,self.portal_name,self.accent=PORTALS.get(self.faction,PORTALS['Адепты'])
        self.body=None
        super().__init__('ПОРТАЛ  /  '+worlds.WORLD_NAME,accent=self.accent,**kwargs)
        self.body=BoxLayout(spacing=dp(16))
        self.art_panel=surface(BoxLayout(padding=dp(5)),INK,self.accent)
        self.art=Image(source=portal_art(self.faction),mipmap=True,fit_mode='contain')
        self.art_panel.add_widget(self.art)
        self.details=BoxLayout(orientation='vertical',spacing=dp(9))
        self.faction_label=text_label(self.faction.upper()+'  /  ПЕРЕХОД МЕЖДУ МИРАМИ',12,self.accent,
                                      bold=True,size_hint_y=None)
        self.title_label=text_label(self.portal_name,32,TEXT,bold=True,size_hint_y=None)
        self.source_label=text_label('Из города '+city_popup.city_name+' — бойцы и герои 2–3 классов',15,MUTED,
                                     size_hint_y=None)
        for label in (self.faction_label,self.title_label,self.source_label):
            self.details.add_widget(label)
        self.rules=[
            PassageRule('1 действие','Герой 4 класса остаётся в городе','files/pict/hire/sword.png',self.accent),
            PassageRule('Чужие города','Торговля, бои и расследования.\nНовые юниты, артефакты и секретные концовки.',
                        'files/buildings/poly.png',self.accent),
            PassageRule('Обратный путь','Через Врата странников','files/status/resource_box/crystal.png',self.accent),
        ]
        for rule in self.rules:self.details.add_widget(rule)
        self.body.add_widget(self.art_panel);self.body.add_widget(self.details)
        self.root.add_widget(self.body)
        self.readiness=text_label('',15,MUTED,size_hint_y=None)
        self.root.add_widget(self.readiness)
        self.status=text_label('',15,(1,.48,.38,1),size_hint_y=None,height=0)
        self.root.add_widget(self.status)
        self.enter_button=StrategyButton(text='Отправить гарнизон · 1 действие',accent=self.accent,primary=True,
                                         size_hint_y=None)
        self.enter_button.bind(on_release=self.enter)
        self.enter_button.base=tuple(.045+c*.14 for c in self.accent[:3])+(1,)
        self.enter_button._feedback(0)
        self.root.add_widget(self.enter_button)
        self._entry_fit=Clock.create_trigger(self._fit_entry,0)
        self.body.bind(size=self._entry_fit)
        self.refresh_readiness()
        self.fit()

    def fit(self,*_):
        super().fit()
        if Window.width>=Window.height:
            self.height=min(self.height,self.width*.56)
        if self.body is not None and hasattr(self,'_entry_fit'):
            self._fit_entry()
            self._entry_fit()

    def _fit_entry(self,*_):
        from window_theme import center_after_resize
        portrait=self.width<self.height
        compact=self.height<430
        inset=min(dp(16),self.height*.025)
        gap=min(dp(12),self.height*.018)
        self.root.padding=inset;self.root.spacing=gap
        self.header.height=min(dp(48),self.height*.092)
        self.heading.font_size=min(sp(23),self.header.height*.5,self.width*.038)
        close=self.header.children[0]
        close.width=self.header.height
        self.enter_button.height=min(dp(58),self.height*.12)
        self.enter_button.font_size=min(sp(20),self.enter_button.height*.38,self.width*.043)
        self.readiness.height=min(dp(30),self.height*.057)
        self.readiness.font_size=min(sp(15),self.readiness.height*.53,self.width*.036)
        self.status.height=min(dp(44),self.height*.09) if self.status.text else 0
        self.status.font_size=min(sp(15),self.width*.036)
        self.body.orientation='vertical' if portrait else 'horizontal'
        self.body.spacing=gap
        self.art_panel.size_hint=(1,.43) if portrait else (.53,1)
        self.details.size_hint=(1,.57) if portrait else (.47,1)
        self.art_panel.padding=min(dp(5),self.height*.009)
        self.details.spacing=min(dp(10),self.details.height*.021)
        available=max(80,self.details.height)
        self.faction_label.height=min(dp(24),available*.064)
        self.faction_label.font_size=min(sp(12),self.faction_label.height*.7,self.details.width*.034)
        self.title_label.height=min(dp(50),available*.135)
        self.title_label.font_size=min(sp(34),self.title_label.height*.76,self.details.width*.071)
        self.source_label.height=min(dp(48),available*(.14 if portrait or compact else .105))
        self.source_label.font_size=min(sp(15),max(10,self.source_label.height*.4),self.details.width*.039)
        center_after_resize(self)

    def refresh_readiness(self):
        units=worlds.departure_units(self.conn,self.city_popup.city_name)
        heroes=any(str(row[7]).split()[0] in ('2','3') for row in units)
        soldiers=sum(row[1] for row in units if str(row[7]).split()[0]=='1')
        row=self.conn.execute('SELECT moves_left FROM turn_check_move WHERE faction=?',(self.faction,)).fetchone()
        moves=row[0] if row else 0
        from developer_access import unlimited_actions
        if unlimited_actions(self.conn,self.faction):moves=max(1,moves)
        ready=bool(heroes and soldiers and moves>0)
        self.enter_button.disabled=not ready or _busy(self.conn)
        from premium_access import allowed
        if not allowed('mirror'):self.enter_button.disabled=_busy(self.conn)
        if not heroes:
            self.readiness.text='Для путешествия нужен герой 2–3 класса в гарнизоне.'
        elif not soldiers:
            self.readiness.text='Герою нужны войска для путешествия.'
        elif moves<1:
            self.readiness.text='Нет действий — завершите текущий ход.'
        else:
            self.readiness.text='Готовы к переходу: '+format_number(soldiers)+' бойцов и герои 2–3 класса'
        self.readiness.color=(.43,.89,.63,1) if ready else (1,.74,.42,1)

    def enter(self,*_):
        from premium_access import allowed
        if not allowed('mirror'):
            from premium_options_ui import show_locked_content
            show_locked_content(on_change=self.refresh_readiness)
            return
        if _busy(self.conn):return
        try:
            worlds.enter(self.conn,self.faction,self.city_popup.city_name)
        except ValueError as exc:
            self.status.text=str(exc);self.refresh_readiness();self.fit();return
        self.dismiss();self.city_popup.dismiss()
        _refresh_main(self.conn,self.faction)
        OtherworldMap(self.conn,self.faction).open()

    def _closed(self,*_):
        super()._closed()
        if hasattr(self,'_entry_fit'):
            self._entry_fit.cancel()
