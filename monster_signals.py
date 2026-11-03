"""Small pooled lightning strikes over lairs, on the existing atmosphere clock."""
import math
import random

from kivy.graphics import Color,InstructionGroup,Line,Rectangle

COLORS=((.78,.88,1),(.76,.48,1),(.38,1,.72),(.55,.78,1),
        (1,.58,.22),(.45,.88,1),(.85,.42,1))


class LairSignal:
    def __init__(self,site,texture):
        self.site=site
        self.group=InstructionGroup()
        self.rng=random.Random(site['id']*71+site['tier']*13+site.get('variant',1))
        self.wait=self.rng.uniform(.25,2.5)
        self.age=1
        rgb=COLORS[site['tier']-1]
        self.halo_color=Color(*rgb,0);self.group.add(self.halo_color)
        self.halo=Rectangle(texture=texture);self.group.add(self.halo)
        self.glow_color=Color(*rgb,0);self.group.add(self.glow_color)
        self.glow=Line(width=2.5);self.group.add(self.glow)
        self.core_color=Color(.96,.98,1,0);self.group.add(self.core_color)
        self.core=Line(width=.8);self.group.add(self.core)
        self.branch_color=Color(*rgb,0);self.group.add(self.branch_color)
        self.branch=Line(width=.75);self.group.add(self.branch)
        self.points=[(0,.56),(.08,.47),(-.02,.42),(.10,.34)]

    def update(self,dt,origin,scale,active):
        if not active:
            for color in (self.halo_color,self.glow_color,self.core_color,self.branch_color):color.a=0
            return
        self.wait-=dt
        self.age+=dt
        if self.wait<=0:
            self.wait=self.rng.uniform(2.6,4.5)
            self.age=0
            side=self.rng.choice((-1,1))
            self.points=[(side*(.22+self.rng.uniform(-.08,.08)),.59),
                         (side*.10,.49),(side*.24,.46),(side*.02,.32)]
        pulse=math.exp(-self.age/.045)
        if self.age>=.13:pulse+=.65*math.exp(-(self.age-.13)/.055)
        pulse=min(.9,pulse) if self.age<.45 else 0
        self.halo_color.a=pulse*.38
        self.glow_color.a=pulse*.32
        self.core_color.a=pulse*.95
        self.branch_color.a=pulse*.55
        x=origin[0]+self.site['x']*scale;y=origin[1]+self.site['y']*scale
        size=72*scale
        points=[v for u,w in self.points for v in (x+u*size,y+w*size)]
        self.glow.points=self.core.points=points
        self.glow.width=max(.6,2.5*scale);self.core.width=max(.45,.8*scale)
        self.branch.width=max(.4,.65*scale)
        self.branch.points=(points[2],points[3],points[2]+size*.12,points[3]-size*.03,
                            points[2]+size*.19,points[3]-size*.13)
        radius=(11+5*pulse)*scale
        self.halo.pos=(x-radius,y+size*.44-radius)
        self.halo.size=(radius*2,radius*2)


class MonsterSignals:
    def __init__(self,atmosphere):
        self.atmosphere=atmosphere
        self.group=InstructionGroup()
        self.signals={}
        self.turn=0
        self.signature=None

    def sync(self,sites,turn):
        self.turn=turn
        signature=tuple((s['id'],s['tier'],s.get('variant',1)) for s in sites)
        if signature!=self.signature:
            self.signature=signature
            self.group.clear()
            self.signals={site['id']:LairSignal(site,self.atmosphere.mist_texture()) for site in sites}
            for signal in self.signals.values():self.group.add(signal.group)
        for site in sites:self.signals[site['id']].site=site
        self.update(0)

    def update(self,dt):
        for signal in self.signals.values():
            signal.update(dt,self.atmosphere._origin,self.atmosphere._scale,
                          signal.site['ready_turn']<=self.turn)
