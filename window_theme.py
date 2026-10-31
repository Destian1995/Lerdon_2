"""One opt-in widget skin and one shared Popup entry point for the whole game.

Keep widget instances and callbacks: styling must not change game decisions.
"""
import re
import os

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.graphics import Color, InstructionGroup, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner, SpinnerOption
from kivy.uix.textinput import TextInput

from strategy_ui import GOLD, INK, SURFACE, TEXT, MUTED, StrategyButton, frame

CLOSE_TEXT = {'закрыть', 'назад', 'закрыть окно', 'x', 'х', '×', '✕', '✖'}


def is_close_button(widget):
    return (getattr(widget, '_strategy_close', False) or
            isinstance(widget, ButtonBehavior) and
            (getattr(widget, 'text', '') or '').strip().lower() in CLOSE_TEXT)


def has_close_button(root):
    return any(is_close_button(widget) for widget in root.walk())


class Fill:
    """A reusable backing over a legacy background, never over its text/art."""
    def __init__(self, widget, color):
        self.widget = widget
        self.group = InstructionGroup()
        self.color = Color(*color)
        self.shape = RoundedRectangle(radius=[dp(9)])
        self.group.add(self.color)
        self.group.add(self.shape)
        widget.bind(pos=self.update, size=self.update)
        self.update()

    def update(self, *args):
        before = self.widget.canvas.before
        if self.group not in before.children:
            before.add(self.group)
        self.shape.pos, self.shape.size = self.widget.pos, self.widget.size


def skin_button(button):
    if isinstance(button, StrategyButton) or hasattr(button, '_window_button_skin'):
        return
    # Empty transparent buttons are hit regions over cards/portraits, not surfaces.
    if (not getattr(button, 'text', '').strip() and
            getattr(button, 'background_color', (0, 0, 0, 1))[3] == 0):
        button._strategy_hit_region = True
        return
    fill = Fill(button, SURFACE)
    button._window_button_skin = fill
    if is_close_button(button) and len((getattr(button, 'text', '') or '').strip()) == 1:
        button.text = '×'
        button.font_size = sp(24)
    frame(button)
    button.color = TEXT
    button.halign, button.valign = 'center', 'middle'
    if hasattr(button, 'background_normal'):
        def has_image():
            source = button.background_normal
            return bool(source and os.path.isfile(source))
        if not has_image():
            button.background_normal = button.background_down = ''
        def transparent(widget, value):
            desired = (1, 1, 1, 1) if has_image() else (0, 0, 0, 0)
            if tuple(widget.background_color) != desired:
                widget.background_color = desired
            fill.color.a = 0 if has_image() else 1
        button.bind(background_color=transparent)
        button.bind(background_normal=transparent)
        transparent(button, button.background_color)
    if hasattr(button, 'md_bg_color'):
        button.md_bg_color = SURFACE
        button.theme_text_color = 'Custom'
        button.text_color = TEXT
    def state(*args):
        selected = getattr(button, 'state', 'normal') == 'down'
        disabled = getattr(button, 'disabled', False)
        fill.color.rgba = ((0.23, 0.17, 0.09, 1) if selected else SURFACE)
        if hasattr(button, 'background_normal') and button.background_normal and os.path.isfile(button.background_normal):
            fill.color.a = 0
        button._strategy_frame.outer_color.a = 0.25 if disabled else 0.85
        fill.update()
    button.bind(state=state, disabled=state)
    from ui_motion import ButtonMotion
    def feedback(level):
        if hasattr(button, 'background_normal') and button.background_normal and os.path.isfile(button.background_normal):
            return
        fill.color.rgba = tuple(a + (b - a) * level for a, b in zip(SURFACE, (0.24, 0.18, 0.10, 1)))
        button._strategy_frame.outer_color.a = 0.25 if button.disabled else 0.75 + level * 0.25
    button._strategy_motion = ButtonMotion(button, feedback)
    state()


def _has_art(widget):
    for instruction in widget.canvas.before.children:
        if isinstance(instruction, Rectangle) and getattr(instruction, 'texture', None):
            if max(instruction.texture.size) > 4:
                return True
    return False


