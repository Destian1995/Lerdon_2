"""A touch-first cork investigation board; all decisions use existing quest actions."""
import json
import random
from kivy.clock import Clock
from kivy.graphics import Color,Rectangle,Line,Ellipse,PushMatrix,PopMatrix,Rotate
from kivy.metrics import dp,sp,Metrics
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from otherworld_ui import WorldPopup,_button,_busy
from otherworld_themes import image_path,theme
from mirror_readable_ui import ReadableText
import otherworld_quests as quests
import otherworlds as worlds

INK=(.20,.14,.09,1)
RED=(.62,.19,.15,1)
BRASS=(.83,.65,.36,1)


def paper_label(text,size=14,bold=False,color=INK):
    label=Label(text=text,font_size=sp(size),bold=bold,color=color,halign='left',valign='middle',size_hint_y=None)
    label._strategy_no_theme=True
    return label


class PinnedCard(ButtonBehavior,BoxLayout):
    def __init__(self,key,title,copy,stamp,callback=None,portrait='',angle=0,**kwargs):
        super().__init__(orientation='vertical',size_hint=(None,None),padding=(dp(12),dp(20),dp(12),dp(10)),spacing=dp(5),**kwargs)
        self._strategy_no_theme=True
        self.key,self.callback,self.angle=key,callback,angle
        self.chosen=False;self.portrait=None
        self.heading=paper_label(title,15,True)
        self.add_widget(self.heading)
        if portrait:
            self.portrait=Image(source=portrait,fit_mode='contain',size_hint_y=None,height=dp(140))
            self.portrait._strategy_no_theme=True
            self.add_widget(self.portrait)
        self.note=paper_label(copy,14);self.add_widget(self.note)
        self.stamp=paper_label(stamp,12,True,RED);self.add_widget(self.stamp)
        self.bind(pos=self.paint,size=self.paint,on_release=self.activate)

    def fit(self,width):
        self.width=width
        total=dp(30)+dp(5)*(len(self.children)-1)
        for label in (self.heading,self.note,self.stamp):
            label.text_size=(max(1,width-dp(24)),None);label.texture_update()
            label.height=max(dp(20),label.texture_size[1]+dp(2));total+=label.height
        if self.portrait:total+=self.portrait.height
        self.height=max(dp(132),total)
        return self.height

    @property
    def pin(self):return self.center_x,self.top-dp(10)

    def activate(self,*_):
        if self.callback:self.callback(self.key)

    def paint(self,*_):
        self.canvas.before.clear();self.canvas.after.clear()
        with self.canvas.before:
            PushMatrix();Rotate(angle=self.angle,origin=self.center)
            Color(0,0,0,.30);Rectangle(pos=(self.x+dp(3),self.y-dp(4)),size=self.size)
            Color(*((.97,.89,.68,1) if self.chosen else (.89,.83,.68,1)))
            Rectangle(pos=self.pos,size=self.size)
            Color(*((.52,.22,.15,1) if self.chosen else (.65,.53,.35,1)))
            Line(rectangle=(self.x+dp(2),self.y+dp(2),self.width-dp(4),self.height-dp(4)),width=dp(1.3 if self.chosen else .6))
            Color(.56,.41,.24,.16)
            for i in range(4):
                y=self.y+dp(28+i*17)
                if y<self.top-dp(38):Line(points=(self.x+dp(10),y,self.right-dp(10),y),width=.5)
        with self.canvas.after:
            x,y=self.pin
            Color(0,0,0,.25);Ellipse(pos=(x-dp(3),y-dp(5)),size=(dp(10),dp(10)))
            Color(*RED);Ellipse(pos=(x-dp(4),y-dp(4)),size=(dp(8),dp(8)))
            Color(1,.69,.48,.9);Ellipse(pos=(x-dp(2),y+dp(1)),size=(dp(3),dp(2)))
            PopMatrix()


