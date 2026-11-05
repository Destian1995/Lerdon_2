"""A layered, touchable town scene with real art for every constructed district."""
from functools import lru_cache
from pathlib import Path
from kivy.core.image import Image as CoreImage
from kivy.graphics import Color,Rectangle,Line,Mesh,Canvas
from kivy.metrics import dp
from kivy.uix.stencilview import StencilView
from town_art import panorama_path,building_path,building_mirrored,citadel_lot,LOTS,map_icon
from city_construction import building_counts


@lru_cache(maxsize=24)
def texture(path):return CoreImage(path,mipmap=True).texture


def mirrored_tex_coords(coords):
    """Swap texture corners without assuming that UVs span the whole buffer.

    Android may back a non-power-of-two image with a larger texture. In that
    case 1-u samples its transparent padding instead of mirroring the image.
    """
    return [coordinate for corner in (1,0,3,2)
            for coordinate in coords[corner*2:corner*2+2]]


@lru_cache(maxsize=48)
def building_shape(path):
    """Small alpha mask and closed contours; no extra generated image assets."""
    image=CoreImage(path,keep_data=True)
    columns=128;rows=max(16,round(columns*image.height/image.width))
    mask=tuple(tuple(image.read_pixel(min(image.width-1,int((x+.5)*image.width/columns)),
                         min(image.height-1,int((rows-y-.5)*image.height/rows)))[3]>.42
                     for x in range(columns)) for y in range(rows))
    edges={}
    def add(a,b):edges.setdefault(a,[]).append(b)
    for y,row in enumerate(mask):
        for x,opaque in enumerate(row):
            if not opaque:continue
            if not y or not mask[y-1][x]:add((x,y),(x+1,y))
            if x==columns-1 or not mask[y][x+1]:add((x+1,y),(x+1,y+1))
            if y==rows-1 or not mask[y+1][x]:add((x+1,y+1),(x,y+1))
            if not x or not mask[y][x-1]:add((x,y+1),(x,y))
    contours=[]
    while edges:
        start=next(iter(edges));point=start;points=[point]
        while point in edges:
            destinations=edges[point];following=destinations.pop()
            if not destinations:del edges[point]
            point=following;points.append(point)
            if point==start:break
        # Ignore isolated decorative pixels and small gaps in the sprite.
        if len(points)>16:
            ring=points[:-1] if points[-1]==points[0] else points
            smoothed=tuple(((ring[i-1][0]+2*x+ring[(i+1)%len(ring)][0])/(4*columns),
                            (ring[i-1][1]+2*y+ring[(i+1)%len(ring)][1])/(4*rows))
                           for i,(x,y) in enumerate(ring))
            contours.append(smoothed+(smoothed[0],))
    return mask,tuple(contours)


def shape_contains(path,u,v):
    mask,_=building_shape(path)
    if not 0<=u<1 or not 0<=v<1:return False
    return mask[min(len(mask)-1,int(v*len(mask)))][min(len(mask[0])-1,int(u*len(mask[0])))]


