"""Shared overflow handling for legacy modal content, in logical Kivy pixels."""
from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.core.text.markup import MarkupLabel
from kivy.metrics import dp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.carousel import Carousel
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.textinput import TextInput
from kivy.uix.tabbedpanel import TabbedPanel


class ActionDock(BoxLayout):
    """Keep dialog actions visible while only the description/list scrolls."""
    def __init__(self, groups, **kwargs):
        super().__init__(orientation='vertical', size_hint_y=None, spacing=dp(6), **kwargs)
        self.groups = groups
        self.refresh = Clock.create_trigger(self._fit, -1)
        for group in groups:
            group.size_hint = (1, None)
            self.add_widget(group)
        self.bind(width=self.refresh, parent=self._parent_changed)
        self.refresh()

    def _parent_changed(self, *args):
        self.refresh() if self.parent else self.refresh.cancel()

    def _fit(self, *args):
        total = 0
        for group in self.groups:
            buttons = list(reversed(group.children)) if isinstance(group, BoxLayout) else [group]
            if not buttons:
                group.height = 0
                continue
            stacked = len(buttons) > 1 and self.width < dp(130) * len(buttons)
            if isinstance(group, BoxLayout):
                group.orientation = 'vertical' if stacked else 'horizontal'
                group.spacing = dp(6)
            for button in buttons:
                button.size_hint = (1, None) if stacked or group is button else (1, 1)
                button.height = dp(48)
                button.text_size = (max(1, self.width / (1 if stacked else len(buttons)) - dp(20)), dp(44))
                button.halign, button.valign = 'center', 'middle'
            padding = group.padding[1] + group.padding[3] if isinstance(group, BoxLayout) else 0
            group.height = padding + dp(48) * (len(buttons) if stacked else 1) + dp(6) * (len(buttons) - 1 if stacked else 0)
            total += group.height
        self.height = total + self.spacing * max(0, len(self.groups) - 1)


def detach_dialog_actions(content):
    """Extract terminal action rows, retaining the original widgets/callbacks."""
    from kivy.uix.spinner import Spinner
    from kivy.uix.togglebutton import ToggleButton
    def action(widget):
        return (isinstance(widget, ButtonBehavior) and isinstance(widget, Label)
                and not isinstance(widget, (Spinner, ToggleButton)))
    def row(widget):
        return (isinstance(widget, BoxLayout) and bool(widget.children)
                and all(action(child) for child in widget.children))
    body = content
    while (isinstance(body, ScrollView) or isinstance(body, BoxLayout) and len(body.children) == 1):
        if not body.children or action(body.children[0]):
            break
        body = body.children[0]
    if not isinstance(body, BoxLayout) or body.orientation != 'vertical':
        return []
    groups = []
    for child in list(body.children):  # Kivy stores the bottom item first.
        if action(child) or row(child):
            body.remove_widget(child)
            groups.insert(0, child)
        else:
            break
    return groups


