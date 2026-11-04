"""Shared hold-and-drag gesture; ordinary taps, panning and pinches stay intact."""
import math
from kivy.clock import Clock
from kivy.graphics import Color, InstructionGroup, Line, Ellipse, Rectangle
from kivy.metrics import dp


class CityArmyDrag:
    def __init__(self, widget, pick, eligible, drop, coordinates=None, faction=None):
        self.widget, self.pick, self.eligible, self.drop = widget, pick, eligible, drop
        self.event = None
        self.coordinates = coordinates or (lambda pos: pos)
        self.faction = faction
        self.emblem_texture = None
        self.touch = None
        self.active = False
        self.hold_slop=dp(22)
        self.layer = InstructionGroup()
        widget.canvas.after.add(self.layer)

    def down(self, touch):
        self.cancel()
        source = self.pick(touch.pos)
        if source is None or not self.eligible(source):
            return
        self.touch, self.source, self.origin = touch, source, tuple(touch.pos)
        self.event = Clock.schedule_once(self.activate, .4)

    def activate(self, *_):
        self.event = None
        if self.touch is not None:
            if not self.eligible(self.source):
                self.cancel()
                return
            self.active = True
            if self.faction:
                from map_city_effects import faction_emblem
                self.emblem_texture = faction_emblem(self.faction())
            self.draw()

    def move(self, touch):
        if self.touch is not touch:
            return False
        if not self.active:
            if math.dist(self.origin, touch.pos) > self.hold_slop:
                self.cancel()
                return False
            # A held city owns small finger/mouse jitter until the hold fires.
            return True
        self.draw()
        return True

    def draw(self):
        self.layer.clear()
        x, y = self.coordinates(self.touch.pos)
        origin = self.coordinates(self.origin)
        self.layer.add(Color(.55, .9, 1, .8))
        self.layer.add(Line(points=[*origin, x, y], width=dp(1.5), dash_length=dp(6), dash_offset=dp(4)))
        self.layer.add(Color(.15, .65, 1, .22))
        self.layer.add(Ellipse(pos=(x-dp(32), y-dp(32)), size=(dp(64), dp(64))))
        self.layer.add(Color(.75, .95, 1, 1))
        self.layer.add(Line(circle=(x, y, dp(32)), width=dp(2)))
        if self.emblem_texture is not None:
            self.layer.add(Color(1, 1, 1, 1))
            width,height=self.emblem_texture.size
            scale=dp(48)/max(width,height)
            size=(width*scale,height*scale)
            self.layer.add(Rectangle(texture=self.emblem_texture,
                                     pos=(x-size[0]/2,y-size[1]/2),size=size))

    def up(self, touch):
        if self.touch is not touch:
            return False
        active, source = self.active, self.source
        target = self.pick(touch.pos) if active else None
        self.cancel()
        if active and target is not None and target != source:
            self.drop(source, target)
        return active

    def cancel(self, *_):
        if self.event is not None:
            self.event.cancel()
        self.event = self.touch = None
        self.active = False
        self.emblem_texture = None
        self.layer.clear()