class TownScene(StencilView):
    def __init__(self,conn,city,faction,select=None,preview=False,**kwargs):
        super().__init__(**kwargs)
        self.paint=Canvas();self.canvas.add(self.paint)
        self.conn,self.city,self.faction=conn,city,faction
        self.select,self.preview=select,preview
        self.selected=None;self.counts={};self.hits=[];self._press=None
        self.lots=dict(LOTS)
        self.sprite_colors={};self._loaded=False
        self._responsive_keep_geometry=True
        from town_effects import TownEffects
        self.effects=TownEffects(self)
        self.bind(pos=self.draw,size=self.draw)
        self.refresh()

    def refresh(self,*_):
        from city_construction import city_owner
        previous=self.counts
        old_faction=self.faction
        self.faction=city_owner(self.conn,self.city) or self.faction
        self.counts=building_counts(self.conn,self.city,self.faction)
        if old_faction!=self.faction:self.effects.flashes.clear()
        self.draw()
        if self._loaded and old_faction==self.faction:
            for name,count in self.counts.items():
                if count and not previous.get(name,0):self.effects.flash(name)
        self._loaded=True

    def draw(self,*_):
        self.paint.clear();self.hits=[];self.sprites={};self.outlines={};self.plots={}
        self.sprite_colors={}
        if self.width<=0 or self.height<=0:
            self.scene_bounds=(self.x,self.y,0,0)
            self.effects.layout()
            return
        path=panorama_path(self.faction,self.city)
        # Used only while art is being generated, or for a damaged installation.
        if not Path(path).is_file():
            path=map_icon(self.faction)
        background=texture(path)
        # The inspection preview fills its frame; the interactive construction
        # scene keeps every district visible and reachable.
        fit = max if self.preview else min
        scale=fit(self.width/background.width,self.height/background.height)
        width,height=background.width*scale,background.height*scale
        left,bottom=self.x+(self.width-width)/2,self.y+(self.height-height)/2
        self.scene_bounds=(left,bottom,width,height)
        self.lots=dict(LOTS)
        citadel=building_path(self.faction,'Цитадель')
        if Path(citadel).is_file():
            art=texture(citadel)
            self.lots['Цитадель']=citadel_lot(self.faction,self.city,
                background.width/background.height,art.height/art.width)
        with self.paint:
            Color(.025,.035,.05,1);Rectangle(pos=self.pos,size=self.size)
            Color(1,1,1,1);Rectangle(texture=background,pos=(left,bottom),size=(width,height))
            for name,(u,v,relative_width) in sorted(self.lots.items(),key=lambda entry:-entry[1][1]):
                count=self.counts.get(name,0)
                x,y=left+u*width,bottom+v*height
                size=relative_width*width
                image=building_path(self.faction,name)
                art=texture(image) if count and Path(image).is_file() else None
                selected=name==self.selected
                if art:
                    h=size*art.height/art.width
                    fit=min(1,max(1,bottom+height*.98-y)/h)
                    size*=fit;h*=fit
                    self.sprite_colors[name]=Color(1,1,1,self.effects.opacity(name))
                    mirrored=building_mirrored(self.faction,name)
                    coords=list(art.tex_coords)
                    if mirrored:
                        coords=mirrored_tex_coords(coords)
                    self.sprites[name]=Rectangle(texture=art,pos=(x-size/2,y),size=(size,h),tex_coords=coords)
                    box=(x-size/2,y,size,h)
                    if selected and not self.preview:
                        _,contours=building_shape(image)
                        self.outlines[name]=contours
                        for alpha,thickness in ((.10,3),(.24,1.8),(.9,.7)):
                            Color(1,.84,.4,alpha)
                            for contour in contours:
                                Line(points=[coordinate for u,v in contour
                                     for coordinate in (x-size/2+(1-u if mirrored else u)*size,y+v*h)],width=dp(thickness))
                else:
                    box=(x-max(dp(22),size*.32),y-dp(8),max(dp(44),size*.64),max(dp(44),size*.45))
                    if not self.preview:
                        # Perspective ground footprint, with no icon obscuring the art.
                        points=(x-size*.43,y-size*.015,x-size*.26,y+size*.17,
                                x+size*.34,y+size*.17,x+size*.48,y-size*.015)
                        self.plots[name]=points
                        Color(1,.81,.32,.24 if selected else .08)
                        Mesh(vertices=[coordinate for i in range(0,8,2)
                             for coordinate in (points[i],points[i+1],0,0)],
                             indices=[0,1,2,3],mode='triangle_fan')
                        for alpha,thickness in ((.12,4),(.7 if selected else .28,1)):
                            Color(1,.83,.36,alpha)
                            Line(points=points,close=True,width=dp(thickness))
                self.hits.append((name,box))
        self.effects.layout()

    def on_touch_down(self,touch):
        if self.collide_point(*touch.pos) and not getattr(touch,'is_mouse_scrolling',False):
            self._press=(touch.uid,touch.pos);touch.grab(self);return True
        return super().on_touch_down(touch)

    def on_touch_up(self,touch):
        if self._press and self._press[0]==touch.uid:
            _,start=self._press;self._press=None;touch.ungrab(self)
            if self.collide_point(*touch.pos) and sum((a-b)**2 for a,b in zip(start,touch.pos))<dp(14)**2:
                if self.preview:
                    if self.select:self.select(None)
                else:
                    left,bottom,width,height=self.scene_bounds
                    nearby=[]
                    for name,(u,v,_) in self.lots.items():
                        distance=(touch.x-left-u*width)**2+(touch.y-bottom-v*height)**2
                        if distance<=dp(22)**2:nearby.append((distance,name))
                    name=next((n for n,(x,y,w,h) in reversed(self.hits)
                         if self.counts.get(n,0) and x<=touch.x<x+w and y<=touch.y<y+h
                         and shape_contains(building_path(self.faction,n),
                             1-(touch.x-x)/w if building_mirrored(self.faction,n) else (touch.x-x)/w,
                             (touch.y-y)/h)),None)
                    if name is None and nearby:name=min(nearby)[1]
                    if name:
                        self.selected=name;self.draw()
                        if self.select:self.select(name)
            return True
        return super().on_touch_up(touch)
