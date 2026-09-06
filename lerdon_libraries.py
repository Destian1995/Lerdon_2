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