class WindowFlow(ScrollView):
    """Give a dialog enough natural height, scrolling instead of squeezing it.

    Existing widget instances, callbacks and inner list scroll views are kept.
    Only plain horizontal button rows are allowed to change orientation.
    """
    def __init__(self, content, **kwargs):
        super().__init__(do_scroll_x=False, bar_width=dp(3), **kwargs)
        self.body = content
        self._busy = False
        self._observed = set()
        self._text_cache = {}
        self.refresh = Clock.create_trigger(self._refresh, -1)
        if content.parent:
            content.parent.remove_widget(content)
        content.size_hint = (1, None)
        self.add_widget(content)
        self.bind(size=self.refresh, parent=self._parent_changed)
        self.refresh()

    def _parent_changed(self, *args):
        if self.parent is None:
            self.refresh.cancel()
        else:
            self.refresh()

    def text_extent(self, widget, width=None):
        key = (widget.text, round(width, 1) if width is not None else None,
               widget.font_name, widget.font_size, widget.bold, widget.italic,
               widget.markup, widget.line_height)
        if key not in self._text_cache:
            factory = MarkupLabel if widget.markup else CoreLabel
            text = factory(text=widget.text or ' ', font_name=widget.font_name,
                           font_size=widget.font_size, bold=widget.bold,
                           italic=widget.italic, line_height=widget.line_height,
                           text_size=(width, None))
            text.refresh()
            if len(self._text_cache) > 512:
                self._text_cache.clear()
            self._text_cache[key] = text.texture.size
        return self._text_cache[key]

    def observe(self, widget):
        if widget in self._observed:
            return
        self._observed.add(widget)
        widget.bind(children=self.refresh, width=self.refresh, size_hint_min_y=self.refresh)
        if isinstance(widget, Label):
            widget.bind(text=self.refresh, font_size=self.refresh, font_name=self.refresh)
        widget._flow_fixed_height = widget.height if widget.size_hint_y is None else 0

    def measure(self, widget):
        self.observe(widget)
        if (widget is not self.body and widget.size_hint_y is None
                and hasattr(widget, '_flow_last_height')
                and abs(widget.height - widget._flow_last_height) > 0.5):
            widget._flow_fixed_height = widget.height
        if widget.opacity == 0 and (widget.height == 0 or widget.width == 0):
            return 0
        if getattr(widget, '_responsive_keep_geometry', False):
            return widget.height
        if isinstance(widget, Label):
            button = isinstance(widget, ButtonBehavior)
            inset = dp(20) if button else dp(4)
            _, height = self.text_extent(widget, max(dp(12), widget.width - inset))
            height += dp(12) if button else dp(6)
            height = max(dp(48) if button else dp(22), height)
            # Constrain text rendering to its own cell even before the next layout.
            widget.text_size = (max(1, widget.width - inset), max(1, widget.height - dp(4)))
            widget.valign = 'middle'
        elif isinstance(widget, TextInput):
            height = dp(48) if not widget.multiline else max(dp(96), widget._flow_fixed_height)
        elif isinstance(widget, Slider):
            height = dp(48)
        elif isinstance(widget, Image):
            height = widget._flow_fixed_height or (min(dp(48), widget.width) if widget.size_hint_x is None else dp(48))
        elif isinstance(widget, ScrollView):
            for child in list(widget.children):
                self.measure(child)
            # Inner lists retain their own viewport and scroll position.
            height = getattr(widget, '_responsive_min_height', dp(48))
        elif isinstance(widget, Carousel):
            height = dp(160)
        elif isinstance(widget, TabbedPanel):
            widget.tab_height = max(dp(48), widget.tab_height)
            for tab in widget.tab_list:
                if tab.content:
                    self.measure(tab.content)
            height = dp(220)
        elif isinstance(widget, (BoxLayout, GridLayout)):
            children = list(reversed(widget.children))
            if isinstance(widget, BoxLayout) and children:
                if not hasattr(widget, '_flow_orientation'):
                    widget._flow_orientation = widget.orientation
                actions = (widget._flow_orientation == 'horizontal' and len(children) > 1
                           and all(isinstance(c, ButtonBehavior) and isinstance(c, Label) for c in children))
                breakpoint = getattr(widget, '_responsive_stack_below', 0)
                if actions or breakpoint:
                    needed = breakpoint or sum(dp(48) if len(c.text.strip()) <= 2 else
                                 max(dp(64), min(dp(240), self.text_extent(c)[0] + dp(28))) for c in children)
                    stacked = needed + widget.spacing * (len(children) - 1) > widget.width
                    widget.orientation = 'vertical' if stacked else 'horizontal'
                    for child in children:
                        if not hasattr(child, '_flow_action_hints'):
                            child._flow_action_hints = tuple(child.size_hint)
                            child._flow_action_size = tuple(child.size)
                        if stacked and not getattr(child, '_flow_stack_active', False) and child._flow_action_hints[1] is not None:
                            child.height = 0
                            child._flow_fixed_height = 0
                            child._flow_last_height = 0
                        child.size_hint = (1, None) if stacked else child._flow_action_hints
                        child._flow_stack_active = stacked
                        if not stacked:
                            if child.size_hint_x is None:
                                child.width = child._flow_action_size[0]
                            if child.size_hint_y is None:
                                child.height = child._flow_action_size[1]
                if widget.orientation == 'horizontal' and not (actions or breakpoint):
                    fixed = [c for c in children if c.size_hint_x is None]
                    flexible = len(children) - len(fixed)
                    available = max(dp(1), widget.width - widget.padding[0] - widget.padding[2]
                                    - widget.spacing * max(0, len(children) - 1) - dp(48) * flexible)
                    for child in fixed:
                        if (not hasattr(child, '_flow_fixed_width') or
                                abs(child.width - getattr(child, '_flow_last_width', child.width)) > 0.5):
                            child._flow_fixed_width = child.width
                    total = sum(c._flow_fixed_width for c in fixed)
                    factor = min(1, available / total) if total else 1
                    for child in fixed:
                        child.width = child._flow_fixed_width * factor
                        child._flow_last_width = child.width
            heights = [self.measure(c) for c in children]
            left, top, right, bottom = widget.padding
            if isinstance(widget, BoxLayout):
                height = (sum(heights) + widget.spacing * max(0, len(heights) - 1)
                          if widget.orientation == 'vertical' else max(heights, default=0)) + top + bottom
            else:
                cols = widget.cols or max(1, (len(children) + (widget.rows or 1) - 1) // (widget.rows or 1))
                rows = [max(heights[i:i + cols], default=0) for i in range(0, len(heights), cols)]
                height = sum(rows) + widget.spacing[1] * max(0, len(rows) - 1) + top + bottom
        else:
            height = max(widget._flow_fixed_height, getattr(widget, '_responsive_min_height', 0))
        height = max(widget._flow_fixed_height, height)
        if widget is not self.body:
            if widget.size_hint_y is None:
                if abs(widget.height - height) > 0.5:
                    widget.height = height
                widget._flow_last_height = widget.height
            else:
                widget.size_hint_min_y = height
        return height

    def _refresh(self, dt):
        if self._busy:
            return
        self._busy = True
        try:
            if getattr(self.body, '_responsive_keep_geometry', False):
                # Fixed responsive layouts must shrink again after rotation;
                # their previous viewport height is not a content minimum.
                self.body.height = self.height
                return
            height = self.measure(self.body)
            self.body.height = max(self.height, height)
            # Removed cards should not be retained by the controller.
            current = set(self.body.walk())
            for widget in self._observed - current:
                widget.unbind(children=self.refresh, width=self.refresh, size_hint_min_y=self.refresh)
                if isinstance(widget, Label):
                    widget.unbind(text=self.refresh, font_size=self.refresh, font_name=self.refresh)
            self._observed.intersection_update(current)
        finally:
            self._busy = False


def fit_popup_to_window(popup):
    """Clamp explicit and proportional dialog sizes to the visible viewport."""
    from kivy.core.window import Window
    available = (max(dp(80), Window.width - dp(16)), max(dp(80), Window.height - dp(16)))
    interactive = any(isinstance(widget, (ButtonBehavior, TextInput, Slider)) for widget in popup.content.walk())
    for axis, extent in enumerate(available):
        prop = 'width' if axis == 0 else 'height'
        hint = popup.size_hint[axis]
        minimum = min(extent, dp(640 if axis == 0 else 240)) if interactive else 0
        if axis == 1 and getattr(popup, '_window_flow', None):
            flow = popup._window_flow
            natural = flow.measure(flow.body)
            wrapper = popup.content
            chrome = sum(w.height for w in wrapper.children if w is not flow)
            chrome += wrapper.padding[1] + wrapper.padding[3] + wrapper.spacing * max(0, len(wrapper.children) - 1)
            minimum = min(extent, max(minimum, natural + chrome))
        if hint is None:
            setattr(popup, prop, max(minimum, min(getattr(popup, prop), extent)))
        else:
            setattr(popup, 'size_hint_min_x' if axis == 0 else 'size_hint_min_y', minimum)
            setattr(popup, 'size_hint_max_x' if axis == 0 else 'size_hint_max_y', extent)
            setattr(popup, prop, max(minimum, min(extent, Window.size[axis] * hint)))
    from window_theme import center_after_resize
    center_after_resize(popup)


def make_action_dock(bar):
    """Keep bottom navigation touch-sized; overflow is horizontally scrollable."""
    from kivy.core.window import Window
    buttons = list(reversed(bar.children))
    bar.clear_widgets()
    scroll = ScrollView(do_scroll_x=True, do_scroll_y=False, bar_width=dp(2))
    row = BoxLayout(size_hint_x=None, spacing=dp(6))
    for button in buttons:
        button.size_hint_x = None
        row.add_widget(button)
    scroll.add_widget(row)
    bar.add_widget(scroll)

    def fit(dt=0):
        left = min(dp(200), max(dp(64), Window.width * 0.145))
        right = min(dp(106), Window.width * 0.15)
        bar.pos = (left, dp(4))
        bar.size = (max(dp(48), Window.width - left - right), dp(64))
        total = 0
        for button in buttons:
            label = CoreLabel(text=button.text, font_name=button.font_name, font_size=button.font_size,
                              bold=button.bold)
            label.refresh()
            button.width = max(dp(112), label.texture.width + dp(24))
            button.text_size = (button.width - dp(12), bar.height - dp(12))
            total += button.width
        row.width = max(scroll.width, total + row.spacing * max(0, len(buttons) - 1))

    refresh = Clock.create_trigger(fit, 0)
    def parent_changed(*args):
        Window.unbind(on_resize=refresh)
        if bar.parent:
            Window.bind(on_resize=refresh)
            refresh()
        else:
            refresh.cancel()
    bar.bind(parent=parent_changed)
    bar._responsive_dock = scroll
    refresh()
    return bar
