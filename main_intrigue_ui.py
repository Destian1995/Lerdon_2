"""A city tavern: illustrated room, visitors' conversations and clear choices."""
from kivy.metrics import dp,sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from otherworld_ui import WorldPopup,_button
from mirror_readable_ui import ReadableText
from strategy_ui import surface,GOLD,MUTED,StrategyButton
from responsive_ui import ActionDock
from city_war import current_turn
from tavern_art import city_tavern
from utils.resource_text import resource_amount
import main_map_intrigues as plots

GREEN=(.43,.88,.60,1)
CYAN=(.40,.81,1,1)
RED=(1,.48,.42,1)
CATEGORIES=(('rumors','У стойки'),('messenger','Тихий стол'),('citizens','Горожане'),('companion','Спутник'),('intel','Разведка'),('history','Записки'))


class TavernDock(ActionDock):
    """Short replies stay side by side even on portrait phones."""
    def _fit(self,*_):
        for group in self.groups:
            group.orientation='horizontal';group.height=dp(48);group.spacing=dp(5)
            for button in group.children:
                button.size_hint=(1,1)
                button.text_size=(max(1,self.width/max(1,len(group.children))-dp(14)),dp(44))
                button.halign=button.valign='center'
        self.height=dp(48)


class MainIntriguesPopup(WorldPopup):
    def __init__(self,conn,faction,city=None,**kwargs):
        self.conn,self.faction=conn,faction;self.controls={};self.category='rumors'
        state=plots.journal(conn,faction)
        cities=[r[0] for r in conn.execute('SELECT name FROM cities ORDER BY name')]
        own=[c for c in cities if plots.owner(conn,c)==faction]
        pending=state['offers']
        self.city=city or (pending[0]['city'] if pending else next(iter(own or cities),''))
        if any(r['city']==self.city for r in state['offers']):self.category='messenger'
        super().__init__('ТАВЕРНА',accent=GOLD,**kwargs)
        self.heading.size_hint_x=.4;self.heading.font_size=sp(18)
        self.city_picker=Spinner(text=self.city,values=cities,size_hint_x=.6,font_size=sp(14),
                                 background_normal='',background_color=(.19,.13,.08,1),color=GOLD)
        self.header.add_widget(self.city_picker,index=1);self.city_picker.bind(text=self.select_city)
        self.notice=ReadableText('',size=13,color=GREEN,height=0);self.root.add_widget(self.notice)
        self.navigation=GridLayout(cols=6,size_hint_y=None,height=dp(40),spacing=dp(4))
        self.tabs={}
        for key,caption in CATEGORIES:
            button=_button(caption,lambda *_,k=key:self.select_category(k),font_size=sp(12),height=dp(40),size_hint_y=None,accent=GOLD)
            self.tabs[key]=button;self.navigation.add_widget(button)
        self.root.add_widget(self.navigation)
        self.columns=BoxLayout(spacing=dp(10))
        self.room=surface(BoxLayout(padding=dp(4)),(.10,.07,.05,1),GOLD)
        self.art=Image(fit_mode='contain',mipmap=True,nocache=True);self.room.add_widget(self.art)
        self.columns.add_widget(self.room)
        self.scroll=ScrollView(do_scroll_x=False,bar_width=dp(4))
        self.body=surface(BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(9),size_hint_y=None),(.10,.075,.055,1),GOLD)
        self.body.bind(minimum_height=self.body.setter('height'));self.scroll.add_widget(self.body)
        self.columns.add_widget(self.scroll);self.root.add_widget(self.columns)
        self.actions=BoxLayout(spacing=dp(6));self.dock=TavernDock([self.actions]);self.root.add_widget(self.dock)
        self.reload()

    def layout_content(self):
        self.header.height=dp(46)
        self.root.padding=dp(8);self.root.spacing=dp(6)
        if not hasattr(self,'columns'):return
        narrow=self.width<dp(420)
        self.navigation.cols=3 if narrow else 6
        self.navigation.height=dp(84 if narrow else 40)
        for button in self.navigation.children:button.height=dp(40)
        if self.category=='intel':
            self.columns.orientation='vertical';self.columns.spacing=0
            self.room.size_hint=(1,None);self.room.height=0;self.room.opacity=0
            self.scroll.size_hint=(1,1);self.dock.refresh();return
        self.room.opacity=1;self.columns.spacing=dp(10)
        wide=self.width>=dp(550) and self.width>self.height
        self.columns.orientation='horizontal' if wide else 'vertical'
        self.room.size_hint=(.48,1) if wide else (1,None)
        if not wide:self.room.height=min(dp(150),self.height*.25)
        self.scroll.size_hint=(.52,1) if wide else (1,1)
        for button in self.actions.children:button.height=dp(48)
        self.dock.refresh()

    def select_city(self,_,city):
        if city==self.city:return
        self.city=city;self.category='rumors';self.notice.text='';self.reload()

    def select_category(self,key):
        self.category=key;self.notice.text='';self.reload();self.scroll.scroll_y=1

    def say(self,speaker,text):
        self.body.add_widget(ReadableText(speaker,size=18,bold=True,color=GOLD))
        self.body.add_widget(ReadableText('«'+text+'»',size=15))

    def detail(self,text,color=MUTED):
        self.body.add_widget(ReadableText(text,size=14,color=color))

    def choices(self,entries=()):
        self.actions.clear_widgets();self.controls={}
        for key,caption,call in entries:
            button=_button(caption,lambda *_,fn=call:self.choose(fn),height=dp(48),size_hint_y=None,accent=GOLD)
            self.controls[key]=button;self.actions.add_widget(button)
        self.actions.add_widget(_button('Закрыть',self.dismiss,height=dp(48),size_hint_y=None,accent=GOLD))
        self.dock.refresh()

    def choose(self,call):
        from premium_access import allowed
        if self.category in ('rumors','messenger') and not allowed('tavern_quests'):
            self.notice.color=GOLD;self.notice.text='Доступно в полной версии.'
            return
        before={r[0] for r in self.conn.execute('SELECT unit_name FROM map_companion_temper WHERE departed=1')}
        try:
            result=call();self.conn.commit()
        except ValueError as error:
            self.notice.color=RED;self.notice.text=str(error);return
        from utils.resource_payments import sync_resources
        sync_resources(self.conn,self.faction)
        left={r[0] for r in self.conn.execute('SELECT unit_name FROM map_companion_temper WHERE departed=1')}-before
        self.notice.color=RED if left else GREEN
        self.notice.text='Спутник покинул ваш отряд: доверие упало до нуля.' if left else 'Ваше решение принято.'
        if isinstance(result,dict) and 'detected' in result:
            from intelligence_cards import money
            self.notice.color=RED if result['detected'] else GREEN
            self.notice.text=money(result['cost'])+' крон списано. '+(
                f"Разведка обнаружена: отношения −35 → {result['relation']}%."
                if result['detected'] else 'Сведения на 2 хода. Разведчики не обнаружены.')
        refresh=getattr(self,'_relations_changed',None)
        if refresh:refresh()
        self.reload()
        from game_process import refresh_map
        refresh_map()

    def reload(self):
        self.body.clear_widgets();self.choices()
        from premium_access import allowed
        if self.category in ('rumors','messenger') and not allowed('tavern_quests'):
            from premium_options_ui import FullVersionNotice
            self.body.add_widget(FullVersionNotice(on_change=self.reload))
        self.art.source=city_tavern(self.conn,self.city,self.faction)
        state=plots.journal(self.conn,self.faction,self.city)
        for key,button in self.tabs.items():button.opacity=1 if key==self.category else .65
        if self.category=='rumors':self.rumor(state)
        elif self.category=='messenger':self.messenger(state)
        elif self.category=='citizens':self.citizens(state)
        elif self.category=='companion':self.companion(state)
        elif self.category=='intel':self.intelligence()
        else:
            self.say('Хозяин таверны','Бумага помнит слова лучше, чем посетители после третьей кружки. Вот ваши последние известия.')
            for row in state['log']:self.detail('Ход '+str(row['event_turn'])+' · '+row['message'])
        self.layout_content()

    def select_intelligence(self,target):
        self.intel_target=target;self.reload();self.scroll.scroll_y=0

    def intelligence(self):
        from army_intelligence import remaining,gather,quote
        from intelligence_cards import ScoutCards,scout_card,money
        self.detail('РАЗВЕДСЕТЬ · СВЕДЕНИЯ НА 2 ХОДА',GOLD)
        if plots.owner(self.conn,self.city) not in (self.faction,'Нейтрал'):
            self.detail('Разведчики работают в тавернах своих и нейтральных городов.');return
        targets=[r[0] for r in self.conn.execute(
            'SELECT DISTINCT faction FROM cities WHERE faction NOT IN (?,?,?) ORDER BY faction',
            (self.faction,'Нейтрал','Мятежники'))]
        from alliance_rules import allies
        friendly=allies(self.conn,self.faction)
        targets=[target for target in targets if target not in friendly]
        selected=getattr(self,'intel_target',None)
        grid=ScoutCards();self.body.add_widget(grid)
        for target in targets:
            price=quote(self.conn,self.faction,target)
            card,button=scout_card(target,price.total,remaining(self.conn,self.faction,target),selected==target,self.select_intelligence)
            grid.add_widget(card);self.controls[('intel',target,'select')]=button
        if selected not in targets:
            return
        price=quote(self.conn,self.faction,selected);left=remaining(self.conn,self.faction,selected)
        self.say('Донесение · '+selected,'Сила армии и гарнизоны откроются на текущий и следующий ход.')
        self.detail('База: 76 000 крон',GOLD)
        self.detail(f'Отношения {price.relation}%: {100-price.relation} × {money(price.rate)} = {money(price.relation_cost)}',GOLD)
        self.detail(f'Империя: {price.cities} × 25 000 = {money(price.cities*25000)}',GOLD)
        self.detail(('Следующее донесение: ' if left==2 else 'ИТОГО: ')+money(price.total)+' крон',GOLD)
        self.detail(f'Обнаружение: 40% · отношения −35: {price.relation}% → {max(0,price.relation-35)}%',RED)
        balance=self.conn.execute("SELECT amount FROM resources WHERE faction=? AND resource_type='Кроны'",(self.faction,)).fetchone()
        affordable=bool(balance and balance[0]>=price.total)
        key=('intel',selected,'gather')
        self.choices([(key,'Оплатить разведку',lambda:gather(self.conn,self.faction,selected,self.city,expected_cost=price.total))])
        self.controls[key].disabled=not affordable or left==2
        if left==2:self.controls[key].text='Сведения актуальны'
        elif not affordable:self.controls[key].text='Недостаточно крон'


    def rumor(self,state):
        if plots.owner(self.conn,self.city) not in (self.faction,'Нейтрал'):
            self.say('Хозяин таверны','О чужих делах здесь говорят вполголоса. Если вас ждёт тайный посланник, он сидит за тихим столом.');return
        row=next(iter(state['secrets']),None)
        if not row or row['stage']<2 or row['resolution']=='conceal':
            self.say('Посетители у стойки','Слышали, что творится в городе? Подсаживайтесь. Есть разговор о деньгах и о том, какую цену за них платят люди.')
            self.detail('Выслушать разговор можно бесплатно. Решение можно отложить, закрыв таверну.')
            self.choices([(('secret',self.city,'investigate'),'Послушать',lambda:plots.investigate(self.conn,self.faction,self.city))]);return
        kind=row['kind']
        speakers={'factory':'Мастер фабрики','hospital':'Городской лекарь','tribute':'Караванщик'}
        speech={'factory':'В цехах трудятся пленники. Что прикажете делать?',
                'hospital':'Лекари скрывают заражение ради платы за лечение. Как нам поступить?',
                'tribute':'Ночью отправляется караван с данью существам Зазеркалья. Решать вам.'}
        self.say(speakers[kind],speech[kind])
        if row['stage']==3:
            self.detail('Ваш ответ: '+('поощрить' if row['resolution']=='exploit' else 'раскрыть и остановить сговор'),GREEN)
            if kind in ('factory','hospital'):
                if not row['policy_active']:self.detail('Прежнее решение утратило силу после смены власти в городе.')
                else:self.policy_lines(kind,row['resolution'])
            self.detail('Этот разговор уже завершён. Повторной выплаты или повторного изменения отношений не будет.');return
        if kind in ('factory','hospital'):
            self.detail('Если поощрить:',GOLD);self.policy_lines(kind,'exploit')
            self.detail('Если раскрыть:',GREEN);self.policy_lines(kind,'expose')
            self.detail('Проценты относятся только к этому городу и действуют постоянно, пока город ваш и соответствующее здание работает. Отрезанный от снабжения город не даёт бонусов.')
            labels=('Поощрить','Раскрыть')
        else:
            attack=plots.caravan_quote(self.conn,self.faction,'exploit');arrest=plots.caravan_quote(self.conn,self.faction,'expose')
            self.detail('Ограбить: +35% от текущего запаса крон; отношения со всеми фракциями −25 п.п.',GOLD)
            self.detail('Сейчас получите '+resource_amount(attack['actual'],'Кроны')+' с учётом лимита хранилища.',GOLD)
            self.detail('Раскрыть и арестовать: −10% текущего запаса крон; отношения со всеми фракциями +5 п.п.',GREEN)
            self.detail('Сейчас потребуется '+resource_amount(arrest['amount'],'Кроны')+'. Отношения остаются в пределах 0–100%.')
            labels=('Ограбить','Арестовать')
        self.detail('Спутник: поощрение или грабёж −20 доверия; раскрытие +10. При 20 возникает конфликт, при 0 спутник покинет героя.',RED)
        self.choices([(('secret',self.city,c),label,lambda c=c:plots.resolve_secret(self.conn,self.faction,self.city,c)) for c,label in zip(('exploit','expose'),labels)])

    def policy_lines(self,kind,choice):
        crowns,crystals,growth=plots.CITY_POLICIES[(kind,choice)]
        for label,value,color in (('Доход крон',crowns,GOLD),('Добыча кристаллов',crystals,CYAN),('Прирост населения',growth,GREEN)):
            if value:self.detail(f'{label} города: {value:+d}%.',color)

    def messenger(self,state):
        row=next(iter(state['offers']),None)
        if not row:self.say('Человек за тихим столом','Сегодня для вас нет тайных писем. Во время войны дворяне соседних городов порой ищут нового покровителя.');return
        terms={'governor':'Оставьте мне управление городом и пощадите жителей.',
               'rescue':'Заплатите 20 000 крон за спасение моей семьи и пощадите жителей после штурма.',
               'betray':'Разорвите союз с '+str(row['ally'])+' и объявите им войну. А мой город после захвата пощадите.'}
        self.say(row['noble'],terms[row['condition']]+' Взамен мои люди откроют ворота.')
        self.detail('Защита гарнизона −50% в одном вашем обычном штурме. Срок: '+str(max(0,row['deadline']-current_turn(self.conn)))+' х. Даже неудачный штурм расходует саботаж.')
        if row['status']=='offered':
            self.choices([(('offer',row['id'],'accept'),'Согласиться',lambda:plots.accept_offer(self.conn,self.faction,row['id'])),
                          (('offer',row['id'],'reject'),'Отказаться',lambda:plots.reject_offer(self.conn,self.faction,row['id']))])
        else:self.detail('Заговор подготовлен. Прикажите своей армии атаковать город.',GREEN)

    def citizens(self,state):
        from city_opinions import conversations
        from otherworld_ui import _screen
        screen=_screen(self.conn)
        rates={}
        if screen:
            rates.update({f:34 for f in getattr(screen,'ai_controllers',{})})
            player=getattr(screen,'faction',None)
            if player is not None:rates[screen.selected_faction]=getattr(player,'current_tax_rate',None)
        for speaker,text in conversations(self.conn,self.city,rates):self.say(speaker,text)

    def companion(self,state):
        if not state['companions']:
            left=self.conn.execute('SELECT 1 FROM map_companion_temper WHERE faction=? AND departed=1',(self.faction,)).fetchone()
            self.say('Свободное место за столом','Ваш спутник ушёл, потеряв доверие к вам. Он больше не служит вашему герою.' if left else 'Сейчас у героя нет спутника, с которым можно обсудить эти решения.');return
        for row in state['companions']:
            name=row['unit_name'].split(' / ')[0].removeprefix('Спутник: ')
            self.say(name,'Я вижу, какие решения вы принимаете. Деньги не заменят доверия.')
            self.detail(f"Доверие: {row['loyalty']} / 100. При 0 спутник покинет героя.",GREEN if row['loyalty']>20 else RED)
            left=max(0,row['conflict_until']-current_turn(self.conn))
            if left:self.detail(f'Конфликт: дворянский облик −25% к атаке и защите, ещё {left} х.',RED)
            self.detail(f"Чудовищная сущность: +{row['blood']*5}% к атаке и защите. Милосердие даёт +10 доверия, жестокость отнимает 20.")


