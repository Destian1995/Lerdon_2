"""A compact journal that exposes the actual, location-gated quest actions."""
from kivy.metrics import dp
from kivy.uix.gridlayout import GridLayout
from otherworld_ui import WorldPopup,_button,_busy,_refresh_main,_screen
from otherworld_themes import theme
from strategy_ui import GOLD
from city_war import current_turn
import otherworlds as worlds
import otherworld_quests as quests


class QuestJournal(WorldPopup):
    def __init__(self,owner,**kwargs):
        self.owner,self.conn,self.faction=owner,owner.conn,owner.faction
        self._feedback_city=None
        super().__init__('ЗАДАНИЯ  /  '+theme(self.faction)['name'],accent=owner.accent,**kwargs)
        from mirror_layout import FitLabel
        self.feedback=FitLabel(text='',maximum=15,color=GOLD,size_hint_y=None,height=0)
        self.root.add_widget(self.feedback)
        self.cards=GridLayout(cols=2,spacing=dp(8))
        self.root.add_widget(self.cards)
        self.close_button=_button('Вернуться на карту',self.dismiss,size_hint_y=None,height=dp(46),accent=self.accent)
        self.root.add_widget(self.close_button)
        self.cards.bind(size=self._layout_event)
        self.feedback.bind(text=self._layout_event)
        self.refresh()

    def layout_content(self):
        if not hasattr(self,'close_button'):return
        h,w=self.root.height,self.root.width
        self.root.padding=min(dp(12),h*.018);self.root.spacing=min(dp(8),h*.014)
        self.header.height=min(dp(46),h*.095)
        self.header.children[0].width=self.header.height
        self.heading.font_size=min(dp(22),self.header.height*.6,w*.036)
        self.feedback.height=min(dp(42),h*.09) if self.feedback.text else 0
        self.close_button.height=min(dp(46),h*.10)
        self.close_button.font_size=min(dp(15),self.close_button.height*.4)
        self.cards.cols=1 if w<h*.9 else 2

    def card(self,title,copy,buttons=()):
        from mirror_layout import QuestCard
        self.cards.add_widget(QuestCard(title,copy,buttons,self.accent))
        self._layout_event()

    def refresh(self):
        self.cards.clear_widgets()
        run=quests.state(self.conn,self.faction)
        p=worlds.party(self.conn,self.faction)
        here=p['city_id'] if p else 0
        if self._feedback_city!=here:self.feedback.text=''
        names=theme(self.faction)['cities']
        now=current_turn(self.conn)
        if not run or run['finished_turn'] is not None:
            ready=not run or run['repeat_turn']<=now
            cooldown=max(0,run['repeat_turn']-now) if run else 0
            copy=('Каждый поход — новое расследование и новый конфликт сказочных сил. Сюжеты, участники, улики и маршруты меняются.\n'
                  'За каждое — мощный предмет на 25 ходов. За оба — Сердце Зазеркалья и лимиты ресурсов +35% на 25 ходов.')
            if run:copy+=f'\nЦепочка завершена. Повтор через {cooldown} х.' if cooldown else '\nМожно начать новую цепочку.'
            self.card('Приключения Зазеркалья',copy,[('Принять задания у Врат',lambda *_:self.perform(lambda:quests.begin(self.conn,self.faction)),ready and here==1 and not quests.pending(self.conn,self.faction))])
        else:
            scenario=quests.details(run);detective=scenario['detective'];war=scenario['war']
            stage=run['detective']
            clue=quests.local_detective_clue(run,here)
            if clue:clue+='\n'
            places=detective['cities']
            tasks=(f'Опросите свидетеля: {names[places[0]-1]}.',f'Изучите записи: {names[places[1]-1]}.',f'Предъявите обвинение: {names[places[2]-1]}.',detective['solved'])
            buttons=[]
            if stage==0:buttons=[('Опросить свидетеля',lambda *_:self.step('witness'),here==places[0])]
            if stage==1:buttons=[('Изучить записи',lambda *_:self.step('ledger'),here==places[1])]
            if stage==2:
                buttons=[('Обвинить: '+name,lambda *_,n=name:self.step('accuse',n),here==places[2]) for name in detective['suspects']]
                if here==places[2]:tasks=(*tasks[:2],'Кого вы обвиняете? Вспомните подсказки из других городов.',tasks[3])
            self.card(detective['title']+'  ·  '+str(stage)+'/3',(detective['premise']+'\n' if stage==0 else '')+clue+tasks[stage]+'\nНаграда: Венец истины · 25 ходов.',buttons)
            stage=run['war'];side=run['side']
            supply_city=war['supplies'][0 if side==war['sides'][0] else 1]
            supply=names[supply_city-1]
            tasks=(f'Посольство: {names[war["embassy"]-1]}.',
                   f'Ваш союзник: {side}. Припасы: {war["amount"]} · {war["resource"]}. Место: {supply}.',
                   f'Сразитесь с противником: {names[war["target"]-1]}. Бой доступен в окне города.',
                   f'{side} победил благодаря вашей помощи.')
            buttons=[]
            if stage==0:buttons=[('Поддержать: '+name,lambda *_,n=name:self.step('side',n),here==war['embassy']) for name in war['sides']]
            if stage==1:buttons=[('Доставить припасы',lambda *_:self.step('supply'),here==supply_city)]
            from mirror_allegiance_ui import AllegianceCard
            from utils.helpers import format_number
            defense=format_number(worlds.QUEST_GARRISON_DEFENSE).replace('.0 ',' ')
            self.cards.add_widget(AllegianceCard(war['title']+'  ·  '+str(stage)+'/3',
                (war['premise']+'\n\n' if stage==0 else '')+tasks[stage],buttons,self.accent,
                self.faction,stage,tasks[stage]+'\nЗащита: '+defense+' · Награда: артефакт на 25 ходов.'))
            self._layout_event()
        pending=quests.pending(self.conn,self.faction)
        if pending:
            from portal_items import champions
            eligible=champions(self.conn,self.faction,p['camp']) if p else []
            summary='Неполученных предметов: '+str(len(pending))+'. Срок каждого начнётся при получении и составит 25 ходов.'
            summary+='\nПолучатель: '+eligible[0]+' [3 класс].' if eligible else '\nПриведите героя 3 класса в отряд.'
            self.card('Ваши награды',summary,[('Забрать награды',lambda *_:self.perform(lambda:quests.claim(self.conn,self.faction)),bool(eligible))])
        left=quests.cap_turns(self.conn,self.faction)
        if left:self.card('Благословение Зазеркалья',f'Лимиты крон, кристаллов, рабочих и населения увеличены на 35%.\nОсталось {left} ходов. Бонус не складывается сам с собой.')

    def step(self,kind,choice=None):
        def action():
            result=quests.action(self.conn,self.faction,kind,choice)
            return 'Подсказка получена. Запомните её перед уходом.' if kind in ('witness','ledger') else result
        self.perform(action)

    def perform(self,callback):
        if _busy(self.conn):return
        p=worlds.party(self.conn,self.faction)
        self._feedback_city=p['city_id'] if p else 0
        try:
            result=callback()
            self.feedback.text=result if isinstance(result,str) else 'Награды получены. Они будут действовать 25 ходов.'
        except ValueError as exc:
            self.feedback.text=str(exc);return
        screen=_screen(self.conn)
        if screen:screen.season_manager.apply_artifact_bonuses(self.conn)
        _refresh_main(self.conn,self.faction)
        self.refresh();self.owner.map.draw();self.owner.refresh()
