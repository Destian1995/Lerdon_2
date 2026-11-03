"""Content-sized cards for the Mirror Realm's small landscape windows."""
import math
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.metrics import sp
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.carousel import Carousel
from strategy_ui import surface,StrategyButton,INK,TEXT,MUTED,GOLD
from utils.ui_text import bind_plain_text


def compact_frame(widget):
    """Keep ornaments inside small cards even at Android density two."""
    border=getattr(widget,'_strategy_frame',None)
    if border is None:return
    def resize(*_):
        x,y=widget.pos;w,h=widget.size
        radius=min(8,h*.16)
        border.outer.width=1; border.inner.width=.7
        border.outer.rounded_rectangle=(x+1,y+1,max(0,w-2),max(0,h-2),radius)
        border.inner.rounded_rectangle=(x+3,y+3,max(0,w-6),max(0,h-6),max(0,radius-2))
        inset=min(7,h*.13,w*.08);length=min(12,h*.22,w*.12)
        for line,(cx,cy,sx,sy) in zip(border.corners,((x+inset,y+inset,1,1),(x+w-inset,y+inset,-1,1),
                                                    (x+inset,y+h-inset,1,-1),(x+w-inset,y+h-inset,-1,-1))):
            line.width=1.2;line.points=(cx,cy+length*sy,cx,cy,cx+length*sx,cy)
    widget.bind(pos=resize,size=resize);resize()


def fitting_font(label,width,height,low,high):
    for _ in range(7):
        size=(low+high)/2
        measure=CoreLabel(text=label.text,font_name=label.font_name,font_size=size,
                          bold=label.bold,text_size=(max(1,width),None),line_height=label.line_height)
        measure.refresh()
        if measure.texture.height<=max(1,height):low=size
        else:high=size
    return low


class FitLabel(Label):
    """Wrap all the copy and fit its font to the allocated cell, without ellipsis."""
    maximum=NumericProperty(16)
    minimum=NumericProperty(9)

    def __init__(self,**kwargs):
        kwargs.setdefault('color',TEXT)
        kwargs.setdefault('halign','left');kwargs.setdefault('valign','middle')
        super().__init__(**kwargs)
        bind_plain_text(self)
        self._fit_event=Clock.create_trigger(self.fit,-1)
        self.bind(size=self._fit_event,text=self._fit_event,maximum=self._fit_event,minimum=self._fit_event)
        self.fit()

    def fit(self,*_):
        width,height=max(1,self.width),max(1,self.height)
        self.font_size=fitting_font(self,width,max(1,height-1),self.minimum,max(self.minimum,self.maximum))
        self.text_size=(width,height)


class FitButton(StrategyButton):
    maximum=NumericProperty(15)

    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        compact_frame(self)
        self._fit_event=Clock.create_trigger(self.fit,-1)
        self.bind(size=self._fit_event,text=self._fit_event,maximum=self._fit_event)
        self.fit()

    def fit(self,*_):
        self.font_size=fitting_font(self,self.width-12,self.height-6,9,max(9,self.maximum))


class CardPager(BoxLayout):
    """One readable card per page, with both swiping and explicit navigation."""
    def __init__(self,accent=GOLD,**kwargs):
        super().__init__(orientation='vertical',spacing=6,**kwargs)
        self.carousel=Carousel(direction='right',loop=False,anim_move_duration=.18,anim_cancel_duration=.12)
        self.nav=BoxLayout(size_hint_y=None,height=40,spacing=8)
        self.previous=FitButton(text='Назад',accent=accent)
        self.counter=FitLabel(text='0 / 0',halign='center',size_hint_x=.55,color=MUTED)
        self.next=FitButton(text='Далее',accent=accent)
        for widget in (self.previous,self.counter,self.next):self.nav.add_widget(widget)
        super().add_widget(self.carousel);super().add_widget(self.nav)
        self.previous.bind(on_release=lambda *_:self.select(self.page_index-1))
        self.next.bind(on_release=lambda *_:self.select(self.page_index+1))
        self.carousel.bind(index=self.update_nav,slides=self.update_nav)
        self.bind(size=self.fit);self.fit();self.update_nav()

    @property
    def pages(self):return self.carousel.slides

    @property
    def page_index(self):return self.carousel.index or 0

    def select(self,index):
        if self.pages:self.carousel.index=max(0,min(index,len(self.pages)-1))

    def clear_cards(self):self.carousel.clear_widgets()

    def add_card(self,card):self.carousel.add_widget(card)

    def update_nav(self,*_):
        count=len(self.pages);index=self.page_index
        self.counter.text=f'{index+1} / {count}' if count else '0 / 0'
        self.previous.disabled=not count or index==0
        self.next.disabled=not count or index==count-1

    def fit(self,*_):
        self.nav.height=min(48,max(36,self.height*.15))
        self.previous.maximum=self.next.maximum=min(sp(18),max(14,self.height*.075))
        self.counter.maximum=min(sp(17),max(14,self.height*.07))


