"""One continuous, clipped news ribbon; only visible text owns GPU textures."""
from collections import deque
import re
import textwrap

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.stencilview import StencilView
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from strategy_ui import surface, StrategyButton, text_label, INK, GOLD, TEXT
from utils.helpers import format_number

GOOD = (.34, .88, .49, 1)
BAD = (1, .36, .32, 1)
EVENT_COLORS = {'positive': GOOD, 'negative': BAD, 'mixed': GOLD}


def effect_kind(changes):
    positive = any(value > 0 for _, value in changes)
    negative = any(value < 0 for _, value in changes)
    return 'mixed' if positive and negative else 'positive' if positive else 'negative' if negative else 'neutral'


def text_chunks(text):
    # Each texture stays under mobile GPU limits. Chunks continue on the same
    # ribbon instead of reopening a notification for every few words.
    plain = re.sub(r'\[(?:/?b|/?i|/?color(?:=[^\]]+)?)\]', '', str(text))
    limit = max(16, int(1200 / max(1, sp(14))))
    return textwrap.wrap(' '.join(plain.split()), width=limit) or ['']


class EventTicker(BoxLayout):
    def __init__(self, description, kind, done, pending=None, **kwargs):
        super().__init__(size_hint=(None, None), height=dp(60), padding=dp(6), spacing=dp(6), **kwargs)
        self.done, self.closed, self.events = done, False, []
        self.pending = pending if pending is not None else deque()
        self.pending.appendleft((description, kind))
        self.segments = deque()
        self.offset = None
        surface(self, (*INK[:3], .96), GOLD)
        self.add_widget(text_label('ЛЕНТА', 10, GOLD, bold=True, size_hint_x=None, width=dp(44)))
        self.viewport = StencilView()
        self.add_widget(self.viewport)
        close = StrategyButton(text='×', size_hint_x=None, width=dp(48))
        close.bind(on_release=self.finish)
        self.add_widget(close)
        self.viewport.bind(pos=self.layout_text, size=self.layout_text)
        self.bind(parent=self.parent_changed)
        self.events.append(Clock.schedule_interval(self.advance, 1 / 30))

    def layout_text(self, *args):
        if self.closed or self.viewport.width <= 1:
            return
        if self.offset is None:
            self.offset = self.viewport.width
        edge = self.offset + sum(label.width for label in self.segments)
        while self.pending and (not self.segments or edge < self.viewport.width + dp(80)):
            text, kind = self.pending.popleft()
            label = Label(text=text, font_size=sp(14), color=EVENT_COLORS.get(kind, TEXT),
                          halign='left', valign='middle', size_hint=(None, None))
            label.texture_update()
            label.size = (max(1, label.texture_size[0]), self.viewport.height)
            self.segments.append(label)
            self.viewport.add_widget(label)
            edge += label.width
        x = self.viewport.x + self.offset
        for label in self.segments:
            label.pos = (x, self.viewport.y)
            label.height = self.viewport.height
            x += label.width

    def advance(self, dt):
        if self.closed:
            return False
        # Read consequences after closing the decision/report that covers them.
        if any(isinstance(widget, ModalView) for widget in Window.children):
            return
        self.layout_text()
        if self.offset is None:
            return
        self.offset -= dp(65) * min(dt, .1)
        while self.segments and self.offset + self.segments[0].width <= 0:
            label = self.segments.popleft()
            self.offset += label.width
            self.viewport.remove_widget(label)
        self.layout_text()
        if not self.segments and not self.pending:
            self.finish()

    def parent_changed(self, widget, parent):
        if parent is None:
            self.finish()

    def cancel(self):
        for event in self.events:
            event.cancel()
        self.events.clear()

    def finish(self, *args):
        if self.closed:
            return
        self.closed = True
        self.cancel()
        self.pending.clear()
        if self.parent:
            self.parent.remove_widget(self)
        self.done()


class EventQueue:
    def __init__(self, screen):
        self.screen, self.pending, self.active = screen, deque(), None
        screen.bind(size=self.fit, pos=self.fit, parent=self.parent_changed)

    def push(self, text, kind='neutral', changes=()):
        changes = tuple(changes)
        if changes:
            kind = effect_kind(changes)
        for index, part in enumerate(text_chunks(text)):
            self.pending.append((('   •   ' if index == 0 else ' ') + part, kind))
        for resource, value in changes:
            sign = '+' if value > 0 else '−' if value < 0 else ''
            summary = f' · {resource}: {sign}{format_number(abs(value))}'
            tone = effect_kind(((resource, value),))
            for part in text_chunks(summary):
                self.pending.append((' ' + part, tone))
        if self.active is None:
            self.next()
        else:
            self.active.layout_text()

    def next(self):
        if self.pending:
            text, kind = self.pending.popleft()
            self.active = EventTicker(text, kind, self.finished, pending=self.pending)
            self.screen.add_widget(self.active)
            self.fit()

    def finished(self):
        self.active = None

    def fit(self, *args):
        if self.active:
            left = getattr(getattr(self.screen, 'resource_box', None), 'width', dp(24)) + dp(12)
            right = dp(102)
            if self.screen.width - left - right < dp(260):
                left = right = dp(8)
            self.active.width = max(1, min(dp(960), self.screen.width - left - right))
            self.active.pos = (self.screen.x + left, self.screen.y + dp(78))

    def parent_changed(self, widget, parent):
        if parent is None:
            self.pending.clear()
            if self.active:
                self.active.finish()