class CorkBoard(FloatLayout):
    def __init__(self,**kwargs):
        super().__init__(size_hint_y=None,**kwargs)
        self._strategy_no_theme=True
        self.notes=[];self.suspects=[];self.ordered=[];self.selected=None
        self.case_cards=[]
        self.minimum_height=0
        self.label=paper_label('УЛИКИ',15,True,(.98,.88,.69,1));self.label.size_hint=(None,None)
        self.dossiers=paper_label('ПОДОЗРЕВАЕМЫЕ',15,True,(.98,.88,.69,1));self.dossiers.size_hint=(None,None)
        self.add_widget(self.label);self.add_widget(self.dossiers)
        self._fit=Clock.create_trigger(self.layout_board,-1)
        self.bind(width=self._fit,pos=self._fit)

    def set_cards(self,notes,suspects,ordered,case_cards=()):
        for card in self.notes+self.suspects+self.case_cards:self.remove_widget(card)
        self.notes,self.suspects,self.ordered=notes,suspects,ordered
        self.case_cards=list(case_cards)
        for card in self.case_cards+notes+suspects:self.add_widget(card)
        self._fit()

    def layout_board(self,*_):
        width=max(dp(140),self.width)
        cols=3 if width>=dp(580) else 2 if width>=dp(340) else 1
        margin=dp(22);gap=dp(18)
        card_width=max(dp(100),(width-margin*2-gap*(cols-1))/cols)
        rows=[]
        if self.case_cards:
            first=self.case_cards[0];first.fit(width-margin*2)
            rows.append(('folder',[first],first.height+dp(22)))
            for i in range(1,len(self.case_cards),cols):
                row=self.case_cards[i:i+cols]
                rows.append(('cards',row,max(card.fit(card_width) for card in row)+dp(28)))
        for group,label in ((self.notes,self.label),(self.suspects,self.dossiers)):
            if not group:
                label.size=(0,0);continue
            rows.append(('label',label,dp(32)))
            for i in range(0,len(group),cols):
                row=group[i:i+cols]
                rows.append(('cards',row,max(card.fit(card_width) for card in row)+dp(28)))
        self.height=max(self.minimum_height,dp(28)+sum(row[2] for row in rows)+dp(14))
        top=self.top-dp(18)
        for kind,items,height in rows:
            if kind=='label':items.pos=(self.x+margin,top-height);items.size=(width-2*margin,height)
            else:
                for col,card in enumerate(items):card.pos=(self.x+margin+col*(card_width+gap),top-card.height-dp(12))
            top-=height
        self.paint()

    def paint(self):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(.24,.14,.085,1);Rectangle(pos=self.pos,size=self.size)
            Color(.40,.26,.15,1);Rectangle(pos=(self.x+dp(9),self.y+dp(9)),size=(self.width-dp(18),self.height-dp(18)))
            Color(.53,.37,.23,1);Line(rectangle=(self.x+dp(5),self.y+dp(5),self.width-dp(10),self.height-dp(10)),width=dp(2))
            rng=random.Random(31)
            for _ in range(380):
                x=self.x+dp(12)+rng.random()*max(1,self.width-dp(24));y=self.y+dp(12)+rng.random()*max(1,self.height-dp(24))
                Color(.82,.64,.39,rng.uniform(.06,.22));Rectangle(pos=(x,y),size=(dp(rng.uniform(1,4)),dp(rng.uniform(1,3))))
            notes={card.key:card for card in self.notes}
            chain=[notes[key] for key in self.ordered if key in notes]
            if self.selected:
                chosen=next((card for card in self.suspects if card.key==self.selected),None)
                if chosen:chain.append(chosen)
            for first,second in zip(chain,chain[1:]):
                a,b=first.pin,second.pin
                Color(0,0,0,.30);Line(bezier=(*a,a[0]+dp(12),a[1]+dp(32),b[0]-dp(12),b[1]+dp(32),*b),width=dp(2))
                Color(.75,.22,.16,1);Line(bezier=(*a,a[0]+dp(12),a[1]+dp(32),b[0]-dp(12),b[1]+dp(32),*b),width=dp(1.15))


