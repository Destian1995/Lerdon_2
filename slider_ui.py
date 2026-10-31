"""Shared vector slider skin; retain Kivy's value/range/touch behavior."""
from kivy.graphics import Color, Ellipse, RoundedRectangle, InstructionGroup
from kivy.metrics import dp
from kivy.uix.slider import Slider
from strategy_ui import GOLD, MUTED


class SliderArt:
    def __init__(self, slider):
        self.slider = slider
        slider.background_width = 0
        slider.cursor_size = (0, 0)
        slider.value_track = False
        slider.padding = dp(20)
        self.group = InstructionGroup()
        self.back_color = Color(0.18, 0.23, 0.30, 1)
        self.track = RoundedRectangle(radius=[dp(4)])
        self.fill_color = Color(*GOLD)
        self.fill = RoundedRectangle(radius=[dp(4)])
        self.halo_color = Color(*GOLD[:3], 0.15)
        self.halo = Ellipse()
        self.knob_color = Color(*GOLD)
        self.knob = Ellipse()
        self.core_color = Color(0.96, 0.90, 0.72, 1)
        self.core = Ellipse()
        for item in (self.back_color, self.track, self.fill_color, self.fill, self.halo_color,
                     self.halo, self.knob_color, self.knob, self.core_color, self.core):
            self.group.add(item)
        slider.canvas.after.add(self.group)
        slider.bind(pos=self.draw, size=self.draw, value=self.draw, min=self.draw, max=self.draw, disabled=self.draw)
        self.draw()

    def draw(self, *args):
        w = self.slider
        if self.group not in w.canvas.after.children:
            w.canvas.after.add(self.group)
        length = max(1, w.width - 2 * w.padding)
        ratio = (w.value - w.min) / (w.max - w.min) if w.max != w.min else 0
        x, y = w.x + w.padding, w.center_y
        knob_x = x + length * ratio
        origin = x + length * (-w.min / (w.max - w.min)) if w.min < 0 < w.max else x
        self.track.pos, self.track.size = (x, y - dp(3)), (length, dp(6))
        self.fill.pos = (min(origin, knob_x), y - dp(3))
        self.fill.size = (max(1, abs(knob_x - origin)), dp(6))
        for shape, radius in ((self.halo, dp(18)), (self.knob, dp(11)), (self.core, dp(5))):
            shape.pos, shape.size = (knob_x - radius, y - radius), (radius * 2, radius * 2)
        alpha = 0.35 if w.disabled else 1
        self.fill_color.a = self.knob_color.a = self.core_color.a = alpha


def style_slider(slider):
    if not hasattr(slider, '_strategy_slider_art'):
        slider._strategy_slider_art = SliderArt(slider)
    return slider


class StrategySlider(Slider):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        style_slider(self)
