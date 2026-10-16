# ============================================================
# Централизованные импорты для проекта Lerdon Legends
# Используется через: from lerdon_libraries import *
# ============================================================

# --- Стандартная библиотека ---
import ast
import heapq
import itertools
import json
import logging
import math
import os
import random
import re
import shutil
import sqlite3
import threading
import time
import unicodedata
import webbrowser
from collections import defaultdict, deque
from datetime import datetime, timedelta

# --- Kivy: Core ---
from kivy import platform
from kivy.animation import Animation, AnimationTransition
from kivy.app import App
from kivy.clock import Clock
from kivy.config import Config
from kivy.core.image import Image as CoreImage
from kivy.core.text import Label as CoreLabel
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.metrics import dp, sp
from kivy.resources import resource_find
from kivy.utils import get_color_from_hex, platform
from kivy.vector import Vector

# --- Kivy: Properties ---
from kivy.properties import (
    BooleanProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
    partial,
)

# --- Kivy: Graphics ---
from kivy.graphics import (
    Color,
    Ellipse,
    InstructionGroup,
    Line,
    Mesh,
    PopMatrix,
    PushMatrix,
    Rectangle,
    Rotate,
    RoundedRectangle,
    Translate,
    Triangle,
)

# --- Kivy: UIX Widgets ---
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.carousel import Carousel
from kivy.uix.dropdown import DropDown
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.popup import Popup
from kivy.uix.progressbar import ProgressBar
from kivy.uix.screenmanager import FadeTransition, Screen, ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from kivy.uix.spinner import Spinner
from kivy.uix.stencilview import StencilView
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelHeader, TabbedPanelItem
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton, ToggleButtonBehavior
from kivy.uix.video import Video
from kivy.uix.widget import Widget
from kivy.uix.image import AsyncImage

# --- KivyMD ---
from kivymd.app import MDApp
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDFlatButton
from kivymd.uix.floatlayout import MDFloatLayout
from kivymd.uix.label import MDLabel
from kivymd.uix.selectioncontrol import MDCheckbox


# ── Универсальная кнопка закрытия «✕» для всех Popup ──────────────────
def _has_buttons(widget):
    """Возвращает True если в дереве виджетов есть хотя бы одна кнопка Button."""
    if isinstance(widget, Button):
        return True
    for child in getattr(widget, 'children', []):
        if _has_buttons(child):
            return True
    return False


def _has_close_button(widget):
    """Возвращает True если в дереве есть кнопка с текстом 'Закрыть' или 'Назад'."""
    if isinstance(widget, Button):
        t = (widget.text or '').strip().lower()
        if t in ('закрыть', 'назад', 'закрыть окно'):
            return True
    for child in getattr(widget, 'children', []):
        if _has_close_button(child):
            return True
    return False


def _inject_close_x(popup_instance):
    """Оборачивает content попапа в FloatLayout и добавляет кнопку ✕
    в правый верхний угол. Вызывается автоматически при popup.open().
    X добавляется только если в контенте есть кнопки, но нет кнопки Закрыть."""
    content = popup_instance.content
    if content is None:
        return
    # Не оборачивать повторно
    if getattr(popup_instance, '_close_x_injected', False):
        return
    # Добавлять X только если в контенте есть кнопки
    if not _has_buttons(content):
        return
    # Не добавлять X если уже есть кнопка «Закрыть» / «Назад»
    if _has_close_button(content):
        return
    popup_instance._close_x_injected = True

    wrapper = FloatLayout()
    # Отвязываем content от popup, чтобы можно было добавить в wrapper
    if content.parent is not None:
        content.parent.remove_widget(content)
    content.size_hint = (1, 1)
    content.pos_hint = {'x': 0, 'y': 0}
    wrapper.add_widget(content)

    _sz = dp(38)
    btn = Button(
        text='X', size_hint=(None, None),
        size=(_sz, _sz),
        pos_hint={'right': 1, 'top': 1},
        background_color=(0, 0, 0, 0),
        color=(1, 1, 1, 1),
        font_size=sp(22), bold=True,
    )
    with btn.canvas.before:
        btn._xc = Color(0.55, 0.14, 0.14, 0.95)
        btn._xe = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(6)])
    btn.bind(
        pos=lambda i, v: setattr(i._xe, 'pos', v),
        size=lambda i, v: setattr(i._xe, 'size', v),
    )
    btn.bind(on_release=lambda *_a: popup_instance.dismiss())
    wrapper.add_widget(btn)

    popup_instance.content = wrapper


_original_popup_open = Popup.open


def _patched_popup_open(self, *args, **kwargs):
    _inject_close_x(self)
    return _original_popup_open(self, *args, **kwargs)


Popup.open = _patched_popup_open
