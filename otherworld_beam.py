"""A small white sun follows the road and completes a saved journey once."""
import math
from kivy.graphics import Color,Ellipse
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
        self.halos=[]
        with self.canvas:
            for radius,opacity in ((17,.02),(15,.03),(13,.045),(11,.065),(9,.10),(7,.17),(5.7,.32)):
                color=Color(1,1,1,opacity);disc=Ellipse()
                self.halos.append((color,disc,radius,opacity))
            self.core_color=Color(1,1,1,1);self.core=Ellipse()
        self.update(0)

    def update(self,dt):
        if self.finished:return
        self.age+=min(dt,.15)
        progress=min(1,self.age/self.duration)
        x,y=self.map_widget.point(*route_point(self.points,progress))
        zoom=getattr(getattr(self.map_widget,'camera',None),'zoom',1)
        scale=max(.8,min(1.2,self.map_widget.width/1000))*zoom
        pulse=1+.07*math.sin(self.age*7)
        for color,disc,radius,opacity in self.halos:
            radius*=scale*pulse
            disc.size=(radius*2,radius*2);disc.pos=(x-radius,y-radius)
            color.a=opacity*(.94+.06*math.sin(self.age*7))
        radius=4.5*scale
        self.core.size=(radius*2,radius*2);self.core.pos=(x-radius,y-radius)
        if progress>=1:self.finish()

    def finish(self):
        if self.finished:return
        self.finished=True
        self.core_color.a=0
        for color,*_ in self.halos:color.a=0
        if self.parent:self.parent.remove_widget(self)
        self.done()

    def on_touch_down(self,touch):return False