class ArmyCard(BoxLayout):
    def __init__(self,name,count,image,experience,accent,**kwargs):
        super().__init__(spacing=4,**kwargs)
        surface(self,INK,accent)
        compact_frame(self)
        self.portrait=Image(source=image or 'files/status/army.png',size_hint_x=None,mipmap=True)
        self.copy=FitLabel(text=name+'\n'+count+' · '+str(experience)+' поб.',maximum=sp(15))
        self.add_widget(self.portrait);self.add_widget(self.copy)
        self.bind(size=self.fit);self.fit()

    def fit(self,*_):
        self.padding=min(5,self.height*.07)
        self.portrait.width=min(self.height*.86,self.width*.23,64)
        self.copy.maximum=min(sp(16),max(10,self.height*.29))


def army_columns(grid):
    """Pick the grid with the largest readable font for the actual roster."""
    count=len(grid.children)
    if not count or not all(isinstance(c,ArmyCard) for c in grid.children):return 1
    best,quality=1,0
    for cols in range(1,min(3,count)+1):
        rows=math.ceil(count/cols)
        width=(grid.width-grid.spacing[0]*(cols-1))/cols
        height=(grid.height-grid.spacing[1]*(rows-1))/rows
        pad=min(5,height*.07)
        picture=min(height*.86,width*.23,64)
        available=max(1,width-2*pad-picture-4)
        score=16
        for card in grid.children:
            font=fitting_font(card.copy,available,height-2*pad,9,min(sp(16),max(10,height*.29)))
            measure=CoreLabel(text=card.copy.text,font_name=card.copy.font_name,font_size=font,text_size=(available,None))
            measure.refresh()
            if measure.texture.height>height-2*pad+1:score=0;break
            score=min(score,font)
        if score>quality:best,quality=cols,score
    return best if quality else min(3,count)


class MarketCard(BoxLayout):
    def __init__(self,title,subtitle,callback,image=None,caption='Купить',**kwargs):
        super().__init__(orientation='vertical',**kwargs)
        surface(self,INK,GOLD)
        compact_frame(self)
        self.header=BoxLayout(spacing=10)
        self.art=Image(source=image,size_hint_x=None,mipmap=True) if image else None
        if self.art:self.header.add_widget(self.art)
        copy=BoxLayout(orientation='vertical',spacing=6)
        self.title_label=FitLabel(text=title,bold=True,color=GOLD,maximum=sp(17))
        copy.add_widget(self.title_label)
        self.details=FitLabel(text=subtitle,color=MUTED,maximum=sp(14))
        copy.add_widget(self.details)
        self.header.add_widget(copy)
        self.button=FitButton(text=caption,size_hint_y=None)
        self.button.bind(on_release=callback)
        for child in (self.header,self.button):self.add_widget(child)
        self.bind(size=self.fit);self.fit()

    def fit(self,*_):
        self.padding=(min(8,self.width*.06),min(6,max(2,self.height*.025)))
        self.spacing=min(3,self.height*.012)
        self.button.height=min(50,max(36,self.height*.23))
        self.button.maximum=min(sp(20),max(14,self.button.height*.40))
        self.title_label.maximum=min(sp(26),max(16,self.height*.13))
        self.details.maximum=min(sp(21),max(14,self.height*.10))
        if self.art:self.art.width=min(self.width*.39,self.height*.64)


class QuestCard(BoxLayout):
    def __init__(self,title,copy,buttons,accent,**kwargs):
        super().__init__(orientation='vertical',**kwargs)
        surface(self,accent=accent)
        compact_frame(self)
        self.heading=FitLabel(text=title,color=accent,bold=True,size_hint_y=None,maximum=sp(21))
        self.copy=FitLabel(text=copy,maximum=sp(16))
        self.buttons=GridLayout(cols=max(1,len(buttons)),size_hint_y=None,spacing=4)
        self.add_widget(self.heading);self.add_widget(self.copy)
        if buttons:self.add_widget(self.buttons)
        for caption,callback,enabled in buttons:
            button=FitButton(text=caption,accent=accent)
            button.disabled=not enabled;button.bind(on_release=callback)
            self.buttons.add_widget(button)
        self.buttons.bind(size=self.fit)
        self.bind(size=self.fit);self.fit()

    def button_height(self):
        return min(44,max(28,self.height*.16))

    def fit(self,*_):
        self.padding=min(12,self.height*.035)
        self.spacing=min(8,self.height*.020)
        self.heading.height=min(38,max(22,self.height*.13))
        self.heading.maximum=min(sp(21),self.heading.height*.72)
        self.copy.maximum=min(sp(16),max(11,self.height*.07))
        count=len(self.buttons.children)
        self.buttons.cols=1 if count>1 and self.width<240 else max(1,count)
        rows=math.ceil(count/self.buttons.cols)
        self.buttons.height=self.button_height()*rows+4*max(0,rows-1)
        for button in self.buttons.children:
            button.maximum=min(sp(14),max(9,self.buttons.width/max(1,self.buttons.cols)/11))