def advisor_panel(screen,advisor):
    root=BoxLayout(orientation='vertical',spacing=dp(6))
    # This is a transient owner for a modal chat, not a separate opaque screen.
    root._strategy_no_theme=True
    root.add_widget(advisor)
    button=StrategyButton(text='Таверна · разговоры и тайные сделки',size_hint_y=None,height=dp(48),accent=GOLD)
    def refresh_chat(*_):
        chat=getattr(advisor,'diplomacy_chat',None)
        target=getattr(chat,'selected_faction',None)
        if target and not getattr(chat,'_disposed',False):chat.update_relation_info_android(target)
    def open_tavern(*_):
        popup=MainIntriguesPopup(screen.conn,screen.selected_faction)
        popup._relations_changed=refresh_chat
        popup.bind(on_dismiss=refresh_chat);popup.open()
    button.bind(on_release=open_tavern)
    # Keep tavern access inside the modal, where it can actually be pressed.
    # It must not survive as an opaque footer after the chat has closed.
    footer_host=getattr(advisor,'chat_content',None) or root
    footer_host.add_widget(button)

    def remove_panel():
        parent=root.parent
        if parent is None:return
        parent.remove_widget(root)
        # A delayed dismissal must not reset a different tab opened meanwhile.
        if parent is getattr(screen,'game_area',None) and not parent.children:
            deactivate=getattr(screen,'deactivate_all_tabs',None)
            if deactivate:deactivate()

    def advisor_parent_changed(widget,parent):
        if parent is None:remove_panel()

    def panel_parent_changed(widget,parent):
        if parent is not None:
            # Popup dismissal can finish before game_area receives the owner.
            # Kivy sets parent before inserting into parent.children.
            if getattr(advisor,'_closed',False):
                from kivy.clock import Clock
                Clock.schedule_once(lambda dt:remove_panel(),0)
        elif not getattr(advisor,'_closed',False):
            close=getattr(advisor,'close_window',None)
            if close:close(None)

    advisor.bind(parent=advisor_parent_changed)
    root.bind(parent=panel_parent_changed)
    return root
