"""Small GPU town particles and construction feedback, with one disposable clock."""
import math

from kivy.clock import Clock
from kivy.graphics import (Color,InstructionGroup,Line,Rectangle,
                           StencilPush,StencilUse,StencilUnUse,StencilPop)
from mirror_effect_sprites import PaintedSprite
from town_art import theme_key

FLASH_DURATION=1.2


def construction_opacity(age):
    """Two brief dips, ending at full opacity without hiding the hit target."""
    if not 0<=age<FLASH_DURATION:return 1.
    return 1-.8*math.sin(2*math.pi*age/FLASH_DURATION)**2


# Chimney mouths in trimmed building art, bottom-origin UV coordinates.
# The abbey crystal workshop has no chimney; its bell tower must not smoke.
CHIMNEYS={
    'north':{'Фабрика':((.50,.69),(.64,.65)),'Кузница':((.59,.78),)},
    'elves':{'Фабрика':((.73,.77),(.82,.71)),'Кузница':((.65,.84),)},
    'vampires':{'Фабрика':((.56,.73),(.70,.70)),'Кузница':((.56,.83),)},
    'adepts':{'Кузница':((.59,.94),)},
    'elines':{'Фабрика':((.72,.78),),'Кузница':((.57,.73),)},
    'undead':{'Фабрика':((.54,.77),(.67,.70)),'Кузница':((.54,.90),)},
    'rebels':{'Фабрика':((.51,.77),(.66,.72)),'Кузница':((.63,.90),)},
    'neutral':{'Фабрика':((.52,.77),(.65,.70)),'Кузница':((.64,.81),)},
}


