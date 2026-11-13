"""Compact, scrollable confirmation for diplomatic resource gifts."""
from kivy.core.window import Window
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from otherworld_ui import WorldPopup,_button
from mirror_readable_ui import ReadableText
from responsive_ui import ActionDock
from strategy_ui import surface,GOLD,MUTED
from utils.resource_text import resource_amount,PREPOSITIONAL
from utils.helpers import format_number,parse_formatted_number

GREEN=(.43,.88,.60,1)
CYAN=(.40,.81,1,1)
RED=(1,.46,.40,1)


class DiplomaticGiftPopup(WorldPopup):
    def __init__(self,faction,resource,cost,balance,relation,bonus,quote=None,**kwargs):
        self.target_faction=faction
        self.can_afford=balance>=cost
        super().__init__('ДИПЛОМАТИЧЕСКИЙ ДАР',accent=GOLD,**kwargs)
        self.scroll=ScrollView(do_scroll_x=False,bar_width=dp(3))
        self.body=BoxLayout(orientation='vertical',spacing=dp(10),size_hint_y=None)
        self.body.bind(minimum_height=self.body.setter('height'))
        self.scroll.add_widget(self.body);self.root.add_widget(self.scroll)
        self.faction_label=ReadableText(faction,size=22,bold=True,color=GOLD)
        self.body.add_widget(self.faction_label)
        self.need_label=ReadableText('Фракция нуждается в '+PREPOSITIONAL[resource]+'.',color=MUTED)
        self.body.add_widget(self.need_label)
        relation_card=surface(BoxLayout(orientation='vertical',padding=dp(8),spacing=dp(2),size_hint_y=None),(.08,.16,.16,1),GREEN)
        relation_card.bind(minimum_height=relation_card.setter('height'))
        relation_card.add_widget(ReadableText('ОТНОШЕНИЯ ПОСЛЕ ПЕРЕДАЧИ',size=13,color=MUTED))
        self.relation_label=ReadableText(f'{relation}%  →  {min(100,relation+bonus)}%',size=27,bold=True,color=GREEN)
        relation_card.add_widget(self.relation_label)
        self.body.add_widget(relation_card)
        self.cards=GridLayout(cols=2,spacing=dp(8),size_hint_y=None)
        self.cards.bind(minimum_height=self.cards.setter('height'))
        def tile(title,value,color,detail=''):
            box=surface(BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(5),size_hint_y=None),(.08,.10,.15,1),color)
            box.bind(minimum_height=box.setter('height'))
            box.add_widget(ReadableText(title,size=13,color=MUTED))
            label=ReadableText(value,size=19,bold=True,color=color);box.add_widget(label)
            if detail:box.add_widget(ReadableText(detail,size=13,color=MUTED))
            self.cards.add_widget(box)
            return label
        resource_color=CYAN if resource=='Кристаллы' else GOLD
        self.cost_label=tile('ПЕРЕДАЁТЕ',resource_amount(cost,resource),resource_color,
                             'Точно: '+resource_amount(cost,resource,compact=False) if parse_formatted_number(format_number(cost))!=cost else '')
        self.balance_label=tile('У ВАС',resource_amount(balance,resource),GREEN if self.can_afford else RED)
        self.body.add_widget(self.cards)
        self.remaining_label=ReadableText(('После передачи: '+resource_amount(balance-cost,resource)) if self.can_afford else
                                        'Не хватает: '+resource_amount(cost-balance,resource),color=MUTED if self.can_afford else RED)
        self.body.add_widget(self.remaining_label)
        self.quote=quote
        row=BoxLayout(spacing=dp(8))
        self.confirm_button=_button('Передать дар' if self.can_afford else 'Недостаточно ресурсов',lambda *_:None,accent=GREEN,disabled=not self.can_afford)
        self.cancel_button=_button('Отмена',self.dismiss,accent=GOLD)
        row.add_widget(self.confirm_button);row.add_widget(self.cancel_button)
        self.dock=ActionDock([row]);self.root.add_widget(self.dock)
        self.layout_content()

    def fit(self,*_):
        self.size=(min(dp(620),Window.width-dp(16)),min(dp(490),Window.height-dp(16)))
        from window_theme import center_after_resize
        center_after_resize(self)
        if hasattr(self,'_layout_event'):self._layout_event()

    def layout_content(self):
        if not hasattr(self,'cards'):return
        short=Window.height<dp(440)
        self.root.padding=dp(8);self.root.spacing=dp(6);self.body.spacing=dp(6)
        self.heading.text='ДАР: '+self.target_faction.upper() if short else 'ДИПЛОМАТИЧЕСКИЙ ДАР'
        self.faction_label.text='' if short else self.target_faction
        self.header.height=dp(44);self.heading.font_size=sp(16)
        self.cards.cols=2 if self.root.width>=dp(420) else 1
        self.dock.refresh()
