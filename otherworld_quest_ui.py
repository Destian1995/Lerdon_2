"""A compact journal that exposes the actual, location-gated quest actions."""
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from otherworld_ui import WorldPopup,_button,_busy,_refresh_main,_screen
from otherworld_themes import theme
from strategy_ui import surface,text_label,SURFACE,GOLD,MUTED,TEXT
from city_war import current_turn
import otherworlds as worlds
import otherworld_quests as quests


class QuestJournal(WorldPopup):
    def __init__(self,owner,**kwargs):
        self.owner,self.conn,self.faction=owner,owner.conn,owner.faction
        super().__init__('ЗАДАНИЯ  /  '+theme(self.faction)['name'],accent=owner.accent,**kwargs)
        self.feedback=text_label('',15,GOLD,size_hint_y=None,height=dp(48))
        self.root.add_widget(self.feedback)
        scroll=ScrollView(do_scroll_x=False)
        self.cards=BoxLayout(orientation='vertical',size_hint_y=None,spacing=dp(10))
        self.cards.bind(minimum_height=self.cards.setter('height'))
        scroll.add_widget(self.cards);self.root.add_widget(scroll)
        self.root.add_widget(_button('Вернуться на карту',self.dismiss,size_hint_y=None,height=dp(46),accent=self.accent))
        self.refresh()

    def card(self,title,copy,buttons=()):
        card=surface(BoxLayout(orientation='vertical',size_hint_y=None,padding=dp(12),spacing=dp(8)),SURFACE,self.accent)
        card.bind(minimum_height=card.setter('height'))
        card.add_widget(text_label(title,21,self.accent,bold=True,size_hint_y=None,height=dp(34)))
        label=text_label(copy,16,TEXT,size_hint_y=None,height=dp(108))
        label.unbind(size=label._strategy_text_sizer)
        label.bind(width=lambda w,v:setattr(w,'text_size',(v,None)),
                   texture_size=lambda w,v:setattr(w,'height',v[1]+dp(6)))
        label.text_size=(label.width,None)
        card.add_widget(label)
        for caption,callback,enabled in buttons:
            button=_button(caption,callback,size_hint_y=None,height=dp(44),accent=self.accent)
            button.disabled=not enabled
            card.add_widget(button)
        self.cards.add_widget(card)

    def refresh(self):
        self.cards.clear_widgets()
        run=quests.state(self.conn,self.faction)
        p=worlds.party(self.conn,self.faction)
        here=p['city_id'] if p else 0
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
            clue=''
            if stage>=1:clue='Улика свидетеля: '+detective['tokens'][run['culprit']]+'.\n'
            if stage>=2:clue+=detective['ledger']+': '+ '; '.join(n+' — '+t for n,t in zip(detective['suspects'],detective['tokens']))+'.\n'
            places=detective['cities']
            tasks=(f'Опросите свидетеля: {names[places[0]-1]}.',f'Изучите записи: {names[places[1]-1]}.',f'Предъявите обвинение: {names[places[2]-1]}.',detective['solved'])
            buttons=[]
            if stage==0:buttons=[('Опросить свидетеля · 1 действие',lambda *_:self.step('witness'),here==places[0])]
            if stage==1:buttons=[('Изучить записи · 1 действие',lambda *_:self.step('ledger'),here==places[1])]
            if stage==2:
                buttons=[('Обвинить: '+name+' · 1 действие',lambda *_,n=name:self.step('accuse',n),here==places[2]) for name in detective['suspects']]
            self.card(detective['title']+'  ·  '+str(stage)+'/3',detective['premise']+'\n'+clue+tasks[stage]+'\nНаграда: Венец истины · 25 ходов.',buttons)
            stage=run['war'];side=run['side']
            supply_city=war['supplies'][0 if side==war['sides'][0] else 1]
            supply=names[supply_city-1]
            tasks=(f'Посетите посольство: {names[war["embassy"]-1]}. Выберите сторону.',
                   f'Ваш союзник: {side}. Припасы: {war["amount"]} · {war["resource"]}. Место: {supply}.',
                   f'Сразитесь с противником: {names[war["target"]-1]}. Бой доступен в окне города.',
                   f'{side} победил благодаря вашей помощи.')
            buttons=[]
            if stage==0:buttons=[('Поддержать: '+name+' · 1 действие',lambda *_,n=name:self.step('side',n),here==war['embassy']) for name in war['sides']]
            if stage==1:buttons=[('Доставить припасы · 1 действие',lambda *_:self.step('supply'),here==supply_city)]
            self.card(war['title']+'  ·  '+str(stage)+'/3',war['premise']+'\n'+tasks[stage]+'\nНаграда: Клинок союзного двора · 25 ходов.',buttons)
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
        self.perform(lambda:quests.action(self.conn,self.faction,kind,choice))

    def perform(self,callback):
        if _busy(self.conn):return
        try:
            result=callback()
            self.feedback.text=result if isinstance(result,str) else 'Награды получены. Они будут действовать 25 ходов.'
        except ValueError as exc:
            self.feedback.text=str(exc);return
        screen=_screen(self.conn)
        if screen:screen.season_manager.apply_artifact_bonuses(self.conn)
        _refresh_main(self.conn,self.faction)
        self.refresh();self.owner.map.draw();self.owner.refresh()
