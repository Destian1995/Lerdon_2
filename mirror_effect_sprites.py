"""Painted atlas clips blended on the GPU, without per-particle timers/files."""
import math
from functools import lru_cache
from pathlib import Path
from kivy.core.image import Image as CoreImage
from kivy.graphics import InstructionGroup, Color, Rectangle, PushMatrix, PopMatrix, Rotate

ASSET_ROOT=Path(__file__).resolve().parent/'files'/'otherworld'/'effects'


def animation_frame(age,fps=7,count=4,loop=True):
    phase=max(0,age)*fps
    if not loop:
        phase=min(phase,count-1)
        index=int(phase)
        return index,min(index+1,count-1),phase-index
    index=int(phase)
    return index%count,(index+1)%count,phase-index


def blend_opacities(opacity,mix):
    """Two ordinary alpha passes maintain opacity throughout the crossfade."""
    opacity=max(0,min(1,opacity));mix=max(0,min(1,mix))
    over=opacity*mix
    under=opacity*(1-mix)/max(1e-8,1-over)
    return under,over


@lru_cache(maxsize=7)
def atlas_texture(key):
    return CoreImage(str(ASSET_ROOT/(key+'.png')),mipmap=True).texture


@lru_cache(maxsize=24)
def animation_clip(key,row=0):
    texture=atlas_texture(key)
    cols,rows=(2,2) if key in ('lightning','lightning-core') else (4,4)
    if key in ('lightning','lightning-core'):
        cells=[(i%2,i//2) for i in range(4)]
    else:cells=[(i,row) for i in range(4)]
    frames=[]
    for col,r in cells:
        left,right=round(col*texture.width/cols),round((col+1)*texture.width/cols)
        bottom,top=round((rows-r-1)*texture.height/rows),round((rows-r)*texture.height/rows)
        frames.append(texture.get_region(left,bottom,right-left,top-bottom))
    return tuple(frames)


class PaintedSprite:
    def __init__(self,canvas,scale=1):
        self.scale=scale
        self.group=InstructionGroup();canvas.add(self.group)
        self.group.add(PushMatrix())
        self.rotation=Rotate()
        self.group.add(self.rotation)
        self.layers=[]
        for _ in range(2):
            color=Color(1,1,1,0);rect=Rectangle()
            self.group.add(color);self.group.add(rect);self.layers.append((color,rect))
        self.group.add(PopMatrix())
        self.clip=None;self.frame=(0,1,0)

    def draw(self,key,row,center,size,age,opacity=1,fps=7,angle=0,loop=True):
        clip=animation_clip(key,row)
        first,second,mix=animation_frame(age,fps,len(clip),loop=loop)
        self.frame=first,second,mix
        self.clip=key,row
        self.rotation.origin=(*center,0);self.rotation.angle=angle
        x,y=center;width,height=(v*self.scale for v in size)
        for (color,rect),frame,alpha in zip(self.layers,(first,second),blend_opacities(opacity,mix)):
            rect.texture=clip[frame]
            rect.pos=(x-width/2,y-height/2);rect.size=(width,height)
            color.rgba=(1,1,1,alpha)

    def hide(self):
        for color,_ in self.layers:color.a=0
