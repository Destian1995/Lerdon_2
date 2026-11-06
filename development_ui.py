"""Development is one copy of every building, delegated by a loyal council."""
from kivy.metrics import dp,sp
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout
from frontend_ui import NaturalList
from mirror_readable_ui import ReadableText
from otherworld_ui import WorldPopup,_button
from strategy_ui import GOLD,MUTED
from city_construction import CATALOG,building_counts,construction_allowed,building_name
from city_development import average_loyalty
from utils.helpers import format_number


class DevelopmentPopup(WorldPopup):
    def __init__(self,faction):
        self.faction=faction
        super().__init__('Развитие городов',accent=GOLD)
        scroll=ScrollView(do_scroll_x=False,bar_width=dp(3));self.root.add_widget(scroll)
        self.page=NaturalList(spacing=dp(6),padding=dp(4));scroll.add_widget(self.page)
        self.loyalty_label=ReadableText('',size=15,bold=True);self.page.add_widget(self.loyalty_label)
        self.rule_label=ReadableText(f'{len(CATALOG)} уникальных типов. Ручное строительство — на панораме.',size=14)
        self.page.add_widget(self.rule_label)
        self.summary=ReadableText('',size=15,color=GOLD);self.page.add_widget(self.summary)
        self.priority_hint=ReadableText('',size=14,color=(1,.72,.34,1),bold=True)
        self.page.add_widget(self.priority_hint)
        self.city_rows=NaturalList(spacing=dp(8));self.page.add_widget(self.city_rows)
        actions=BoxLayout(size_hint_y=None,height=dp(44),spacing=dp(6))
        actions.add_widget(_button('Обновить',self.refresh));actions.add_widget(_button('Закрыть',self.dismiss))
        self.root.add_widget(actions);self.actions=actions
        self.refresh();self.fit()

    def layout_content(self):
        if hasattr(self,'actions'):
            self.actions.height=dp(44);self.header.height=dp(40)
            self.header.children[0].width=dp(40);self.heading.font_size=sp(18)
            self.root.padding=dp(6);self.root.spacing=dp(4)

    def refresh(self,*_):
        model=self.faction;conn=model.conn;name=model.faction
        loyalty=average_loyalty(conn,name);active=loyalty>80
        model.auto_build_enabled=active
        self.loyalty_label.text=f'Совет: {loyalty:.1f}% · '+('Автостройка работает' if active else 'Авто: пауза (нужно >80%)')
        self.loyalty_label.color=(.4,.9,.6,1) if active else GOLD
        self.city_rows.clear_widgets();done=total=cost=0;needs_economy=False
        for city, in conn.execute('SELECT name FROM cities WHERE faction=? ORDER BY name',(name,)).fetchall():
            if not construction_allowed(conn,city,name):continue
            counts=building_counts(conn,city,name);missing=[b for b in CATALOG if not counts.get(b,0)]
            count=len(CATALOG)-len(missing);done+=count;total+=len(CATALOG)
            cost+=sum(CATALOG[b]['cost'] for b in missing)
            essentials=[b for b in ('Больница','Фабрика') if b in missing]
            needs_economy=needs_economy or bool(essentials)
            text=f'{city} · {count} из {len(CATALOG)}'
            if essentials:
                text+='\nОбязательно постройте '+ ' и '.join({'Больница':'больницу','Фабрика':'фабрику'}[b] for b in essentials)+'.'
            text+='\nОсталось: '+', '.join(building_name(name,b) for b in missing) if missing else '\nВсе здания построены'
            color=(1,.72,.34,1) if essentials else MUTED if missing else (.4,.9,.6,1)
            self.city_rows.add_widget(ReadableText(text,size=15,color=color))
        self.priority_hint.text=('Больница и фабрика обязательны для развития экономики. '
                                 'В отмеченных городах постройте недостающее: город → «Построить».'
                                 if needs_economy else '')
        self.summary.text=f'Построено {done} из {total} · На завершение: {format_number(cost)} крон'


def open_development(faction,show_message=None):
    popup=DevelopmentPopup(faction);popup.open();return popup