def skin_panel(widget):
    if getattr(widget, '_strategy_no_theme', False):
        return
    if hasattr(widget, '_window_panel_skin') or hasattr(widget, '_strategy_frame'):
        return
    if hasattr(widget, 'md_bg_color'):
        widget.md_bg_color = INK
    # Preserve illustrated backdrops and portraits; only replace solid fills.
    if not _has_art(widget):
        widget._window_panel_skin = Fill(widget, INK)
    frame(widget)


def _neutral_text(label):
    rgb = label.color[:3]
    if min(rgb) > 0.78 and max(rgb) - min(rgb) < 0.16 or max(rgb) < 0.3:
        label.color = TEXT
        if hasattr(label, 'theme_text_color') and hasattr(label, 'text_color'):
            label.theme_text_color = 'Custom'
            label.text_color = TEXT
    if label.markup:
        def lighten(match):
            rgb = [int(match.group(1)[i:i + 2], 16) / 255 for i in (0, 2, 4)]
            return '#B9C5D1' if max(rgb) < 0.5 and max(rgb) - min(rgb) < 0.16 else match.group(0)
        label.text = re.sub(r'(?<=\[color=)#([0-9a-fA-F]{6})(?=\])', lighten, label.text)


class StrategySpinnerOption(SpinnerOption):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.height = dp(48)
        skin_button(self)


def theme_tree(root, observe=True):
    """Also used for non-Popup panels; dynamic children receive the same skin."""
    if root is None:
        return
    skin_panel(root)
    trigger = getattr(root, '_window_theme_trigger', None)
    if observe and trigger is None:
        trigger = Clock.create_trigger(lambda dt: theme_tree(root), -1)
        root._window_theme_trigger = trigger
    for widget in list(root.walk()):
        if isinstance(widget, ButtonBehavior) and hasattr(widget, 'text'):
            skin_button(widget)
        elif isinstance(widget, Image):
            from portrait_ui import style_portrait_image
            style_portrait_image(widget)
        elif isinstance(widget, Label):
            _neutral_text(widget)
        elif isinstance(widget, TextInput):
            widget.background_normal = widget.background_active = ''
            widget.background_color = SURFACE
            widget.foreground_color, widget.cursor_color = TEXT, GOLD
            widget.selection_color = (0.76, 0.60, 0.34, 0.35)
            frame(widget, (0.34, 0.42, 0.51, 1))
        elif isinstance(widget, Slider):
            from slider_ui import style_slider
            style_slider(widget)
        elif isinstance(widget, ScrollView):
            widget.bar_color = GOLD
            widget.bar_inactive_color = (0.35, 0.42, 0.50, 0.25)
        elif isinstance(widget, BoxLayout) and widget.canvas.before.children:
            skin_panel(widget)
        if isinstance(widget, Spinner) and widget.option_cls is not StrategySpinnerOption:
            widget.option_cls = StrategySpinnerOption
        if trigger is not None and hasattr(widget, 'children') and not getattr(widget, '_window_theme_observed', False):
            widget.bind(children=lambda *args, trigger=trigger: trigger())
            widget._window_theme_observed = True


def _remove_native_header(popup):
    chrome = popup._container.parent
    chrome.padding = 0
    for child in list(chrome.children):
        if child != popup._container:
            chrome.remove_widget(child)


def prepare_custom_popup(popup):
    popup._strategy_custom_chrome = True
    _remove_native_header(popup)


def center_after_resize(popup):
    """SDL may update Window.center after on_resize; center on the next frame."""
    if popup.parent is None:
        return
    pending = getattr(popup, '_strategy_center_event', None)
    if pending:
        pending.cancel()
    def centered(dt):
        popup._strategy_center_event = None
        if popup.parent:
            popup.center = Window.center
    popup._strategy_center_event = Clock.schedule_once(centered, 0)
    if not getattr(popup, '_strategy_center_bound', False):
        def cancel_center(*args):
            event = getattr(popup, '_strategy_center_event', None)
            if event:
                event.cancel()
                popup._strategy_center_event = None
        popup.bind(on_dismiss=cancel_center)
        popup._strategy_center_bound = True


def watch_game_area(area):
    def style_children(*args):
        for child in list(area.children):
            if not getattr(child, '_strategy_no_theme', False):
                theme_tree(child)
    area.bind(children=style_children)
    style_children()


