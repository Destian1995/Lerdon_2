"""Brief, map-bound fog and light when a marching army enters a waypoint."""
import math
from kivy.graphics import Color, InstructionGroup, Line, Rectangle
from terrain_placement import FEATURE_SIZE


def reaches_site(start, end, center, radius):
    dx,dy=end[0]-start[0],end[1]-start[1]
    length=dx*dx+dy*dy
    t=max(0,min(1,((center[0]-start[0])*dx+(center[1]-start[1])*dy)/length)) if length else 0
    return math.hypot(start[0]+dx*t-center[0],start[1]+dy*t-center[1])<=radius


class TerrainArrivalEffects:
    """A bounded pool on the march clock; all positions stay in world space."""
    duration=1.15

    def __init__(self,atmosphere):
        self.atmosphere=atmosphere
        self.group=InstructionGroup()
        self.sites={}
        self.pulses=[]
        for _ in range(12):
            glow=Color(1,1,1,0);halo=Rectangle(texture=atmosphere.mist_texture())
            edge=Color(1,1,1,0);ring=Line(width=1.2)
            for instruction in (glow,halo,edge,ring):self.group.add(instruction)
            fog=[]
            for i in range(5):
                color=Color(1,1,1,0);shape=Rectangle(texture=atmosphere.mist_texture())
                self.group.add(color);self.group.add(shape);fog.append((color,shape))
            self.pulses.append(dict(age=self.duration,site=None,glow=glow,halo=halo,edge=edge,ring=ring,fog=fog))

    def set_sites(self,sites):
        self.sites={site['id']:dict(site) for site in sites if site['kind'] in ('forest','swamp')}

    def enter(self,site):
        pulse=next((p for p in self.pulses if p['age']<self.duration and p['site']['id']==site['id']),None)
        pulse=pulse or next((p for p in self.pulses if p['age']>=self.duration),None)
        if pulse is None:pulse=max(self.pulses,key=lambda p:p['age'])
        pulse.update(age=0,site=dict(site))

    def update(self,dt):
        a=self.atmosphere;scale=a._scale
        for p in self.pulses:
            p['age']=min(self.duration,p['age']+dt)
            u=p['age']/self.duration
            strength=math.sin(math.pi*u)**.7 if u<1 else 0
            if p['site'] is None:continue
            site=self.sites.get(p['site']['id'],p['site'])
            x=a._origin[0]+site['x']*scale
            y=a._origin[1]+(site['y']+FEATURE_SIZE*.12)*scale
            rgb=(.39,.86,.62) if site['kind']=='forest' else (.66,.80,.46)
            width=FEATURE_SIZE*(1.05+.5*u)*scale
            p['glow'].rgba=(*rgb,strength*.55)
            p['halo'].pos=(x-width*.6,y-width*.45);p['halo'].size=(width*1.2,width*.9)
            p['edge'].rgba=(*rgb,strength*.35)
            p['ring'].ellipse=(x-width*.42,y-width*.3,width*.84,width*.6)
            for i,(color,shape) in enumerate(p['fog']):
                phase=i*2.4
                px=x+math.cos(phase)*(10+u*14)*scale
                py=y+math.sin(phase)*8*scale+u*10*scale
                w=(38+u*28)*scale
                color.rgba=(.72,.86,.79,strength*.46)
                shape.pos=(px-w/2,py-w*.25);shape.size=(w,w*.5)

    def clear(self):
        for p in self.pulses:p['age']=self.duration
        self.update(0)
