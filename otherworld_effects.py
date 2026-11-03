"""A single, disposable clock for the Mirror Realm's magical map ambience."""
import math
from kivy.clock import Clock
from kivy.graphics import Color,Ellipse,Line
from kivy.uix.widget import Widget


class MirrorEffects(Widget):
    def __init__(self,map_widget,**kwargs):
        super().__init__(**kwargs)
        self.map_widget=map_widget
        accent=map_widget.owner.accent
        self._event=None;self.age=0
        self.motes=[]
        with self.canvas:
            for i in range(28):
                color=Color(*accent[:3],0)
                shape=Ellipse(size=(2,2))
                self.motes.append((color,shape))
            self.gate_color=Color(*accent[:3],.5)
            self.gate=Line(width=1.2)
            self.party_color=Color(.50,.97,.83,.7)
            self.party=Line(width=1.4)

    def start(self,*_):
        if self._event is None:self._event=Clock.schedule_interval(self.update,1/30)

    def stop(self,*_):
        if self._event:self._event.cancel();self._event=None

    def update(self,dt):
        self.age+=min(dt,.1)
        w=self.map_widget
        beam=getattr(w,'beam',None)
        if beam and not beam.finished:beam.update(dt)
        scale=min(w.width/1200,w.height/800)*w.camera.zoom
        for i,(color,shape) in enumerate(self.motes):
            node=w.nodes[i%len(w.nodes)]
            phase=self.age*(.22+i%4*.04)+i*1.7
            x,y=w.point(node['x'],node['y'])
            radius=(28+i%5*8)*max(.6,scale)
            color.a=max(0,math.sin(phase*1.4))*.65
            size=(2+i%3)*max(.6,scale)
            shape.size=(size,size)
            shape.pos=(x+math.cos(phase)*radius,y+math.sin(phase*.7)*radius+20*scale)
        node=w.nodes[0];x,y=w.point(node['x'],node['y'])
        radius=max(23,45*scale)
        self.gate.ellipse=(x-radius,y-radius*.45,radius*2,radius*.9,0,360)
        self.gate_color.a=.25+.18*math.sin(self.age*1.5)
        current=next((c for c in w.nodes if c['id']==getattr(w,'_current_city',None)),None)
        self.party_color.a=.55+.2*math.sin(self.age*2) if current else 0
        if current:
            x,y=w.point(current['x'],current['y'])
            self.party.ellipse=(x-radius,y-radius*.45,radius*2,radius*.9,0,360)

    def on_touch_down(self,touch):return False
    def on_touch_move(self,touch):return False
    def on_touch_up(self,touch):return False