class TownEffects:
    def __init__(self,scene):
        self.scene=scene;self.age=0.;self._event=None;self._popup=None
        self.flashes={};self.chimneys=[];self.key=None;self._ancestors=[]
        self.group=InstructionGroup();scene.canvas.add(self.group)
        for instruction in (StencilPush(),Color(1,1,1,1)):
            self.group.add(instruction)
        self.mask=Rectangle();self.group.add(self.mask);self.group.add(StencilUse())
        self.smoke_layer=InstructionGroup();self.group.add(self.smoke_layer)
        self.weather_layer=InstructionGroup();self.group.add(self.weather_layer)
        self.group.add(StencilUnUse());self.group.add(Color(1,1,1,1))
        self.unmask=Rectangle();self.group.add(self.unmask)
        self.group.add(StencilPop())
        from map_atmosphere import MapAtmosphere
        mist=MapAtmosphere.mist_texture()
        self.smoke=[]
        for _ in range(24):
            color=Color(.44,.47,.50,0);rect=Rectangle(texture=mist)
            self.smoke_layer.add(color);self.smoke_layer.add(rect)
            self.smoke.append((color,rect))
        self._sync=Clock.create_trigger(self.sync_visibility,0)
        scene.bind(parent=self._parent_changed)
        self._sync()

    def _parent_changed(self,*_):
        self.stop();self._sync()

    def sync_visibility(self,*_):
        from kivy.uix.popup import Popup
        node=self.scene;popup=None;ancestors=[]
        while node is not None:
            if node is not self.scene:ancestors.append(node)
            if isinstance(node,Popup):popup=node;break
            node=node.parent
        for ancestor in self._ancestors:
            if ancestor not in ancestors:ancestor.unbind(parent=self._parent_changed)
        for ancestor in ancestors:
            if ancestor not in self._ancestors:ancestor.bind(parent=self._parent_changed)
        self._ancestors=ancestors
        if popup is not self._popup:
            if self._popup is not None:
                self._popup.unbind(on_open=self.sync_visibility,on_dismiss=self.stop)
            self._popup=popup
            if popup is not None:
                popup.bind(on_open=self.sync_visibility,on_dismiss=self.stop)
        active=self.key in ('north','elves','vampires','adepts') or self.chimneys or self.flashes
        if self.scene.get_root_window() is not None and active:
            if self._event is None:self._event=Clock.schedule_interval(self.update,1/30)
        else:self.stop()

    def stop(self,*_):
        if self._event is not None:self._event.cancel();self._event=None

    def flash(self,name):
        self.flashes[name]=0.
        self.sync_visibility()

    def opacity(self,name):return construction_opacity(self.flashes.get(name,-1))

    def layout(self):
        scene=self.scene;left,bottom,width,height=scene.scene_bounds
        x=max(scene.x,left);y=max(scene.y,bottom)
        self.bounds=(x,y,max(0,min(scene.right,left+width)-x),max(0,min(scene.top,bottom+height)-y))
        for mask in (self.mask,self.unmask):mask.pos=self.bounds[:2];mask.size=self.bounds[2:]
        key=theme_key(scene.faction)
        if key!=self.key:self.configure(key)
        self.chimneys=[]
        for name,anchors in CHIMNEYS.get(key,{}).items():
            rect=scene.sprites.get(name)
            if rect is not None:
                for u,v in anchors:
                    self.chimneys.append((name,rect.pos[0]+u*rect.size[0],
                                         rect.pos[1]+v*rect.size[1],rect.size[0]))
        self.flashes={name:age for name,age in self.flashes.items() if name in scene.sprites}
        self.update(0);self._sync()

    def configure(self,key):
        self.key=key;self.weather_layer.clear()
        self.particles=[];self.rain=[];self.bolt=None;self.glow=None
        count={'north':30,'elves':18,'vampires':6}.get(key,0)
        if self.scene.preview:count=max(0,int(count*.65))
        for _ in range(count):self.particles.append(PaintedSprite(self.weather_layer))
        if key=='adepts':
            for _ in range(26 if self.scene.preview else 42):
                color=Color(.68,.79,.88,.32);line=Line(width=.7)
                self.weather_layer.add(color);self.weather_layer.add(line)
                self.rain.append(line)
        if key=='elves':
            self.glow=Color(.72,.83,1,0);self.weather_layer.add(self.glow)
            self.sky_glow=Rectangle();self.weather_layer.add(self.sky_glow)
            self.bolt=PaintedSprite(self.weather_layer)

    def update(self,dt):
        if dt and self.scene.get_root_window() is None:
            self.stop();return
        self.age+=min(max(dt,0),.1)
        for name in list(self.flashes):
            self.flashes[name]+=min(max(dt,0),.1)
            if self.flashes[name]>=FLASH_DURATION:del self.flashes[name]
        for name,color in self.scene.sprite_colors.items():color.a=self.opacity(name)
        x,y,w,h=self.bounds
        if w<=0 or h<=0:return
        scale=max(.5,min(1.3,w/800));t=self.age
        for i,(color,rect) in enumerate(self.smoke):
            source=i//6
            if source>=len(self.chimneys):color.a=0;continue
            name,cx,cy,building_width=self.chimneys[source]
            phase=(t/(2.7+source*.21)+(i%6)/6)%1
            size=building_width*(.055+phase*.18)
            rect.pos=(cx+building_width*(.10*phase+.035*math.sin(t+i))-size/2,
                      cy+phase*building_width*.43-size*.15)
            rect.size=(size,size*1.3)
            color.a=math.sin(math.pi*phase)*.26*self.opacity(name)
        for i,sprite in enumerate(self.particles):
            if self.key=='north':
                u=(i*.618+t*.018+math.sin(t*.6+i)*.025)%1
                v=1-(i*.317+t*(.075+i%3*.012))%1
                size=(5+i%4)*scale
                sprite.draw('north',0,(x+u*w,y+v*h),(size,size),t*.7+i,.62,fps=3,angle=t*8+i*27)
            elif self.key=='elves':
                u=(i*.618+t*.026+math.sin(t*.7+i)*.04)%1
                v=1-(i*.283+t*(.055+i%3*.012))%1
                size=(12+i%4*2)*scale
                sprite.draw('elves',0,(x+u*w,y+v*h),(size,size*.8),t*.8+i,.65,fps=4,angle=t*24+i*31)
            else:
                u=(t*(.07+i*.009)+i*.173)%1
                v=.65+.18*math.sin(t*.9+i*1.8)
                size=(23+i%3*5)*scale
                sprite.draw('vampires',i%2,(x+u*w,y+v*h),(size,size*.75),t+i*.31,.8,fps=8,
                            angle=math.sin(t+i)*7)
        for i,line in enumerate(self.rain):
            u=(i*.618-t*.10)%1;v=1-(i*.271+t*(.8+i%3*.09))%1
            px,py=x+u*w,y+v*h
            line.points=(px,py,px-3*scale,py-11*scale)
        if self.bolt is not None:
            phase=(t+9)%13
            strength=max(0,math.sin(phase/.7*math.pi)) if phase<.7 else 0
            strength*=.65+.35*math.cos(phase*36)**2
            self.glow.a=strength*.055
            self.sky_glow.pos=(x,y+h*.48);self.sky_glow.size=(w,h*.52)
            cx=x+w*(.24 if int((t+9)//13)%2 else .76)
            self.bolt.draw('lightning-core',0,(cx,y+h*.78),(w*.11,h*.43),phase,
                           strength*.7,fps=5,loop=False)
        if not (self.flashes or self.chimneys or self.key in ('north','elves','vampires','adepts')):
            self.stop()
