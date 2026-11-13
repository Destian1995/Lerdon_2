"""A compact journal that exposes the actual, location-gated quest actions."""
from kivy.metrics import dp,sp
from otherworld_ui import WorldPopup,_button,_busy,_refresh_main,_screen
from otherworld_themes import theme
from strategy_ui import GOLD
from city_war import current_turn
import otherworlds as worlds
import otherworld_quests as quests
from weakref import WeakSet

_open_journals=WeakSet()


def refresh_open_journals(conn,faction):
    """Called on the UI thread after an expedition transaction commits."""
    for journal in tuple(_open_journals):
        if journal.conn is conn and journal.faction==faction and journal.parent is not None:
            journal.refresh()


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
        _open_journals.add(self)

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
        selected_title=self.cards.pages[selected].title if self.cards.pages and selected<len(self.cards.pages) else None
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
            copy+='\nРиск: неверное место поиска или обвинение обнуляют все ваши кроны.'
            if run:copy+=f'\nЦепочка завершена. Повтор через {cooldown} х.' if cooldown else '\nМожно начать новую цепочку.'
            self.card('Приключения Зазеркалья',copy,[('Принять задания' if self.tavern_city else 'Принять задания у Врат',lambda *_:self.perform(lambda:quests.begin(self.conn,self.faction,tavern_city=self.tavern_city)),ready and (here==1 or here==self.tavern_city) and not quests.pending(self.conn,self.faction))])
        else:
            scenario=quests.details(run);detective=scenario['detective'];war=scenario['war']
            stage=run['detective']
            status=('Расследование начато.','Свидетель опрошен.','Улики собраны.','Расследование завершено.')[stage]
            self.card(detective['title']+'  ·  '+str(stage)+'/3',status+'\nВсе материалы и действия доступны на доске расследования.',
                      [('Доска расследования',lambda *_:self.open_board(),True)])
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
        if morgana and morgana['status'] in ('offered','deferred'):
            from morgana_covenant_ui import show_offer
            self.card('Предложение Морганы','Ваша душа отмечена знаком Зазеркалья. Моргана предлагает силу в обмен на душу. На победу — новые 15 ходов. После ответа «Подумаю» вступление стоит ещё 1,5 млн крон.',
                      [('Выслушать Моргану',lambda *_:show_offer(self.conn,self.faction,force=True),True)])
        elif morgana and morgana['status']=='accepted':
            self.card('Служение Моргане','Ваши города — некрополи. Лимиты армии и ресурсов +45% навсегда. С живыми фракциями — вечная война. На победу отведено 15 ходов с принятия предложения Морганы.')
        pending=quests.pending(self.conn,self.faction)
        new_rewards=bool(set(pending)-set(getattr(self,'_pending_rewards',())))
        self._pending_rewards=tuple(pending)
        if pending:
            from portal_items import champions,reward
            from utils.helpers import format_number
            eligible=champions(self.conn,self.faction,p['camp']) if p else []
            summary='Неполученных предметов: '+str(len(pending))+'. Срок каждого начнётся при получении и составит 25 ходов.'
            for key in pending:
                item=reward(self.conn,self.faction,key)
                summary+='\n'+item['name']+' · АТК +'+format_number(item['attack'])+' · ЗАЩ +'+format_number(item['defense'])
            summary+='\nПолучатель: '+eligible[0]+' [3 класс].' if eligible else '\nПриведите героя 3 класса в отряд.'
            self.card('Ваши награды',summary,[('Забрать награды',lambda *_:self.perform(lambda:quests.claim(self.conn,self.faction)),bool(eligible))])
        left=quests.cap_turns(self.conn,self.faction)
        if left:self.card('Благословение Зазеркалья',f'Лимиты крон, кристаллов, рабочих и населения увеличены на 35%.\nОсталось {left} ходов. Бонус не складывается сам с собой.')
        if new_rewards:selected_title='Ваши награды'
        selected=next((i for i,page in enumerate(self.cards.pages) if page.title==selected_title),selected)
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
            from heart_contract import state as heart_state,multiplier
            soul=hunt.soul_pact(self.conn,self.faction);heart=heart_state(self.conn,self.faction)
            cursed=multiplier(self.conn,self.faction)<1
            title='Сделка с Морганой' if soul else 'Сердце дворянина'
            description=('На победу осталось '+str(left)+' х. Не успеете — поражение без звания.' if soul else
                         'Проклятие сердца: вся армия навсегда теряет 50% боевых характеристик. Кампания продолжается.' if cursed else
                         'Победите за 20 ходов после договора. Осталось '+str(left)+' х. Иначе вся армия получит постоянное проклятие −50%.')
            self.card(title,description+'\nВозвращение домой и потеря спутника не отменяют договор.\n'+
                      ('Спутник: '+form['unit_name'].removeprefix(hunt.PREFIX).split(' / ')[0]+'.\n'
                       'Дворянин: атака ×1,5, защита ×0,5. Монстр: атака ×0,5, защита ×1,5.' if form else 'Договор заключён с Морганой.'),
                      [('Облик дворянина',lambda *_:self.change_form('noble'),alive),
                       ('Облик монстра',lambda *_:self.change_form('monster'),alive),
                       ('Мужской персонаж',lambda *_:self.change_gender('lord'),alive),
                       ('Женский персонаж',lambda *_:self.change_gender('lady'),alive)] if form else [])
        if case:
            import json
            title=json.loads(case['scenario'])['title']+' · '+str(case['stage'])+'/3'
            status=('Расследование начато.','Свидетель опрошен.','Улики собраны.','Расследование завершено.')[case['stage']]
        else:title,status='Исчезнувшие жители · необязательно','Расследование ещё не начато.'
        resolved=bool(case and case['stage']==2 and hunt.identified(case))
        caption=('Вернуться к монстру' if hunt.revealed(case) else 'Выслушать дворянина') if resolved else 'Доска расследования'
        self.card(title,status+('\nДворянин ждёт вашего решения.' if resolved else '\nВсе материалы и действия доступны на доске расследования.'),
                  [(caption,lambda *_:self.open_board(noble=True),True)])

    def noble_materials(self,case,party,here,names):
        import json
        import mirror_monster_quest as hunt
        deal=hunt.pact(self.conn,self.faction)
        if not case or case['stage']==3:
            left=max(0,case['finished_turn']+hunt.COOLDOWN-current_turn(self.conn)) if case else 0
            seasonal=' · '.join(hunt.SEASONS[i]+' ×'+str(hunt.stat_percent(self.faction,i)/100).replace('.',',') for i in range(4))
            copy=('Необязательное дело о гибели и исчезновениях жителей. Соберите две улики и вычислите, кто из трёх дворян скрывает чудовище. '
                  'База монстра: 260 млн атаки и 310 млн защиты. Сезонные коэффициенты вашей фракции: '+seasonal+'. '
                  'Сезон фиксируется при принятии. Можно сразиться или завладеть сердцем дворянина, обещав победу за 20 ходов.\n'
                  'Победа в бою: дворянин навсегда становится спутником победившего героя без договора и ограничения ходов. '
                  'Его боевые характеристики на 40% ниже тех, с которыми он сражался; сезон дела учитывается. '
                  'Спутник остаётся с отрядом при возвращении домой.')
            if case:
                copy+='\nПредыдущее дело раскрыто героем '+case['hero']+'. Новое дело через '+str(left)+' х.'
                if json.loads(case['scenario']).get('service')=='conquered':
                    copy+='\nПобеждённый дворянин служит без ограничения ходов. Его характеристики снижены на 40%; договор за сердце не заключён.'
            available=bool(party and hunt.heroes(self.conn,party['camp'],self.faction) and not left)
            return copy,[('Принять расследование',lambda *_:self.perform(lambda:hunt.begin(self.conn,self.faction)),available)],'', ''
        story=json.loads(case['scenario']);stage=case['stage'];enemy=hunt.monster(case)
        from utils.helpers import format_number
        copy=story['premise']+'\nГород: '+names[case['city_id']-1]+'. Сезон дела: '+hunt.SEASONS[case['season']]+'.'
        exposed=hunt.revealed(case)
        identified=hunt.identified(case)
        if stage>=2 and identified and not exposed:
            copy+='\n'+hunt.noble_name(case)+' сохраняет человеческий облик и отдаёт вам своё сердце в обмен на обещание победить за 20 ходов.  '
            copy+='После сделки можно менять облик: дворянин усиливает атаку на 50%, ослабляя защиту на 50%; монстр — наоборот.'
        if stage>=2 and exposed:
            if story.get('nobles'):copy+='\n'+story['nobles'][story['culprit']]['name']+' раскрывает свою истинную сущность.'
            copy+='\nМонстр: '+story['monster']+'. Атака: '+format_number(enemy['attack'])+' · Защита: '+format_number(enemy['defense'])+'.'
        buttons=[]
        confirming=False
        if stage<2:
            buttons=[('Опросить свидетеля' if stage==0 else 'Проверить следы',
                      lambda *_:self.perform(lambda:hunt.investigate(self.conn,self.faction)),here==case['city_id'])]
        elif not identified:
            copy+='\nСопоставьте герб и печать на доске расследования, затем выберите дворянина для обвинения.'
            buttons=[('Открыть доску расследования',lambda *_:self.open_board(noble=True),True)]
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
                confirming=True
                copy=(hunt.noble_name(case)+' станет вашим спутником без боя.\n'
                      'Атака: '+format_number(enemy['attack']*3//2)+' · Защита: '+format_number(enemy['defense']//2)+'.\n'
                      'Пол и облик спутника можно менять после сделки.\n\n'
                      'Завладейте сердцем дворянина. Победите в кампании за 20 ходов после принятия. '
                      'Иначе вся ваша армия до конца кампании потеряет 50% боевых характеристик. Кампания продолжится. Возвращение домой срок не продлевает.')
                buttons=[('Завладеть сердцем · '+hero,lambda *_:self.accept_soul(hero),True),
                         ('Отказаться от сделки',lambda *_:self.offer_soul(None),True)]
        if stage<2:buttons.append(('Доска расследования',lambda *_:self.open_board(noble=True),True))
        buttons=[(caption,callback,enabled) for caption,callback,enabled in buttons if 'доск' not in caption.casefold()]
        details='Сердце · Срок: 20 ходов' if confirming else 'Победа: постоянный спутник · Характеристики −40%'
        image=(enemy['unit_image'] if exposed else hunt.noble_image(case)) if stage==2 and identified else ''
        return copy,buttons,details,image

    def open_board(self,noble=False):
        if noble:
            import mirror_monster_quest as hunt
            case=hunt.state(self.conn,self.faction)
            if case and case['stage']==2 and hunt.identified(case):return self.open_noble_encounter()
        from investigation_board_ui import InvestigationBoard
        board=InvestigationBoard(self,noble=noble)
        board.open()
        return board

    def open_noble_encounter(self):
        from noble_encounter_ui import NobleEncounter
        existing=getattr(self,'noble_encounter',None)
        if existing and existing.parent is not None:return existing
        self.noble_encounter=NobleEncounter(self)
        self.noble_encounter.open(animation=False)
        return self.noble_encounter

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
            hunt.claim_heart(self.conn,self.faction,hero)
            self._soul_offer=None
            return 'Сердце дворянина у вас. Спутник присоединился к отряду. Победите за 20 ходов, иначе вся армия получит постоянное проклятие −50%.'
        self.perform(accept)
        from morgana_covenant_ui import show_offer
        show_offer(self.conn,self.faction)

    def hunt_battle(self,hero):
        import mirror_monster_quest as hunt
        if _busy(self.conn):return
        from tactical_battle_bridge import launch_operation
        launch_operation(self.conn,lambda db:hunt.fight(db,self.faction,hero,tactical=True),
                         lambda outcome:self.hunt_battle_result(hero,outcome),
                         lambda error:setattr(self.feedback,'text',error))

    def hunt_battle_result(self,hero,outcome):
        self.perform(lambda:('Дворянин побеждён и навсегда служит герою '+hero+'. Ограничения ходов нет; боевые характеристики −40% от силы противника.'
                             if outcome['won'] else 'Монстр не побеждён. Соберите силы и возвращайтесь в логово.'))
        if outcome.get('tactical'):return
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
        from morgana_covenant_ui import schedule_offer
        schedule_offer(self.conn,self.faction)
