"""A bounded camera over the existing overview; never changes world geometry."""
import math


class MapCamera:
    minimum, maximum = 1.0, 1.5

    def __init__(self, viewport, rect):
        self.zoom = 1.0
        self.pan = (0.0, 0.0)
        self.viewport, self.rect = tuple(viewport), tuple(rect)

    @property
    def translation(self):
        return tuple((1-self.zoom)*extent/2+pan for extent,pan in zip(self.viewport,self.pan))

    def project(self, x, y):
        tx,ty = self.translation
        return x*self.zoom+tx,y*self.zoom+ty

    def unproject(self, x, y):
        tx,ty = self.translation
        return (x-tx)/self.zoom,(y-ty)/self.zoom

    def contains(self, x, y):
        if not (0 <= x <= self.viewport[0] and 0 <= y <= self.viewport[1]):
            return False
        x,y = self.unproject(x,y)
        left,bottom,width,height = self.rect
        return left <= x <= left+width and bottom <= y <= bottom+height

    def clamp(self):
        # An axis that still fits stays centered. A cropped axis can be panned
        # only far enough to reveal its edge, never past it into empty space.
        limits = [max(0,(size*self.zoom-extent)/2) for size,extent in zip(self.rect[2:],self.viewport)]
        self.pan = tuple(max(-limit,min(limit,pan)) for limit,pan in zip(limits,self.pan))

    def set_zoom(self, value, anchor=None):
        if not math.isfinite(value):
            return False
        value = max(self.minimum,min(self.maximum,value))
        anchor = anchor or (self.viewport[0]/2,self.viewport[1]/2)
        point = self.unproject(*anchor)
        changed = abs(value-self.zoom) > 1e-9
        self.zoom = value
        self.pan = tuple(a-extent/2-(p-extent/2)*value
                         for a,p,extent in zip(anchor,point,self.viewport))
        self.clamp()
        return changed

    def move(self, dx, dy):
        self.pan = (self.pan[0]+dx,self.pan[1]+dy)
        self.clamp()

    def configure(self, viewport, rect):
        ratio = rect[2]/self.rect[2] if self.rect[2] else 1
        self.pan = tuple(p*ratio for p in self.pan)
        self.viewport,self.rect = tuple(viewport),tuple(rect)
        self.clamp()

    def reset(self):
        self.zoom,self.pan = 1.0,(0.0,0.0)
