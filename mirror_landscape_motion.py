"""Localized river glints and falling foliage, driven by MirrorEffects' clock."""
import json
import math
from functools import lru_cache
from pathlib import Path
from kivy.core.image import Image as CoreImage
from kivy.graphics import (Color,Line,Rectangle,InstructionGroup,PushMatrix,PopMatrix,Rotate)

ROOT=Path(__file__).resolve().parent/'files/otherworld/themes'
WATER_COLORS={'north':(.72,.90,1),'elves':(.69,1,.96),'adepts':(.83,.94,1),
              'elines':(.90,1,.84),'vampires':(.76,.68,.95)}


@lru_cache(maxsize=5)
def landscape_data(key):
    path=ROOT/key/'ambience.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {'water':[],'leaves':[]}


def water_position(patch,age,offset):
    phase=(age*(.16 if patch['travel']<10 else .20)+offset)%1
    along=(phase-.5)*patch['travel']
    return (patch['x']+patch['dx']*along,patch['y']+patch['dy']*along,
            math.sin(math.pi*phase)**2)


def falling_leaf(anchor,age,index):
    phase=(age/(5.5+index%4)+index*.381966)%1
    return (anchor[0]+phase*17+math.sin(age*1.7+index)*5,
            anchor[1]-phase*62,phase,math.sin(math.pi*phase)**.7)


class LandscapeMotion:
    def __init__(self,map_widget,leaf_canvas,water_canvas,key):
        self.map=map_widget;self.key=key
        data=landscape_data(key)
        self.water=[];self.leaves=[]
        for i,patch in enumerate(data['water'][:28]):
            for shift in (0,.5):
                color=Color(*WATER_COLORS[key],0)
                line=Line(bezier=(0,0,0,0,0,0,0,0),bezier_precision=8,width=.7)
                water_canvas.add(color);water_canvas.add(line)
                self.water.append((patch,i*.618034+shift,color,line))
        anchors=data.get('leaves',())
        if anchors:
            source='yellow' if key=='adepts' else 'green'
            self.leaf_texture=CoreImage('files/status/icons/'+source+'_leaf.png',mipmap=True).texture
            for i in range(min(12,len(anchors))):
                group=InstructionGroup();leaf_canvas.add(group)
                group.add(PushMatrix());rotation=Rotate();group.add(rotation)
                color=Color(1,1,1,0);shape=Rectangle(texture=self.leaf_texture)
                group.add(color);group.add(shape);group.add(PopMatrix())
                self.leaves.append((anchors[i],color,shape,rotation))

    def update(self,age,scale):
        w=self.map
        for patch,offset,color,line in self.water:
            x,y,fade=water_position(patch,age,offset)
            dx,dy=patch['dx'],patch['dy']
            radius=patch.get('half_width',3)*(.65+.25*fade)
            bend=math.sin(age*1.4+offset)*.7
            points=[]
            for across,along in ((-radius,0),(-radius*.3,bend),(radius*.3,bend),(radius,0)):
                points.extend(w.point(x-dy*across+dx*along,y+dx*across+dy*along))
            line.bezier=points;line.width=max(.55,.8*scale)
            color.a=fade*(.42 if self.key=='north' else .52)
        for i,(anchor,color,shape,rotation) in enumerate(self.leaves):
            x,y,phase,fade=falling_leaf(anchor,age,i)
            x,y=w.point(x,y)
            size=(9+i%3*2)*max(.45,scale)
            width=size*(.35+.65*abs(math.sin(phase*math.pi*3+i)))
            shape.pos=(x-width/2,y-size/2);shape.size=(width,size)
            color.a=.85*fade
            rotation.origin=(x,y,0);rotation.angle=i*29+phase*165+math.sin(age+i)*18
