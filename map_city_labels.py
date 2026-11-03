"""Resize only city-name glyphs; the map, roads and hit targets stay fixed."""


def label_scale(zoom):
    # Overview x1 -> name x1; map x1.5 -> name x1.3, with a smooth transition.
    zoom=max(1,min(1.5,zoom))
    return (1+(zoom-1)*.6)/zoom


class CityLabels:
    def __init__(self):
        self.labels=[]
        self.factor=None

    def add(self,center_x,top,size,rectangles):
        self.labels.append((center_x,top,tuple(size),rectangles))
        self.factor=None

    def apply(self,zoom):
        factor=label_scale(zoom)
        if factor==self.factor:
            return
        self.factor=factor
        for center_x,top,(width,height),rectangles in self.labels:
            w,h=width*factor,height*factor
            for rect,dx,dy in rectangles:
                rect.size=(w,h)
                rect.pos=(center_x-w/2+dx*factor,top-h+dy*factor)