def theme_popup(popup):
    if getattr(popup, '_window_theme_busy', False) or popup.content is None:
        return
    popup._window_theme_busy = True
    try:
        popup.background = ''
        popup.background_color = INK
        popup.overlay_color = (0.01, 0.02, 0.04, 0.78)
        popup._anim_duration = 0.18
        if getattr(popup, '_strategy_custom_chrome', False):
            if getattr(popup.content, '_strategy_fixed_layout', False):
                theme_tree(popup.content)
                return
            # Keep the custom header; apply the same overflow rules to its body.
            from responsive_ui import WindowFlow
            if not isinstance(popup.content, WindowFlow):
                popup._window_flow = WindowFlow(popup.content)
                popup.content = popup._window_flow
                popup.bind(on_open=lambda *_: popup._window_flow.refresh(),
                           on_dismiss=lambda *_: popup._window_flow.refresh.cancel())
            return
        if not getattr(popup.content, '_window_theme_wrapper', False):
            content = popup.content
            existing_close = has_close_button(content)
            has_actions = any(isinstance(w, ButtonBehavior) for w in content.walk())
            caption = popup.title
            _remove_native_header(popup)
            wrapper = BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(10))
            wrapper._window_theme_wrapper = True
            can_close = has_actions or popup.auto_dismiss and bool(caption)
            if caption or can_close and not existing_close:
                header = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
                title = Label(text=caption, color=GOLD, font_size=sp(17), bold=True,
                              halign='left', valign='middle')
                title.bind(size=lambda widget, value: setattr(widget, 'text_size', value))
                header.add_widget(title)
                popup._window_theme_title = title
                if not existing_close and can_close:
                    close = StrategyButton(text='×', size_hint=(None, 1), width=dp(48))
                    close._strategy_close = True
                    close.bind(on_release=popup.dismiss)
                    header.add_widget(close)
                wrapper.add_widget(header)
            if content.parent:
                content.parent.remove_widget(content)
            content.size_hint = (1, 1)
            from responsive_ui import WindowFlow, ActionDock, detach_dialog_actions
            groups = detach_dialog_actions(content)
            flow = WindowFlow(content)
            popup._window_flow = flow
            wrapper.add_widget(flow)
            if groups:
                popup._window_action_dock = ActionDock(groups)
                wrapper.add_widget(popup._window_action_dock)
            popup.content = wrapper
            popup._window_theme_original_content = content
        theme_tree(popup.content)
        if not getattr(popup, '_window_fit_bound', False):
            from responsive_ui import fit_popup_to_window
            fit_trigger = Clock.create_trigger(lambda dt: fit_popup_to_window(popup), 0)
            def fit(*args):
                fit_trigger()
            def released(*args):
                Window.unbind(on_resize=fit)
                fit_trigger.cancel()
                flow = getattr(popup, '_window_flow', None)
                if flow:
                    flow.refresh.cancel()
            def opened(*args):
                Window.bind(on_resize=fit)
                fit()
                flow = getattr(popup, '_window_flow', None)
                if flow:
                    flow.refresh()
            popup.bind(on_open=opened, on_dismiss=released)
            popup._window_fit_bound = True
            fit()
        if not getattr(popup, '_window_theme_content_bound', False):
            popup.bind(content=lambda widget, value: theme_popup(widget))
            popup._window_theme_content_bound = True
    finally:
        popup._window_theme_busy = False


def install_window_theme():
    """Called once by lerdon_libraries; covers imported aliases/subclasses too."""
    if getattr(Popup.open, '_lerdon_strategy_theme', False):
        return
    original = Popup.open
    def open_themed(popup, *args, **kwargs):
        if not getattr(popup, '_strategy_custom_chrome', False) and not getattr(popup, '_window_theme_content_bound', False):
            popup.bind(content=lambda widget, value: theme_popup(widget))
            popup._window_theme_content_bound = True
            def caption_changed(widget, value):
                label = getattr(widget, '_window_theme_title', None)
                if label:
                    label.text = value
            popup.bind(title=caption_changed)
        theme_popup(popup)
        return original(popup, *args, **kwargs)
    open_themed._lerdon_strategy_theme = True
    Popup.open = open_themed
