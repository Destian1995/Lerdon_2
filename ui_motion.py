"""Finite interface motion. No idle clocks and no geometry-changing effects."""
from kivy.animation import Animation
from kivy.event import EventDispatcher
from kivy.properties import NumericProperty

PRESS_TIME = 0.08
RELEASE_TIME = 0.16
ENTER_TIME = 0.22


class ButtonMotion(EventDispatcher):
    level = NumericProperty(0)

    def __init__(self, button, draw):
        super().__init__()
        self.button, self.draw = button, draw
        self.bind(level=lambda *_: draw(self.level))
        button.bind(state=self.change, disabled=self.change, parent=self.parent_changed)

    def change(self, *args):
        Animation.cancel_all(self)
        target = 1 if self.button.state == 'down' and not self.button.disabled else 0
        Animation(level=target, duration=PRESS_TIME if target else RELEASE_TIME, t='out_quad').start(self)

    def parent_changed(self, widget, parent):
        if parent is None:
            Animation.cancel_all(self)
            self.level = 0


def enter(widget):
    Animation.cancel_all(widget, 'opacity')
    widget.opacity = 0
    Animation(opacity=1, duration=ENTER_TIME, t='out_quad').start(widget)
    if not getattr(widget, '_enter_cleanup_bound', False):
        widget.bind(parent=lambda target, parent: Animation.cancel_all(target, 'opacity') if parent is None else None)
        widget._enter_cleanup_bound = True
