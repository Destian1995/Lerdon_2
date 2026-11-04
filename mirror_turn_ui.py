"""Compact turn feedback above the Mirror Realm's action buttons."""
from kivy.graphics import Color,Rectangle
from kivy.uix.widget import Widget
from kivy.metrics import sp
from mirror_layout import FitLabel,compact_frame
from strategy_ui import surface,INK


class MirrorTurnProgress(Widget):
    def __init__(self,accent,**kwargs):
        super().__init__(**kwargs)
        surface(self,INK,accent);compact_frame(self)
        self.label=FitLabel(text='Ходят ИИ…',maximum=sp(17),color=accent,bold=True,halign='center',size_hint=(None,None))
        self.add_widget(self.label)
        with self.canvas:
            Color(*accent[:3],.18);self.track=Rectangle()
            Color(*accent[:3],.9);self.fill=Rectangle()
        self.phase=0;self.progress=0
        self.bind(size=self.layout,pos=self.layout)
        self.layout()

    def update(self,dt,progress,status):
        self.phase=(self.phase+max(0,dt)*.6)%1
        self.progress=max(0,min(1,progress))
        self.label.text=('Завершение хода…' if self.progress>=1 else 'Ходят ИИ…'+(' · '+status if status else ''))
        self.layout()

    def layout(self,*_):
        self.label.pos=(self.x+10,self.y+14)
        self.label.size=(max(1,self.width-20),max(1,self.height-20))
        width=max(1,self.width-20)
        self.track.pos=(self.x+10,self.y+7);self.track.size=(width,5)
        if self.progress:
            self.fill.pos=self.track.pos;self.fill.size=(width*self.progress,5)
        else:
            self.fill.pos=(self.x+10+self.phase*width*.72,self.y+7)
            self.fill.size=(width*.28,5)
