"""A compact journal that exposes the actual, location-gated quest actions."""
from kivy.metrics import dp,sp
from otherworld_ui import WorldPopup,_button,_busy,_refresh_main,_screen
from otherworld_themes import theme
from strategy_ui import GOLD
from city_war import current_turn
import otherworlds as worlds
import otherworld_quests as quests


class QuestJournal(WorldPopup):
    def __init__(self,owner,tavern_city=None,**kwargs):
        self.owner,self.conn,self.faction=owner,owner.conn,owner.faction
        self.tavern_city=tavern_city
        self._feedback_city=None
        super().__init__('ЗАДАНИЯ  /  '+theme(self.faction)['name'],accent=owner.accent,**kwargs)
        from mirror_readable_ui import ReadableText
        self.feedback=ReadableText('',size=14,color=GOLD)
        self.root.add_widget(self.feedback)
        self.close_button=_button('Вернуться на карту',self.dismiss,size_hint_y=None,height=dp(46),accent=self.accent)
        from mirror_quest_layout import QuestSplitView
        self.cards=QuestSplitView(self.close_button,self.accent)
        self.root.add_widget(self.cards)
        self.cards.bind(size=self._layout_event)
        self.feedback.bind(text=self._layout_event)
        self.refresh()

    def layout_content(self):
        if not hasattr(self,'close_button'):return
        self.root.padding=dp(6);self.root.spacing=dp(6)
        self.header.height=dp(38)
        self.header.children[0].width=dp(40)
        self.heading.font_size=sp(19)
        self.feedback.height=max(dp(22),self.feedback.texture_size[1]+dp(2)) if self.feedback.text else 0
        self.close_button.height=dp(44);self.close_button.font_size=sp(15)

    def card(self,title,copy,buttons=(),details=''):
        from mirror_quest_layout import QuestDetail
        self.cards.add_card(QuestDetail(title,copy,buttons,self.accent,details=details))
        self._layout_event()

    def refresh(self):
        selected=self.cards.page_index
        self.cards.clear_cards()
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
            copy+='\nРиск: неверное место поиска, порядок улик или обвинение обнуляют все ваши кроны.'
            if run:copy+=f'\nЦепочка завершена. Повтор через {cooldown} х.' if cooldown else '\nМожно начать новую цепочку.'
            self.card('Приключения Зазеркалья',copy,[('Принять задания' if self.tavern_city else 'Принять задания у Врат',lambda *_:self.perform(lambda:quests.begin(self.conn,self.faction,tavern_city=self.tavern_city)),ready and (here==1 or here==self.tavern_city) and not quests.pending(self.conn,self.faction))])
        else:
            scenario=quests.details(run);detective=scenario['detective'];war=scenario['war']
            stage=run['detective']
            clue=quests.local_detective_clue(run,here)
            if clue:clue+='\n'
            places=detective['cities']
            tasks=(f'Опросите свидетеля: {names[places[0]-1]}.',f'Изучите записи: {names[places[1]-1]}.',f'Предъявите обвинение: {names[places[2]-1]}.',detective['solved'])
            buttons=[]
            if stage==0:buttons=[('Опросить свидетеля',lambda *_:self.step('witness'),here==places[0])]
            if stage==1:
                sites=detective.get('search_sites')
                buttons=[('Искать: '+site,lambda *_,s=site:self.step('ledger',s),here==places[1]) for site in sites] if sites else [('Изучить записи',lambda *_:self.step('ledger'),here==places[1])]
            if stage==2:
                buttons=[('Обвинить: '+name,lambda *_,n=name:self.step('accuse',n),here==places[2]) for name in detective['suspects']]
                if here==places[2]:tasks=(*tasks[:2],'Кого вы обвиняете? Вспомните подсказки из других городов.',tasks[3])
                if detective.get('search_sites'):
                    collected,arranged=quests.evidence(self.conn,self.faction)
                    board='\n'.join(f'{i+1}. {item}' for i,item in enumerate(arranged)) or 'Доска пуста'
                    notes='\n'.join(quests.evidence_notes(run))
                    tasks=(*tasks[:2],'Соберите цепочку: показание → находка → запись. Затем выберите виновного.\n'+notes+'\nДоска улик:\n'+board+'\nРиск: ошибка при обвинении обнулит все кроны.',tasks[3])
                    if len(arranged)<3:
                        buttons=[('Разместить: '+item,lambda *_,c=item:self.step('arrange',c),here==places[2]) for item in reversed(collected) if item not in arranged]
                    else:
                        buttons.append(('Переставить улики',lambda *_:self.step('reset_board'),here==places[2]))
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
            from utils.helpers import format_number
            defense=format_number(worlds.QUEST_GARRISON_DEFENSE).replace('.0 ',' ')
            self.card(war['title']+'  ·  '+str(stage)+'/3',
                (war['premise']+'\n\n' if stage==0 else '')+tasks[stage],buttons,
                details='ЗАЩ '+defense+' · Артефакт 25 х.')
            self._layout_event()
        self.monster_card(p,here,names)
        from morgana_covenant import offer
        morgana=offer(self.conn,self.faction)
        if morgana and morgana['status']=='offered':
            from morgana_covenant_ui import show_offer
            self.card('Предложение Морганы','Моргана предлагает вам возглавить легион Нежити. Решение изменит города и дипломатию до конца кампании.',
                      [('Выслушать Моргану',lambda *_:show_offer(self.conn,self.faction,force=True),True)])
        elif morgana and morgana['status']=='accepted':
            self.card('Служение Моргане','Ваши города — некрополи. Лимиты армии и ресурсов +45% навсегда. С живыми фракциями — вечная война. Исходный срок сделки за душу продолжает идти.')
        pending=quests.pending(self.conn,self.faction)
        if pending:
            from portal_items import champions
            eligible=champions(self.conn,self.faction,p['camp']) if p else []
            summary='Неполученных предметов: '+str(len(pending))+'. Срок каждого начнётся при получении и составит 25 ходов.'
            summary+='\nПолучатель: '+eligible[0]+' [3 класс].' if eligible else '\nПриведите героя 3 класса в отряд.'
            self.card('Ваши награды',summary,[('Забрать награды',lambda *_:self.perform(lambda:quests.claim(self.conn,self.faction)),bool(eligible))])
        left=quests.cap_turns(self.conn,self.faction)
        if left:self.card('Благословение Зазеркалья',f'Лимиты крон, кристаллов, рабочих и населения увеличены на 35%.\nОсталось {left} ходов. Бонус не складывается сам с собой.')
        self.cards.select(selected)

    def monster_card(self,party,here,names):
        import json
        import mirror_monster_quest as hunt
        case=hunt.state(self.conn,self.faction)
        deal=hunt.pact(self.conn,self.faction)
        if deal:
            left=max(0,deal['deadline']-current_turn(self.conn))
            form=hunt.companion_form(self.conn,self.faction)
            alive=bool(form and self.conn.execute('SELECT 1 FROM garrisons WHERE unit_name=? AND unit_count>0',(form['unit_name'],)).fetchone())
            self.card('Сделка за душу · '+str(left)+' х.',
                      'Монстр на вашей стороне. Победите в кампании не позднее хода '+str(deal['deadline'])+
                      '.\nОсталось ходов: '+str(left)+'. Срок не сбрасывается при возвращении домой или потере монстра. '
                      'Если не победите за 30 ходов после сделки — поражение без нового звания.\n'
                      'Облик дворянина: атака +50%, защита −50%. Облик монстра: атака −50%, защита +50%.',
                      [('Облик дворянина',lambda *_:self.change_form('noble'),alive),
                       ('Облик монстра',lambda *_:self.change_form('monster'),alive),
                       ('Мужской персонаж',lambda *_:self.change_gender('lord'),alive),
                       ('Женский персонаж',lambda *_:self.change_gender('lady'),alive)])
        if not case or case['stage']==3:
            left=max(0,case['finished_turn']+hunt.COOLDOWN-current_turn(self.conn)) if case else 0
            seasonal=' · '.join(hunt.SEASONS[i]+' ×'+str(hunt.stat_percent(self.faction,i)/100).replace('.',',') for i in range(4))
            copy=('Необязательное дело о гибели и исчезновениях жителей. Соберите две улики и вычислите, кто из трёх дворян скрывает чудовище. '
                  'База монстра: 260 млн атаки и 310 млн защиты. Сезонные коэффициенты вашей фракции: '+seasonal+'. '
                  'Сезон фиксируется при принятии. Можно сразиться или договориться ценой души.\n'
                  'Награда: один уникальный спутник в отряд победителя. База: 100 млн атаки и 100 млн защиты; '
                  'каждая характеристика получает отдельную надбавку от 14,2% до 27,1%. '
                  'Спутник остаётся с отрядом при возвращении домой.')
            if case:copy+='\nПредыдущее дело раскрыто героем '+case['hero']+'. Новое дело через '+str(left)+' х.'
            available=bool(party and hunt.heroes(self.conn,party['camp'],self.faction) and not left)
            self.card('Исчезнувшие жители · необязательно',copy,
                      [('Принять расследование',lambda *_:self.perform(lambda:hunt.begin(self.conn,self.faction)),available)])
            return
        story=json.loads(case['scenario']);stage=case['stage'];enemy=hunt.monster(case)
        from utils.helpers import format_number
        copy=story['premise']+'\nГород: '+names[case['city_id']-1]+'. Сезон дела: '+hunt.SEASONS[case['season']]+'.'
        if stage>=1:copy+='\n'+story['witness']
        if story.get('nobles'):
            copy+='\nДворянский реестр:\n'+'\n'.join(n['name']+' — герб: '+n['crest']+'; '+n['mark']+'.' for n in story['nobles'])
        if stage>=2:copy+='\n'+story['clue']
        exposed=hunt.revealed(case)
        identified=hunt.identified(case)
        if stage>=2 and identified and not exposed:
            copy+='\n'+hunt.noble_name(case)+' сохраняет человеческий облик и предлагает помощь в обмен на вашу душу. '
            copy+='После сделки можно менять облик: дворянин усиливает атаку на 50%, ослабляя защиту на 50%; монстр — наоборот.'
        if stage>=2 and exposed:
            if story.get('nobles'):copy+='\n'+story['nobles'][story['culprit']]['name']+' раскрывает свою истинную сущность.'
            copy+='\nМонстр: '+story['monster']+'. Атака: '+format_number(enemy['attack'])+' · Защита: '+format_number(enemy['defense'])+'.'
        buttons=[]
        if stage<2:
            buttons=[('Опросить свидетеля' if stage==0 else 'Проверить следы',
                      lambda *_:self.perform(lambda:hunt.investigate(self.conn,self.faction)),here==case['city_id'])]
        elif not identified:
            copy+='\nКто из дворян совпадает с обеими уликами?'
            buttons=[('Обвинить: '+n['name'],lambda *_,n=n['name']:self.perform(lambda:hunt.accuse(self.conn,self.faction,n)),
                      here==case['city_id'] and n['name'] not in story.get('cleared',[])) for n in story['nobles']]
        elif party:
            buttons=[]
            if exposed:
                buttons=[('В бой · '+hero,lambda *_,h=hero:self.hunt_battle(h),here==case['city_id'])
                         for hero in hunt.heroes(self.conn,party['camp'],self.faction)]
            elif not exposed:
                if not deal:
                    buttons += [('Договориться · '+hero,lambda *_,h=hero:self.offer_soul(h),here==case['city_id'])
                                for hero in hunt.heroes(self.conn,party['camp'],self.faction)]
                buttons.append(('Отказать и увидеть сущность',lambda *_:self.perform(lambda:hunt.reject_soul(self.conn,self.faction)),here==case['city_id']))
            confirm=getattr(self,'_soul_offer',None)
            if not exposed and confirm and confirm==(case['id'],here):
                hero=self._soul_hero
                copy+='\nРиск: цена сделки — ваша душа. Союзник присоединится без боя в облике дворянина: атака '+format_number(enemy['attack']*3//2)+', защита '+format_number(enemy['defense']//2)+'. '
                copy+='Вы обязаны победить в кампании за 30 ходов, иначе проиграете без присвоения звания. Сделка необратима.'
                buttons=[('Продать душу · '+hero,lambda *_:self.accept_soul(hero),True),
                         ('Отказаться от сделки',lambda *_:self.offer_soul(None),True)]
        self.card(story['title']+' · '+str(stage)+'/3',copy,buttons,
                  details='Награда: спутник · АТК +'+str(case['attack_bonus']/10)+'% · ЗАЩ +'+str(case['defense_bonus']/10)+'%')
        if stage==2 and identified:
            from kivy.uix.image import Image
            card=self.cards.pages[-1]
            card.content.add_widget(Image(source=enemy['unit_image'] if exposed else hunt.noble_image(case),fit_mode='contain',
                                          size_hint_y=None,height=dp(130)),index=1 if buttons else 0)

    def change_form(self,form):
        import mirror_monster_quest as hunt
        def change():
            hunt.set_form(self.conn,self.faction,form)
            return 'Облик спутника изменён. Срок сделки остался прежним.'
        self.perform(change)

    def change_gender(self,gender):
        import mirror_monster_quest as hunt
        def change():
            hunt.choose_gender(self.conn,self.faction,gender)
            return 'Облик персонажа выбран. Характеристики и срок сделки не изменились.'
        self.perform(change)

    def offer_soul(self,hero):
        import mirror_monster_quest as hunt
        case=hunt.state(self.conn,self.faction);party=worlds.party(self.conn,self.faction)
        self._soul_offer=(case['id'],party['city_id']) if hero and case and party else None
        self._soul_hero=hero
        self.refresh()

    def accept_soul(self,hero):
        import mirror_monster_quest as hunt
        def accept():
            hunt.sell_soul(self.conn,self.faction,hero)
            self._soul_offer=None
            return 'Монстр присоединился к отряду. Победите за 30 ходов. При неудаче — поражение без звания.'
        self.perform(accept)
        from morgana_covenant_ui import show_offer
        show_offer(self.conn,self.faction)

    def hunt_battle(self,hero):
        import mirror_monster_quest as hunt
        result=[]
        def battle():
            outcome=hunt.fight(self.conn,self.faction,hero);result.append(outcome)
            return ('Расследование раскрыто! Спутник присоединился к отряду героя '+hero+'.'
                    if outcome['won'] else 'Монстр не побеждён. Соберите силы и возвращайтесь в логово.')
        self.perform(battle)
        if not result:return
        outcome=result[0]
        from battle_ui import BattleViewer
        class HuntBattle(BattleViewer):
            def reveal_result(view):
                super().reveal_result()
                view.result_detail.text=('Победа · уникальный спутник в отряде героя '+hero
                                        if outcome['won'] else 'Отступление · расследование продолжается')
        HuntBattle(outcome['rounds'],self.faction,outcome['guards'][0]['unit_name'],
                   'attacker' if outcome['won'] else 'defender',self.faction,'Экспедиция',outcome['city'],
                   attacker_image=outcome.get('attacker_image'),defender_image=outcome['guards'][0]['unit_image']).open()

    def step(self,kind,choice=None):
        def action():
            result=quests.action(self.conn,self.faction,kind,choice)
            return 'Подсказка получена. Запомните её перед уходом.' if kind in ('witness','ledger') and not result.startswith('Расследование провалено') else result
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
        if screen:
            screen.season_manager.apply_artifact_bonuses(self.conn)
            if hasattr(screen,'turn_label'):
                from mirror_monster_quest import deadline_caption
                caption=deadline_caption(self.conn,self.faction)
                screen.turn_label.text=f'Текущий ход: {screen.turn_counter}'+('\n'+caption if caption else '')
        _refresh_main(self.conn,self.faction)
        self.refresh();self.owner.map.draw();self.owner.refresh()
