"""A two-choice audience after a noble is identified on the investigation board."""
from kivy.core.window import Window
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from otherworld_ui import WorldPopup,_button,_busy
from mirror_readable_ui import ReadableText
from responsive_ui import ActionDock
from strategy_ui import GOLD,MUTED
from utils.helpers import format_number
import otherworlds as worlds
import mirror_monster_quest as hunt


class NobleEncounter(WorldPopup):
    def __init__(self,journal,**kwargs):
        self.journal,self.conn,self.faction=journal,journal.conn,journal.faction
        self.working=False
        super().__init__('ПРЕДЛОЖЕНИЕ ДВОРЯНИНА',accent=GOLD,**kwargs)
        self.content_row=BoxLayout(spacing=dp(12));self.root.add_widget(self.content_row)
        self.art=Image(fit_mode='contain');self.content_row.add_widget(self.art)
        self.scroll=ScrollView(do_scroll_x=False,bar_width=dp(3));self.content_row.add_widget(self.scroll)
        self.copy=BoxLayout(orientation='vertical',spacing=dp(10),size_hint_y=None)
        self.copy.bind(minimum_height=self.copy.setter('height'));self.scroll.add_widget(self.copy)
        self.name=ReadableText('',size=22,bold=True,color=GOLD);self.copy.add_widget(self.name)
        self.speech=ReadableText('',size=16);self.copy.add_widget(self.speech)
        self.terms=ReadableText('',size=15,color=GOLD);self.copy.add_widget(self.terms)
        self.copy.remove_widget(self.speech);self.copy.add_widget(self.speech)
        self.stats=ReadableText('',size=14,color=MUTED);self.copy.add_widget(self.stats)
        self.hero_caption=ReadableText('Герой, к которому присоединится спутник:',size=14,color=MUTED)
        self.copy.add_widget(self.hero_caption)
        self.hero=Spinner(size_hint_y=None,height=dp(48),font_size=sp(16))
        self.copy.add_widget(self.hero)
        self.notice=ReadableText('',size=14,color=(1,.48,.40,1));self.copy.add_widget(self.notice)
        row=BoxLayout(spacing=dp(8))
        self.accept_button=_button('Принять сделку',self.accept,accent=(.42,.88,.60,1))
        self.refuse_button=_button('Отказаться',self.refuse,accent=GOLD)
        row.add_widget(self.accept_button);row.add_widget(self.refuse_button)
        self.dock=ActionDock([row]);self.root.add_widget(self.dock)
        self.refresh();self.layout_content()

    def fit(self,*_):
        self.size=(min(dp(900),Window.width-dp(16)),min(dp(630),Window.height-dp(16)))
        from window_theme import center_after_resize
        center_after_resize(self)
        if hasattr(self,'_layout_event'):self._layout_event()

    def layout_content(self):
        if not hasattr(self,'dock'):return
        portrait=self.root.width<dp(480)
        self.root.padding=dp(8);self.root.spacing=dp(6)
        self.header.height=dp(44);self.heading.font_size=sp(16)
        self.content_row.orientation='vertical' if portrait else 'horizontal'
        self.art.size_hint=(1,None) if portrait else (.43,1)
        if portrait:self.art.height=dp(160)
        self.scroll.size_hint=(1,1) if portrait else (.57,1)
        self.dock.refresh()

    def refresh(self):
        case=hunt.state(self.conn,self.faction)
        if not case or case['stage']!=2 or not hunt.identified(case):return self.dismiss(animation=False)
        party=worlds.party(self.conn,self.faction)
        heroes=hunt.heroes(self.conn,party['camp'],self.faction) if party else []
        self.here=bool(party and party['city_id']==case['city_id'])
        current=self.hero.text
        self.hero.values=heroes;self.hero.text=current if current in heroes else heroes[0] if heroes else 'Нет доступного героя'
        self.hero.disabled=len(heroes)<2
        self.exposed=hunt.revealed(case)
        enemy=hunt.monster(case)
        self.art.source=enemy['unit_image'] if self.exposed else hunt.noble_image(case)
        self.name.text=enemy['unit_name'] if self.exposed else hunt.noble_name(case)
        if self.exposed:
            self.heading.text='ИСТИННАЯ СУЩНОСТЬ'
            self.speech.text='Сделка отвергнута. Дворянин раскрывает свою истинную сущность. Вы можете сразиться сейчас или вернуться с более сильным отрядом.'
            self.terms.text='Победа в бою: постоянный спутник без ограничения ходов. Его характеристики будут на 40% ниже силы противника.'
            self.stats.text='Противник: АТК '+format_number(enemy['attack'])+' · ЗАЩ '+format_number(enemy['defense'])
            self.hero_caption.text='Герой, который вступит в бой:'
            self.accept_button.text='В бой';self.refuse_button.text='Уйти'
        else:
            self.speech.text='«Вы раскрыли мою тайну. Возьмите моё сердце — и я стану вашим спутником. Взамен обещайте победить в кампании за 20 ходов».'
            self.terms.text='Спутник без боя — в обмен на победу за 20 ходов.\nПросрочка: вся ваша армия навсегда теряет 50% боевых характеристик. Кампания продолжится.\nОтказ раскрывает сущность и закрывает сделку.'
            self.stats.text='Облик дворянина: АТК '+format_number(enemy['attack']*3//2)+' · ЗАЩ '+format_number(enemy['defense']//2)+'.\nПосле сделки можно менять пол и облик спутника.'
        self.accept_button.disabled=not self.here or not heroes or (not self.exposed and bool(hunt.pact(self.conn,self.faction)))
        self.refuse_button.disabled=not self.here and not self.exposed
        self.notice.text=('Вернитесь в город расследования, чтобы продолжить.' if not self.here else
                          'Приведите героя 2 или 3 класса.' if not heroes else
                          'Договор уже заключён. Новый договор недоступен.' if not self.exposed and hunt.pact(self.conn,self.faction) else '')

    def accept(self,*_):
        if self.working or self.accept_button.disabled or _busy(self.conn):return
        self.working=True
        if self.exposed:
            hero=self.hero.text;self.dismiss(animation=False);self.journal.hunt_battle(hero);return
        self.journal.accept_soul(self.hero.text)
        case=hunt.state(self.conn,self.faction)
        if case and case['stage']==3:self.dismiss(animation=False)
        else:
            self.working=False;self.refresh();self.notice.text=self.journal.feedback.text
        self.journal.feedback.text=''

    def refuse(self,*_):
        if self.working or self.refuse_button.disabled or _busy(self.conn):return
        if self.exposed:return self.dismiss(animation=False)
        self.journal.perform(lambda:hunt.reject_soul(self.conn,self.faction))
        feedback=self.journal.feedback.text;self.journal.feedback.text=''
        self.refresh()
        if not self.exposed:self.notice.text=feedback
