"""A transparent electric hemisphere, animated by the existing map clock."""
import math
import random
from kivy.graphics import InstructionGroup, Color, Mesh, Line
from map_terrain import city_sprite_size


class PortalDome:
    def __init__(self):
        self.group=InstructionGroup()
        self.fill_color=Color(.25,.37,1,.045)
        self.fill=Mesh(mode='triangle_fan')
        self.group.add(self.fill_color);self.group.add(self.fill)
        self.rims=[]
        for rgb,alpha,width in (((.32,.22,1),.12,5),((.25,.65,1),.35,2),((.65,.91,1),.8,.7)):
            color=Color(*rgb,alpha);line=Line(width=width)
            self.group.add(color);self.group.add(line)
            self.rims.append((color,line))
        self.ring_color=Color(.37,.68,1,.65)
        self.ring=Line(width=1)
        self.group.add(self.ring_color);self.group.add(self.ring)
        self.meridians=[]
        for _ in range(3):
            color=Color(.45,.58,1,.10);line=Line(width=.6)
            self.group.add(color);self.group.add(line)
            self.meridians.append((color,line))
        self.bolts=[]
        for i in range(9):
            halo_color=Color(.36,.68,1,0);halo=Line(width=.85)
            color=Color(.94,.99,1,0);line=Line(width=.30)
            branch=Line(width=.22)
            for instruction in (halo_color,halo,color,line,branch):self.group.add(instruction)
            self.bolts.append((halo_color,halo,color,line,branch))
        self.center=(0,0);self.radius=0;self.height=0
        self._bolt_profiles=[None]*len(self.bolts)

    @staticmethod
    def _ease(value):
        value=max(0.,min(1.,value))
        return value*value*(3-2*value)

    def _bolt_profile(self,index,tick):
        cached=self._bolt_profiles[index]
        if cached is None or cached[0]!=tick:
            rng=random.Random(701+index*1301+tick*7919)
            # Each flash starts at a new position, including between the poles.
            profile=(rng.uniform(0,math.tau),rng.uniform(.12,.85),
                     rng.uniform(.28,.65),rng.uniform(-1.4,1.4),
                     tuple(rng.uniform(-.025,.025) for _ in range(16)))
            cached=(tick,profile)
            self._bolt_profiles[index]=cached
        return cached[1]

    def update(self,center,scale,time):
        if center is None:
            self.fill.vertices=[];self.fill.indices=[]
            for _,line in self.rims+self.meridians:line.points=[]
            self.ring.points=[]
            for _,halo,_,line,branch in self.bolts:
                halo.points=[];line.points=[];branch.points=[]
            return
        size=city_sprite_size(scale)
        x,y=center
        base=y-size*.27
        radius=size*.77;height=size*1.05;depth=size*.23
        self.center=(x,base);self.radius=radius;self.height=height
        pulse=.5+.5*math.sin(time*1.8)
        arch=[(x+radius*math.cos(t*math.pi/48),base+height*math.sin(t*math.pi/48)) for t in range(49)]
        bottom=[(x+radius*math.cos(math.pi+t*math.pi/24),base+depth*math.sin(math.pi+t*math.pi/24)) for t in range(25)]
        contour=arch+bottom
        vertices=[x,base+height*.35,0,0]
        vertices.extend(v for point in contour+[contour[0]] for v in (*point,0,0))
        self.fill.vertices=vertices;self.fill.indices=list(range(len(vertices)//4))
        self.fill_color.a=.025+.018*pulse
        arch_points=[v for point in arch for v in point]
        for i,(color,line) in enumerate(self.rims):
            line.points=arch_points
            color.a=(.09,.24,.55)[i]+(.05,.12,.22)[i]*pulse
        self.ring.points=[v for i in range(65) for v in
                          (x+radius*math.cos(i*math.tau/64),base+depth*math.sin(i*math.tau/64))]
        self.ring_color.a=.35+.2*pulse
        for j,(color,line) in enumerate(self.meridians):
            longitude=(j-1)*.66
            line.points=[v for i in range(33) for v in
                (x+radius*longitude*math.sin(i*math.pi/32),
                 base+height*math.cos(i*math.pi/32)/2+height/2)]
            color.a=.055+.035*pulse
        for i,(halo_color,halo,color,line,branch) in enumerate(self.bolts):
            cycle=.18+.025*(i%4)
            phase=time/cycle+i*.391;tick=math.floor(phase)
            local=phase-tick
            longitude,start,span,sweep,jitters=self._bolt_profile(i,tick)
            # The old geometry hopped while fully lit. Now every new path is
            # introduced at zero opacity, then drifts continuously as it fades.
            life=local/.78
            flash=self._ease(life/.20)*self._ease((1-life)/.45)
            points=[]
            for step,jitter in enumerate(jitters):
                fraction=step/15
                angle=start+span*fraction
                arc=longitude+sweep*fraction+.12*local
                bend=.012*math.sin(local*math.tau+step*.9)
                points.extend((x+radius*(math.sin(angle)*math.cos(arc)+jitter+bend),
                    base+height*math.cos(angle)+depth*math.sin(angle)*math.sin(arc)+jitter*height*.4))
            halo.points=points;line.points=points
            bx,by=points[16:18]
            direction=1 if sweep>=0 else -1
            branch.points=[bx,by,bx+radius*.045*direction,by+height*.015,
                           bx+radius*.08*direction,by-height*.055]
            color.a=flash;halo_color.a=.5*flash
