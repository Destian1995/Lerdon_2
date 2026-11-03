"""A map-space light beam completes the saved journey exactly once."""
import math
from kivy.graphics import Color,Ellipse,Line
from kivy.uix.widget import Widget


def route_point(points,progress):
    lengths=[math.dist(a,b) for a,b in zip(points,points[1:])]
    distance=max(0,min(1,progress))*sum(lengths)
    for a,b,length in zip(points,points[1:],lengths):
        if distance<=length:
            u=distance/max(length,1e-9)
            return (a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u)
        distance-=length
    return points[-1]


class BeamTravel(Widget):
    def __init__(self,map_widget,points,accent,done,**kwargs):
        super().__init__(**kwargs)
        self.map_widget=map_widget;self.points=points;self.done=done
        self.age=0;self.finished=False
        self.duration=max(1.7,min(3.,sum(math.dist(a,b) for a,b in zip(points,points[1:]))/220))
        with self.canvas:
            self.glow_color=Color(*accent[:3],.28);self.glow=Line(width=8)
            self.core_color=Color(1,1,1,.95);self.core=Line(width=1.8)
            self.head_color=Color(*accent[:3],1);self.head=Ellipse(size=(9,9))

    def update(self,dt):
        if self.finished:return
        self.age+=min(dt,.15)
        progress=min(1,self.age/self.duration)
        trail=[self.map_widget.point(*route_point(self.points,max(0,progress-.14+i*.14/16))) for i in range(17)]
        self.glow.points=[v for p in trail for v in p];self.core.points=self.glow.points
        x,y=trail[-1];self.head.pos=(x-4.5,y-4.5)
        self.glow_color.a=.23+.1*math.sin(self.age*10)
        if progress>=1:self.finish()

    def finish(self):
        if self.finished:return
        self.finished=True
        self.glow_color.a=self.core_color.a=self.head_color.a=0
        if self.parent:self.parent.remove_widget(self)
        self.done()

    def on_touch_down(self,touch):return False
