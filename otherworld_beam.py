"""Two endpoint portals teleport a party without drawing or following a route."""
import math
from kivy.graphics import Color,Ellipse,Line,Rectangle
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
        self.duration=1.6
        self.halos=[]
        self.portals=[]
        with self.canvas:
            for endpoint in (points[0],points[-1]):
                rings=[]
                for i in range(3):
                    color=Color(*accent[:3],0);ring=Line(width=1.2+i*.3)
                    rings.append((color,ring))
                glow=Color(*accent[:3],0);column=Rectangle()
                sparks=[]
                for i in range(12):
                    color=Color(1,1,1,0);spark=Ellipse()
                    sparks.append((color,spark))
                self.portals.append((endpoint,rings,glow,column,sparks))
            for radius,opacity in ((17,.02),(15,.03),(13,.045),(11,.065),(9,.10),(7,.17),(5.7,.32)):
                color=Color(1,1,1,opacity);disc=Ellipse()
                self.halos.append((color,disc,radius,opacity))
            self.core_color=Color(1,1,1,1);self.core=Ellipse()
        self.update(0)

    def update(self,dt):
        if self.finished:return
        self.age+=min(dt,.15)
        progress=min(1,self.age/self.duration)
        # The traveller vanishes here and reappears there; never crosses terrain.
        self.position=self.points[0] if progress<.5 else self.points[-1]
        x,y=self.map_widget.point(*self.position)
        zoom=getattr(getattr(self.map_widget,'camera',None),'zoom',1)
        scale=max(.8,min(1.2,self.map_widget.width/1000))*zoom
        for index,(endpoint,rings,glow,column,sparks) in enumerate(self.portals):
            local=max(0,min(1,(progress-index*.45)/.55))
            power=math.sin(math.pi*local)
            px,py=self.map_widget.point(*endpoint)
            radius=(22+15*math.sin(math.pi*local))*scale
            for j,(color,ring) in enumerate(rings):
                color.a=power*(.65-j*.12)
                r=radius*(1+j*.23)
                ring.points=[v for n in range(49) for v in
                             (px+r*math.cos(n*math.tau/48+self.age*2+j),
                              py+r*.45*math.sin(n*math.tau/48+self.age*2+j)+j*5*scale)]
            glow.a=power*.25
            column.pos=(px-4*scale,py);column.size=(8*scale,(40+40*power)*scale)
            for j,(color,spark) in enumerate(sparks):
                angle=j*math.tau/12+self.age*2.5
                lift=((local+j/12)%1)*65*scale
                r=radius*(.5+.25*math.sin(j*3+self.age*4))
                color.a=power*.8
                spark.size=(3*scale,3*scale)
                spark.pos=(px+math.cos(angle)*r,py+math.sin(angle)*r*.4+lift)
        pulse=1+.07*math.sin(self.age*7)
        envelope=math.sin(math.pi*min(1,progress/.5)) if progress<.5 else math.sin(math.pi*(progress-.5)/.5)
        for color,disc,radius,opacity in self.halos:
            radius*=scale*pulse
            disc.size=(radius*2,radius*2);disc.pos=(x-radius,y-radius)
            color.a=opacity*envelope*(.94+.06*math.sin(self.age*7))
        radius=4.5*scale*envelope
        self.core.size=(radius*2,radius*2);self.core.pos=(x-radius,y-radius)
        if progress>=1:self.finish()

    def finish(self):
        if self.finished:return
        self.finished=True
        self.core_color.a=0
        for color,*_ in self.halos:color.a=0
        for _,rings,glow,_,sparks in self.portals:
            glow.a=0
            for color,_ in rings+sparks:color.a=0
        if self.parent:self.parent.remove_widget(self)
        self.done()

    def on_touch_down(self,touch):return False
