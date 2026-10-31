"""Queued, clipped world events above the bottom navigation."""
from collections import deque
import re
import textwrap
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.stencilview import StencilView
from kivy.uix.label import Label
from strategy_ui import surface, StrategyButton, text_label, INK, GOLD, MUTED, TEXT
from ui_motion import enter


class EventTicker(BoxLayout):
    def __init__(self, description, kind, done, **kwargs):
        super().__init__(size_hint=(None, None), height=dp(64), padding=dp(8), spacing=dp(10), **kwargs)
        self.done, self.closed, self.events = done, False, []
        surface(self, (*INK[:3], 0.96), GOLD)
        badge = text_label('МИР', 11, GOLD, bold=True, size_hint_x=None, width=dp(44))
        self.add_widget(badge)
        self.viewport = StencilView()
        self.label = Label(text=description, markup=True, font_size=sp(14), color=TEXT,
                           halign='left', valign='middle', size_hint=(None, None))
        self.viewport.add_widget(self.label)
        self.add_widget(self.viewport)
        close = StrategyButton(text='×', size_hint_x=None, width=dp(48))
        close.bind(on_release=self.finish)
        self.add_widget(close)
        self.viewport.bind(pos=self.layout_text, size=self.layout_text)
        self.bind(parent=self.parent_changed)
        self.events.append(Clock.schedule_once(self.start_scroll, 0.8))
        enter(self)

    def layout_text(self, *args):
        self.label.text_size = (None, None)
        self.label.texture_update()
        self.label.size = (max(self.viewport.width, self.label.texture_size[0]), self.viewport.height)
        self.label.pos = self.viewport.pos

    def start_scroll(self, dt):
        if self.closed:
            return
        self.layout_text()
        distance = max(0, self.label.width - self.viewport.width)
        duration = max(3.5, distance / dp(75))
        if distance:
            Animation(x=self.viewport.x - distance, duration=duration, t='linear').start(self.label)
        self.events.append(Clock.schedule_once(self.finish, duration + 1.5))

    def parent_changed(self, widget, parent):
        if parent is None:
            self.cancel()

    def cancel(self):
        for event in self.events:
            event.cancel()
        self.events.clear()
        Animation.cancel_all(self.label)
        Animation.cancel_all(self)

    def finish(self, *args):
        if self.closed:
            return
        self.closed = True
        self.cancel()
        if self.parent:
            self.parent.remove_widget(self)
        self.done()


class EventQueue:
    def __init__(self, screen):
        self.screen, self.pending, self.active = screen, deque(), None
        screen.bind(size=self.fit, parent=self.parent_changed)

    def push(self, text, kind):
        # Bound texture width on dense Android screens; retain the full message.
        limit = max(20, int(1600 / max(1, sp(14))))
        if len(text) > limit:
            plain = re.sub(r'\[(?:/?b|/?i|/?color(?:=[^\]]+)?)\]', '', text)
            for part in textwrap.wrap(plain, width=limit):
                self.pending.append((part, kind))
        else:
            self.pending.append((text, kind))
        if self.active is None:
            self.next()

    def next(self):
        self.active = None
        if self.pending:
            text, kind = self.pending.popleft()
            self.active = EventTicker(text, kind, self.next)
            self.screen.add_widget(self.active)
            self.fit()

    def fit(self, *args):
        if self.active:
            left = getattr(getattr(self.screen, 'resource_box', None), 'width', dp(24)) + dp(12)
            right = dp(102)
            self.active.width = max(dp(180), min(dp(960), self.screen.width - left - right))
            self.active.pos = (self.screen.x + left, self.screen.y + dp(78))

    def parent_changed(self, widget, parent):
        if parent is None:
            self.pending.clear()
            if self.active:
                self.active.cancel()
                if self.active.parent:
                    self.active.parent.remove_widget(self.active)
                self.active = None