class InvestigationBoard(WorldPopup):
    def __init__(self,journal,noble=False,**kwargs):
        self.journal,self.conn,self.faction=journal,journal.conn,journal.faction
        self.noble=noble;self.selected=None;self.last_feedback=''
        super().__init__('ДОСКА РАССЛЕДОВАНИЯ',accent=BRASS,**kwargs)
        self.case_title=ReadableText('',size=17,bold=True,color=BRASS);self.root.add_widget(self.case_title)
        self.status=ReadableText('',size=14);self.root.add_widget(self.status)
        self.scroll=ScrollView(do_scroll_x=False,bar_width=dp(4));self.root.add_widget(self.scroll)
        self.board=CorkBoard();self.scroll.add_widget(self.board)
        self.scroll.bind(height=self.viewport_changed)
        self.actions=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(6));self.root.add_widget(self.actions)
        self.reset_button=_button('Снять улики',self.reset,accent=BRASS)
        self.accuse_button=_button('Выберите подозреваемого',self.accuse,accent=BRASS)
        self.actions.add_widget(self.reset_button);self.actions.add_widget(self.accuse_button)
        self.bind(on_dismiss=self.cleanup)
        Metrics.bind(density=self.refit,fontscale=self.refit)
        self.refresh()

    def layout_content(self):
        if not hasattr(self,'board'):return
        compact=self.root.width<dp(420)
        self.root.padding=dp(7);self.root.spacing=dp(5);self.header.height=dp(40)
        self.heading.text='ДОСКА УЛИК' if compact else 'ДОСКА РАССЛЕДОВАНИЯ'
        self.heading.font_size=sp(17)
        self.actions.orientation='vertical' if compact else 'horizontal'
        self.actions.height=dp(102 if compact else 52)
        self.board._fit()

    def viewport_changed(self,_,height):
        self.board.minimum_height=height;self.board._fit()

    def refit(self,*_):
        self.refresh()

    def refresh(self):
        self._primary_action=None
        if self.noble:return self.refresh_noble()
        run=quests.state(self.conn,self.faction)
        if not run:return self.dismiss()
        detective=quests.details(run)['detective'];stage=run['detective']
        party=worlds.party(self.conn,self.faction);here=party['city_id'] if party else 0
        self.here=here==detective['cities'][2];self.finished=stage==3
        self.case_title.text=detective['title']+(' · ДЕЛО РАСКРЫТО' if self.finished else '')
        collected,arranged=quests.evidence(self.conn,self.faction)
        self.ready=stage==2 and (not detective.get('search_sites') or len(arranged)==3)
        notes=quests.evidence_notes(run)
        self.evidence_order=arranged
        cards=[]
        order=list(arranged)+[key for key in reversed(quests.EVIDENCE_ORDER) if key not in arranged]
        for key in order:
            i=quests.EVIDENCE_ORDER.index(key);known=key in collected
            stamp=('СВЯЗЬ '+str(arranged.index(key)+1)+' · ПРИКРЕПЛЕНО') if key in arranged else 'НАЖМИТЕ, ЧТОБЫ ПРИКРЕПИТЬ' if known and self.here and stage==2 else 'ПОДШИТО К ДЕЛУ' if known else 'УЛИКА ПОКА НЕ НАЙДЕНА'
            body=notes[i] if known else 'Отправляйтесь к месту расследования. Здесь появятся найденные сведения.'
            if i==0 and known and detective.get('search_sites'):
                body+='\nМесто поиска: '+detective['search_sites'][detective['search_answer']]+'.'
            callback=self.place if known and key not in arranged and self.here and stage==2 else None
            cards.append(PinnedCard(key,key,body,stamp,callback,angle=(-1.2,.9,-.7)[i]))
        self.suspect_names=detective['suspects'];suspects=[]
        for i,name in enumerate(self.suspect_names):
            solved=self.finished and i==run['culprit']
            stamp='ВИНОВНЫЙ УСТАНОВЛЕН' if solved else 'ВЫБРАН ДЛЯ ОБВИНЕНИЯ' if name==self.selected else 'НАЖМИТЕ ДЛЯ ВЫБОРА'
            card=PinnedCard(name,name,detective['tokens'][i] if stage>=2 else 'Примета ещё не установлена.',stamp,self.select_suspect,
                            portrait=image_path(self.faction,'units',('sentinel','weaver','rider')[i]),angle=(.7,-1,.8)[i])
            card.chosen=name==self.selected or solved;suspects.append(card)
        names=theme(self.faction)['cities'];places=detective['cities']
        route=('Опросите свидетеля: '+names[places[0]-1], 'Найдите улику: '+names[places[1]-1],
               'Сопоставьте материалы и предъявите обвинение: '+names[places[2]-1],detective['solved'])[stage]
        copy=detective['premise']+'\n'+route+'.\nНаграда: Венец истины · 25 ходов. Ошибка при поиске или обвинении обнуляет все кроны.'
        choices=[]
        if stage==0:choices=[('Опросить свидетеля',lambda *_:self.journal.step('witness'),here==places[0])]
        if stage==1:
            sites=detective.get('search_sites')
            choices=[('Искать: '+site,lambda *_,place=site:self.journal.step('ledger',place),here==places[1]) for site in sites] if sites else [('Изучить записи',lambda *_:self.journal.step('ledger'),here==places[1])]
        folders=self.make_materials(copy,choices)
        self.board.selected=self.selected;self.board.set_cards(cards,suspects,arranged,folders)
        self.reset_button.disabled=not (self.here and stage==2 and arranged)
        self.accuse_button.disabled=not (self.here and self.ready and self.selected)
        self.accuse_button.text='Дело раскрыто' if self.finished else 'Обвинить: '+self.selected if self.selected else 'Выберите подозреваемого'
        if stage<2:self.configure_primary(choices)
        city=theme(self.faction)['cities'][detective['cities'][2]-1]
        self.status.text=('Цепочка: показание → находка → запись. Нажимайте на улики в нужном порядке.\n' if stage==2 else '')+(
            'Дело раскрыто. Материалы сохранены.' if self.finished else 'Обвинение доступно в городе «'+city+'».\nОшибка при обвинении обнулит все ваши кроны.' if not self.here else 'Выберите подозреваемого после размещения улик. Ошибка при обвинении обнулит все кроны.')

        if stage<2:self.status.text='Изучайте материалы дела и выполняйте действия на карточках доски.'

    def refresh_noble(self):
        import mirror_monster_quest as hunt
        case=hunt.state(self.conn,self.faction)
        party=worlds.party(self.conn,self.faction);here=party['city_id'] if party else 0
        names=theme(self.faction)['cities']
        copy,choices,details,image=self.journal.noble_materials(case,party,here,names)
        folders=self.make_materials(copy,choices,details,image)
        if not case:
            self.case_title.text='Исчезнувшие жители'
            self.here=False;self.finished=False;self.ready=False
            self.board.selected=None;self.board.set_cards([],[],[],folders)
            self.reset_button.text='Вернуться к журналу';self.reset_button.disabled=False
            self.configure_primary(choices)
            self.status.text='Примите дело на доске, чтобы начать расследование.'
            return
        story=json.loads(case['scenario']);people=story.get('nobles',[])
        party=worlds.party(self.conn,self.faction);self.here=bool(party and party['city_id']==case['city_id'])
        self.finished=hunt.identified(case);self.ready=case['stage']==2 and not self.finished
        self.case_title.text=story['title']+(' · ДВОРЯНИН РАЗОБЛАЧЁН' if self.finished else '')
        registry='\n'.join(n['name']+': '+n['crest']+', '+n['mark'] for n in people)
        notes=[('Показание свидетеля',story['witness'],case['stage']>=1),('Дворянский реестр',registry,True),('След на месте исчезновения',story['clue'],case['stage']>=2)]
        cards=[PinnedCard(key,key,copy if known else 'Сведения ещё не собраны.', 'ПОДШИТО К ДЕЛУ' if known else 'УЛИКА НЕ НАЙДЕНА',angle=(-1,.8,-.5)[i]) for i,(key,copy,known) in enumerate(notes)]
        ordered=[key for key,_,known in notes if known]
        self.suspect_names=[n['name'] for n in people];suspects=[]
        for i,n in enumerate(people):
            name=n['name'];cleared=name in story.get('cleared',[])
            stamp='ОПРАВДАН' if cleared else 'РАЗОБЛАЧЁН' if self.finished and i==story['culprit'] else 'СВЕРЬТЕ ГЕРБ И ПЕЧАТЬ'
            portrait=hunt.noble_portrait(case,name)
            card=PinnedCard(name,name,'Герб: '+n['crest']+'\nПечать: '+n['mark'],stamp,None if cleared else self.select_suspect,portrait=portrait,angle=(-.6,.8,-1)[i])
            card.chosen=name==self.selected or self.finished and i==story['culprit'];suspects.append(card)
        self.board.selected=self.selected;self.board.set_cards(cards,suspects,ordered,folders)
        self.reset_button.text='Вернуться к заданию';self.reset_button.disabled=False
        self.accuse_button.disabled=not (self.here and self.ready and self.selected)
        self.accuse_button.text='Дворянин разоблачён' if self.finished else 'Обвинить: '+self.selected if self.selected else 'Выберите подозреваемого'
        self.status.text='Совпасть должны обе улики: герб и печать. Ошибочно обвинённые дворяне будут оправданы.' if not self.finished else 'Личность установлена. Выслушайте дворянина и выберите действие на доске.'
        if not self.here:self.status.text+='\nДля обвинения вернитесь в город расследования.'
        if case['stage']<2 or self.finished:self.configure_primary(choices)

    def make_materials(self,copy,choices,details='',image=''):
        text=copy+('\n\n'+self.last_feedback if self.last_feedback else '')
        cards=[PinnedCard('case-folder','Материалы дела',text,details or 'ДОСЬЕ РАССЛЕДОВАНИЯ',portrait=image)]
        for index,(caption,callback,enabled) in enumerate(choices):
            action=(lambda _,cb=callback,name=caption:self.run_action(cb,name)) if enabled else None
            cards.append(PinnedCard('case-action-'+str(index),caption,
                'Нажмите на карточку, чтобы выполнить действие.' if enabled else 'Действие пока недоступно. Проверьте место, этап дела и наличие героя.',
                'ДЕЙСТВИЕ ПО ДЕЛУ' if enabled else 'НЕДОСТУПНО',action,angle=(-.6,.8,-.5)[index%3]))
        return cards

    def configure_primary(self,choices):
        self._primary_action=None
        if len(choices)==1:
            caption,callback,enabled=choices[0]
            self._primary_action=lambda:self.run_action(callback,caption)
            self.accuse_button.text=caption;self.accuse_button.disabled=not enabled
        else:
            self.accuse_button.text='Выберите действие на доске' if choices else 'Материалы дела'
            self.accuse_button.disabled=True

    def run_action(self,callback,caption=''):
        if _busy(self.conn):return
        if caption.startswith('В бой'):
            self.dismiss();callback();return
        callback()
        self.last_feedback=self.journal.feedback.text
        self.journal.feedback.text=''
        self.refresh()

    def place(self,key):
        if _busy(self.conn):return
        self.run_action(lambda:self.journal.step('arrange',key))

    def select_suspect(self,name):
        if self.finished:return
        self.selected=name;self.refresh()

    def reset(self,*_):
        if self.noble:return self.dismiss()
        if self.reset_button.disabled or _busy(self.conn):return
        self.selected=None;self.run_action(lambda:self.journal.step('reset_board'))

    def accuse(self,*_):
        if self.accuse_button.disabled or _busy(self.conn):return
        if self._primary_action is not None:return self._primary_action()
        if self.noble:
            import mirror_monster_quest as hunt
            self.journal.perform(lambda:hunt.accuse(self.conn,self.faction,self.selected))
        else:self.journal.step('accuse',self.selected)
        self.last_feedback=self.journal.feedback.text;self.journal.feedback.text=''
        if self.noble:
            case=hunt.state(self.conn,self.faction)
            if case and case['stage']==2 and hunt.identified(case):
                self.dismiss(animation=False)
                self.journal.open_noble_encounter()
                return
        self.selected=None;self.refresh()

    def cleanup(self,*_):
        Metrics.unbind(density=self.refit,fontscale=self.refit)
        self.board._fit.cancel()
