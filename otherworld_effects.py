"""A single, disposable clock for the Mirror Realm's magical map ambience."""
import math
from kivy.clock import Clock
from kivy.graphics import Color,Rectangle
from kivy.graphics.texture import Texture
from kivy.uix.widget import Widget

AMBIENT_ICON_SCALE=.35
SKY_EFFECT_SPOTS=((430,630),(470,520),(700,650),(970,540),(820,360),(360,370))
LIGHTNING_INTERVAL=1.9
SKY_EFFECT_INTERVAL=2.4


def mountain_anchors(terrain):
    """Use the authored mountain mask in map coordinates, including camera zoom."""
    if terrain:
        from map_terrain import MOUNTAIN,SNOW
        points=[((x+.5)*terrain.world_width/terrain.width,
                 (1-(y+.5)/terrain.height)*terrain.world_height)
                for y in range(terrain.height) for x in range(terrain.width)
                if terrain.grid[y*terrain.width+x] in (MOUNTAIN,SNOW)]
        if points:return points[::max(1,len(points)//40)][:40]
    return [(940,710),(1040,670),(1100,590),(820,720)]


def mist_texture():
    texture=Texture.create(size=(48,48),colorfmt='rgba')
    pixels=bytearray()
    for y in range(48):
        for x in range(48):
            radius=((x-23.5)/23.5)**2+((y-23.5)/23.5)**2
            pixels.extend((255,255,255,int(140*max(0,1-radius)**2)))
    texture.blit_buffer(bytes(pixels),colorfmt='rgba',bufferfmt='ubyte')
    return texture


def fog_front(anchor,age):
    """Shared wind displacement for a gently fading weather front."""
    phase=(age/24+.18)%1
    return (anchor[0]-170+340*phase,
            anchor[1]+math.sin(anchor[0]*.006+age*.17)*12,
            math.sin(math.pi*phase)**.6)


def lightning_envelope(phase):
    """A spreading cloud flash with two bright returns and a soft decay."""
    if not 0<=phase<1.25:return 0
    if phase<.12:return phase/.12*.85
    return min(.95,.85*math.exp(-(phase-.12)*3.8)+
               .42*math.exp(-((phase-.30)/.045)**2)+
               .27*math.exp(-((phase-.53)/.065)**2))


def lightning_glow_envelope(phase):
    """The fog lights up after the channel appears, and outlives its flash."""
    delay=.16
    if phase<=delay or phase>=1.8:return 0
    age=phase-delay
    return .8*(1-math.exp(-age*12))*math.exp(-age*2.6)


class MirrorEffects(Widget):
    def __init__(self,map_widget,**kwargs):
        super().__init__(**kwargs)
        self.map_widget=map_widget
        self._event=None;self.age=0
        from otherworld_themes import theme
        self.weather=theme(map_widget.owner.faction)['key']
        self.anchors=mountain_anchors(getattr(map_widget,'terrain',None))
        self.fog=[]
        fog_color={'vampires':(.52,.31,.72),'elves':(.24,.73,.35),
                   'north':(.72,.84,.94),'adepts':(.66,.65,.73),'elines':(.79,.57,.28)}[self.weather]
        self.mist=mist_texture()
        self.quest_glows=[];self.quest_targets=set();self._quest_refresh=-1
        with self.canvas.before:
            for city in map_widget.nodes:
                self.quest_glows.append((city,Color(1,.77,.25,0),Rectangle(texture=self.mist)))
        with self.canvas:
            for i in range(32):
                color=Color(*fog_color,.2)
                shape=Rectangle(texture=self.mist)
                self.fog.append((color,shape))
        self.storm_clouds=[];self.lightning_glow=[]
        if self.weather=='vampires':
            with self.canvas:
                for _ in SKY_EFFECT_SPOTS:
                    clouds=[];glow=[]
                    for _ in range(4):
                        clouds.append((Color(.40,.28,.55,.12),Rectangle(texture=self.mist)))
                    for _ in range(4):
                        glow.append((Color(.78,.68,1,0),Rectangle(texture=self.mist)))
                    self.storm_clouds.append(clouds);self.lightning_glow.append(glow)
        from mirror_effect_sprites import PaintedSprite
        self.snow=[PaintedSprite(self.canvas,scale=AMBIENT_ICON_SCALE) for _ in range(24)] if self.weather=='north' else []
        self.flair=[PaintedSprite(self.canvas,scale=AMBIENT_ICON_SCALE) for _ in range(16)]
        self.motes=[PaintedSprite(self.canvas,scale=AMBIENT_ICON_SCALE) for _ in range(12)]
        self.ripples=[PaintedSprite(self.canvas,scale=AMBIENT_ICON_SCALE) for _ in range(7)]
        self.runes=[PaintedSprite(self.canvas,scale=AMBIENT_ICON_SCALE) for _ in range(4)]
        self.gate=PaintedSprite(self.canvas,scale=AMBIENT_ICON_SCALE)
        self.party=PaintedSprite(self.canvas,scale=AMBIENT_ICON_SCALE)
        self.sky=PaintedSprite(self.canvas,scale=AMBIENT_ICON_SCALE)
        self.sky_effects=[self.sky]+[PaintedSprite(self.canvas,scale=AMBIENT_ICON_SCALE) for _ in SKY_EFFECT_SPOTS[1:]]
        self.lightning=[PaintedSprite(self.canvas) for _ in SKY_EFFECT_SPOTS] if self.weather=='vampires' else []
        from mirror_landscape_motion import LandscapeMotion
        water_layer=getattr(map_widget,'_water_layer',None)
        self.landscape=LandscapeMotion(map_widget,self.canvas,
            water_layer if water_layer is not None else self.canvas.before,self.weather)

    def start(self,*_):
        if self._event is None:self._event=Clock.schedule_interval(self.update,1/30)

    def stop(self,*_):
        if self._event:self._event.cancel();self._event=None

    def update(self,dt):
        self.age+=min(dt,.1)
        w=self.map_widget
        from turn_ui_guard import database_busy
        conn=getattr(w.owner,'conn',None)
        if self.age-self._quest_refresh>=.5 and conn is not None and not database_busy(conn):
            from otherworld_quests import objectives
            self.quest_targets=set(objectives(w.owner.conn,w.owner.faction))
            self._quest_refresh=self.age
        for city,color,shape in self.quest_glows:
            color.a=(.35+.25*math.sin(self.age*3)**2) if city['id'] in self.quest_targets else 0
            x,y=w.point(city['x'],city['y'])
            radius=max(28,105*min(w.width/1200,w.height/800)*w.camera.zoom)
            radius*=1+.08*math.sin(self.age*3)
            shape.pos=(x-radius,y-radius*.55);shape.size=(radius*2,radius*1.5)
        turn_progress=getattr(w.owner,'update_turn_progress',None)
        if turn_progress:turn_progress(dt)
        beam=getattr(w,'beam',None)
        if beam and not beam.finished:beam.update(dt)
        scale=min(w.width/1200,w.height/800)*w.camera.zoom
        for i,(color,shape) in enumerate(self.fog):
            dust=self.weather=='elines'
            ax,ay=self.anchors[i%len(self.anchors)]
            if dust:
                ax=(i*197+self.age*42)%1300-50
                ay=(i*113)%820
                fade=1
            else:
                ax,ay,fade=fog_front((ax,ay),self.age)
            x,y=w.point(ax,ay)
            width=(260 if dust else 180)*scale
            height=(105 if dust else 78)*scale
            shape.pos=(x-width/2,y-height/2);shape.size=(width,height)
            color.a=(.35+.12*math.sin(self.age*.4+i))*fade
        for i,sprite in enumerate(self.snow):
            ax,ay=self.anchors[i%len(self.anchors)]
            x,y=w.point(ax+((i*37+self.age*14)%150)-75,
                        ay+60-((i*29+self.age*32)%140))
            size=(9+i%4*2)*max(.65,scale)
            sprite.draw('north',0,(x,y),(size,size),self.age*.6+i,.48,fps=3,angle=self.age*9+i*17)
        for i,sprite in enumerate(self.lightning):
            phase=(self.age-i*LIGHTNING_INTERVAL)%(len(self.lightning)*LIGHTNING_INTERVAL)
            intensity=lightning_envelope(phase)
            x,y=w.point(*SKY_EFFECT_SPOTS[i])
            width=(96+i%3*8)*max(.8,scale)*AMBIENT_ICON_SCALE
            glow=lightning_glow_envelope(phase)
            for j,(cloud,light) in enumerate(zip(self.storm_clouds[i],self.lightning_glow[i])):
                cx=x+(-.3,-.1,.12,.32)[j]*width
                cy=y+math.sin(self.age*.16+j)*width*.05
                size=(width*.8,width*.55)
                pos=(cx-size[0]/2,cy-size[1]/2)
                cloud[1].pos=light[1].pos=pos;cloud[1].size=light[1].size=size
                cloud[0].a=.12+.025*math.sin(self.age*.2+j)
                light[0].a=glow
            sprite.draw('lightning-core',0,(x,y),(width,width*.85),
                        phase,intensity,fps=5,angle=-15+i*6,loop=False)
        for i,sprite in enumerate(self.motes):
            node=w.nodes[i%len(w.nodes)]
            phase=self.age*(.22+i%4*.04)+i*1.7
            x,y=w.point(node['x'],node['y'])
            radius=(28+i%5*8)*max(.6,scale)
            opacity=max(0,math.sin(phase*1.4))*.7
            size=(18+i%3*5)*max(.65,scale)
            sprite.draw(self.weather,1,(x+math.cos(phase)*radius,y+math.sin(phase*.7)*radius+20*scale),
                        (size,size),self.age+i*.31,opacity,fps=6)
        node=w.nodes[0];x,y=w.point(node['x'],node['y'])
        radius=max(23,45*scale)
        self.gate.draw(self.weather,2,(x,y),(radius*2.6,radius*1.25),self.age*.4,
                       .45+.15*math.sin(self.age*1.5),fps=3)
        current=next((c for c in w.nodes if c['id']==getattr(w,'_current_city',None)),None)
        if current:
            x,y=w.point(current['x'],current['y'])
            self.party.draw(self.weather,2,(x,y),(radius*2.8,radius*1.3),self.age*.5+1,
                            .6+.15*math.sin(self.age*2),fps=3)
        else:self.party.hide()
        self.update_life(w,scale)
        self.landscape.update(self.age,scale)

    def update_life(self,w,scale):
        t=self.age
        for i,sprite in enumerate(self.flair):
            node=w.nodes[i%len(w.nodes)]
            phase=(t*(.065+i%3*.012)+i*.173)%1
            ax=node['x']+math.sin(t*.23+i*2)*85
            ay=node['y']+45+phase*90
            if self.weather=='elines':
                ax=(i*173+t*48)%1300-50
                ay=120+(i*97)%570
            x,y=w.point(ax,ay)
            size=((56 if self.weather=='vampires' else 44)+i%3*9)*max(.8,scale)
            opacity=math.sin(phase*math.pi)*.85
            # Two bat designs alternate; the other factions use leaves, ice,
            # painted wisps and golden dust with independent animation phases.
            row=i%2 if self.weather=='vampires' else 0
            angle=math.sin(t*.7+i)*12 if self.weather=='vampires' else t*12+i*31
            sprite.draw(self.weather,row,(x,y),(size,size),t+i*.27,opacity,
                        fps=7 if self.weather=='vampires' else 4,angle=angle)
        for i,sprite in enumerate(self.ripples):
            node=w.nodes[i%len(w.nodes)]
            phase=(t*.12+i*.21)%1
            x,y=w.point(node['x'],node['y']-10)
            radius=(28+phase*38)*scale
            sprite.draw(self.weather,2,(x,y),(radius*2.6,radius*1.2),t*.4+i,
                        math.sin(math.pi*phase)*.28,fps=3)
        for i,sprite in enumerate(self.runes):
            ax,ay=self.anchors[(i*7)%len(self.anchors)]
            x,y=w.point(ax,ay)
            size=(38+5*math.sin(t+i))*max(.65,scale)
            sprite.draw(self.weather,2,(x,y),(size,size*.65),t*.4+i,
                        max(0,math.sin(t*.5+i))*.36,fps=3,angle=t*3)
        for i,sprite in enumerate(self.sky_effects):
            phase=(t-i*SKY_EFFECT_INTERVAL)%(len(self.sky_effects)*SKY_EFFECT_INTERVAL)
            opacity=math.sin(math.pi*phase/1.8)*.75 if phase<1.8 else 0
            ax,ay=SKY_EFFECT_SPOTS[i]
            drift=min(phase,1.8)
            center=w.point(ax-drift*18,ay-drift*6)
            size=max(.8,scale)
            sprite.draw(self.weather,3,center,(96*size,48*size),t*.6+i,
                        opacity,fps=3 if self.weather=='north' else 5)

    def on_touch_down(self,touch):return False
    def on_touch_move(self,touch):return False
    def on_touch_up(self,touch):return False
