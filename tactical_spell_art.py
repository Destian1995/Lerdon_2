"""Lazy playback of hand-painted transparent VFX atlases. No combat rules here."""
import json
from pathlib import Path
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color,Rectangle

ROOT=Path(__file__).resolve().parent/'files/battlefields/effects'
SPELLS={'blood_vortex':'blood_vortex','whirlwind':'blade_whirlwind',
        'blizzard':'frost_storm','freeze':'frost_storm','flame':'flame','fire_shield':'flame',
        'heal':'healing','inspire':'inspiration','vampirism':'vampirism',
        'vampire_raise':'vampirism','dominate':'domination','blood':'blood_curse','drain':'life_drain'}


def effect_duration(key):
    return 1.2 if key in SPELLS and key!='blood_vortex' else .8


def vortex_positions(vortices,motions,age):
    """Retain the final movement even after the rules remove an expired vortex."""
    active={v['id']:v['pos'] for v in vortices};result=[]
    for key in dict.fromkeys([*active,*motions]):
        pos=active.get(key);alpha=1
        if key in motions:
            path,start=motions[key]
            if key not in active:
                if age>=start+.8:continue
                alpha=min(1,max(0,(start+.8-age)/.2))
            if path:
                pos=path[0]
                if len(path)>1:
                    t=max(0,min(1,(age-start)/.6))*(len(path)-1)
                    index=min(len(path)-2,int(t));fraction=min(1,t-index)
                    pos=tuple(path[index][axis]+(path[index+1][axis]-path[index][axis])*fraction for axis in (0,1))
        if pos is not None:result.append((key,pos,alpha))
    return result


class SpellArt:
    def __init__(self):
        self.index=json.loads((ROOT/'index.json').read_text(encoding='utf-8'))['effects']
        self.atlases={}

    def frame(self,key,age,loop=False):
        clip=self.index[key]
        if key not in self.atlases:
            atlas=CoreImage(str(ROOT/clip['image']),nocache=True).texture
            frames=[atlas.get_region(x,atlas.height-y-h,w,h) for x,y,w,h in clip['frames']]
            self.atlases[key]=(atlas,frames)
        frames=self.atlases[key][1]
        index=max(0,int(age*clip['fps']))
        index=index%len(frames) if loop else min(len(frames)-1,index)
        return frames[index]

    def draw(self,key,age,center,size,alpha=1,loop=False):
        texture=self.frame(key,age,loop)
        Color(1,1,1,max(0,min(1,alpha)))
        Rectangle(texture=texture,pos=(center[0]-size/2,center[1]-size/2),size=(size,size))

    def cast(self,ability,cells,age,cell_center,cell,impact=None):
        key=SPELLS.get(ability)
        if key is None:return False
        if ability=='blood_vortex':return True  # The moving world effect draws once below.
        duration=effect_duration(ability)
        if not 0<=age<duration:return True
        alpha=min(1,age/.10,(duration-age)/.20)
        if ability in ('flame','fire_shield','freeze','heal','inspire','vampirism','vampire_raise','dominate','blood','drain'):
            for pos in cells:
                self.draw(key,age,cell_center(pos),cell*1.8,alpha)
        elif cells:
            center=impact if impact is not None else tuple((min(p[i] for p in cells)+max(p[i] for p in cells))/2 for i in (0,1))
            self.draw(key,age,cell_center(center),cell*3.8,alpha)
        return True

    def clear(self):self.atlases.clear()
