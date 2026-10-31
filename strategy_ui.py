"""Shared mobile strategy chrome and a responsive city inspection window."""
from kivy.core.window import Window
from kivy.graphics import Color, InstructionGroup, Line, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.properties import BooleanProperty

GOLD = (0.76, 0.60, 0.34, 1)
INK = (0.035, 0.052, 0.079, 1)
SURFACE = (0.065, 0.088, 0.125, 1)
TEXT = (0.92, 0.91, 0.85, 1)
MUTED = (0.56, 0.64, 0.72, 1)
FACTIONS = {'Север': (0.34, 0.65, 0.93, 1), 'Эльфы': (0.33, 0.74, 0.50, 1),
            'Вампиры': (0.72, 0.36, 0.62, 1), 'Адепты': (0.94, 0.61, 0.28, 1),
            'Элины': (0.90, 0.79, 0.35, 1), 'Нежить': (0.42, 0.71, 0.75, 1)}


class PanelFrame:
    """Stable vector frame, independent of a legacy widget's background redraw."""
    def __init__(self, widget, accent=GOLD, radius=10):
        self.widget, self.radius = widget, dp(radius)
        self.group = InstructionGroup()
        self.outer_color = Color(*accent[:3], 0.8)
        self.outer = Line(width=dp(1.0))
        self.inner_color = Color(0.58, 0.68, 0.79, 0.13)
        self.inner = Line(width=dp(0.8))
        self.corners_color = Color(*accent[:3], 0.95)
        self.corners = [Line(width=dp(1.4)) for _ in range(4)]
        for item in (self.outer_color, self.outer, self.inner_color, self.inner,
                     self.corners_color, *self.corners):
            self.group.add(item)
        widget.canvas.after.add(self.group)
        widget.bind(pos=self.update, size=self.update)
        self.update()

    def update(self, *args):
        if self.group not in self.widget.canvas.after.children:
            self.widget.canvas.after.add(self.group)
        x, y = self.widget.pos
        w, h = self.widget.size
        self.outer.rounded_rectangle = (x + 1, y + 1, max(0, w - 2), max(0, h - 2), self.radius)
        self.inner.rounded_rectangle = (x + dp(4), y + dp(4), max(0, w - dp(8)),
                                        max(0, h - dp(8)), max(0, self.radius - dp(3)))
        inset, length = dp(7), min(dp(15), w / 6, h / 6)
        for line, (cx, cy, sx, sy) in zip(self.corners, (
                (x + inset, y + inset, 1, 1), (x + w - inset, y + inset, -1, 1),
                (x + inset, y + h - inset, 1, -1), (x + w - inset, y + h - inset, -1, -1))):
            line.points = (cx, cy + length * sy, cx, cy, cx + length * sx, cy)


def frame(widget, accent=GOLD):
    if not hasattr(widget, '_strategy_frame'):
        widget._strategy_frame = PanelFrame(widget, accent)
    return widget


def surface(widget, color=SURFACE, accent=GOLD):
    with widget.canvas.before:
        Color(*color)
        shape = RoundedRectangle(pos=widget.pos, size=widget.size, radius=[dp(10)])
    def update(*args):
        shape.pos, shape.size = widget.pos, widget.size
    widget.bind(pos=update, size=update)
    return frame(widget, accent)


class StrategyButton(Button):
    selected = BooleanProperty(False)

    def __init__(self, accent=GOLD, primary=False, **kwargs):
        kwargs.setdefault('font_size', sp(24 if kwargs.get('text') in ('×', '✕', 'X') else 14))
        for key in ('background_normal', 'background_down', 'background_color', 'color', 'bold'):
            kwargs.pop(key, None)
        super().__init__(background_normal='', background_down='', background_color=(0, 0, 0, 0),
                         color=TEXT, bold=True, **kwargs)
        self.accent = accent
        self.base = ((0.22, 0.15, 0.075, 1) if primary else (0.075, 0.10, 0.145, 1))
        with self.canvas.before:
            self._fill = Color(*self.base)
            self._shape = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(9)])
        frame(self, accent)
        from ui_motion import ButtonMotion
        self._motion = ButtonMotion(self, self._feedback)
        self.bind(pos=self._layout, size=self._layout, disabled=self._state, selected=self._state)
        self._layout()

    def set_selected(self, value):
        self.selected = bool(value)

    def _feedback(self, level):
        amount = max(level, 0.35 if self.selected else 0)
        target = (*self.accent[:3], 0.34)
        self._fill.rgba = tuple(a + (b - a) * amount for a, b in zip(self.base, target))
        self._strategy_frame.outer_color.a = 0.95 if self.selected else 0.75 + level * 0.25

    def _layout(self, *args):
        self._shape.pos, self._shape.size = self.pos, self.size
        self.text_size = (max(1, self.width - dp(12)), max(1, self.height - dp(6)))
        self.halign, self.valign = 'center', 'middle'

    def _state(self, *args):
        self._feedback(self._motion.level)
        self.opacity = 0.45 if self.disabled else 1


def text_label(text, size=14, color=TEXT, **kwargs):
    label = Label(text=text, font_size=sp(size), color=color, halign='left', valign='middle', **kwargs)
    def resize(widget, value):
        widget.text_size = value
    label._strategy_text_sizer = resize
    label.bind(size=resize)
    return label


def section(title, icon, accent):
    panel = surface(BoxLayout(orientation='vertical', padding=dp(12), spacing=dp(8)), accent=accent)
    heading = BoxLayout(size_hint_y=None, height=dp(32), spacing=dp(9))
    heading.add_widget(Image(source=icon, size_hint=(None, 1), width=dp(28), mipmap=True))
    heading.add_widget(text_label(title, 16, bold=True))
    panel.add_widget(heading)
    panel._section_heading = heading
    return panel


class CityColumns(BoxLayout):
    """Two columns on landscape phones; tabs preserve space on narrow screens."""
    def __init__(self, left, right, accent, **kwargs):
        super().__init__(orientation='vertical', spacing=dp(10), **kwargs)
        self.panels = (left, right)
        self.selected = 0
        self._wide = None
        self.tabs = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.buttons = []
        for index, title in enumerate(('Гарнизон', 'Здания')):
            button = StrategyButton(text=title, accent=accent)
            button.bind(on_release=lambda widget, index=index: self.select(index))
            self.tabs.add_widget(button)
            self.buttons.append(button)
        self.body = BoxLayout(spacing=dp(10))
        self.bind(width=self._resize)
        self._resize()

    def _resize(self, *args):
        wide = self.width >= dp(650)
        if wide == self._wide:
            return
        self._wide = wide
        for panel in self.panels:
            panel._section_heading.height = dp(32) if wide else 0
            panel._section_heading.opacity = 1 if wide else 0
        self.clear_widgets()
        self.body.clear_widgets()
        self.body.orientation = 'horizontal'
        if wide:
            for panel in self.panels:
                self.body.add_widget(panel)
        else:
            self.add_widget(self.tabs)
            self.body.add_widget(self.panels[self.selected])
        self.add_widget(self.body)
        self._highlight()

    def select(self, index):
        self.selected = index
        if not self._wide:
            self.body.clear_widgets()
            self.body.add_widget(self.panels[index])
        self._highlight()

    def _highlight(self):
        for i, button in enumerate(self.buttons):
            button.color = GOLD if i == self.selected else MUTED


def build_city_window(popup):
    from city_war import read_city_war_states
    popup._strategy_custom_chrome = True
    accent = FACTIONS.get(popup.city_faction, GOLD)
    popup.title, popup.title_size, popup.separator_height = '', 0, 0
    popup.background = ''
    popup.background_color = (0, 0, 0, 0)
    popup.overlay_color = (0.01, 0.02, 0.04, 0.78)
    popup.padding = dp(4)
    # The window has its own header: remove Popup's blank title and fixed padding.
    chrome = popup._container.parent
    chrome.padding = 0
    for child in list(chrome.children):
        if child != popup._container:
            chrome.remove_widget(child)
    popup.size_hint = (None, None)
    popup.auto_dismiss = False
    popup._is_undead_city = bool(popup.conn.execute(
        'SELECT COALESCE(is_undead, 0) FROM cities WHERE name=?', (popup.city_name,)).fetchone()[0])
    root = surface(BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12)), INK, accent)
    popup.city_root = root
    header = BoxLayout(size_hint_y=None, height=dp(76), spacing=dp(12))
    state = read_city_war_states(popup.conn).get(popup.city_name)
    art = ('files/buildings/ruined/undead.png' if popup._is_undead_city else 'files/buildings/ruined/town.png') if state and state.ruined else (
        'files/buildings/castle_death.png' if popup._is_undead_city else 'files/buildings/default.png')
    portrait = surface(BoxLayout(size_hint=(None, 1), width=dp(76), padding=dp(5)), accent=accent)
    portrait.add_widget(Image(source=art, mipmap=True))
    header.add_widget(portrait)
    heading = BoxLayout(orientation='vertical', spacing=dp(1))
    heading.add_widget(text_label('ПОСЕЛЕНИЕ  /  ' + (popup.city_faction or 'Нейтрал'), 10, accent))
    heading.add_widget(text_label(popup.city_name, 24, bold=True))
    owned = popup.city_faction == popup.player_fraction
    status = ('Руины · идёт восстановление' if state.ready_turn is not None else 'Руины · отстройте 25 зданий') if state and state.ruined else (
        'Ваш город' if owned else 'Чужие владения' if popup.city_faction != 'Нейтрал' else 'Нейтральный город')
    heading.add_widget(text_label(status, 12, MUTED))
    header.add_widget(heading)
    close = StrategyButton(text='×', size_hint=(None, None), size=(dp(48), dp(48)),
                           pos_hint={'center_y': 0.5}, accent=accent)
    close.font_size = sp(24)
    close.bind(on_release=popup.dismiss)
    header.add_widget(close)
    root.add_widget(header)

    left = section('Гарнизон', 'files/status/army.png', accent)
    popup.attacking_units_list = ScrollView(do_scroll_x=False, bar_width=dp(3), scroll_type=['bars', 'content'])
    popup.attacking_units_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8))
    popup.attacking_units_box.bind(minimum_height=popup.attacking_units_box.setter('height'))
    popup.attacking_units_list.add_widget(popup.attacking_units_box)
    left.add_widget(popup.attacking_units_list)
    right = section('Проклятые земли' if popup._is_undead_city else 'Здания', 'files/status/icons/building.png', accent)
    if popup._is_undead_city:
        image = 'files/city/death/' + {'Некрополь': 'nekropolis', 'Горгум': 'gorgum', 'Морготар': 'morgotar'}.get(popup.city_name, 'city') + '.png'
        city_image = Image(source=image, mipmap=True)
        def open_lore(widget, touch):
            if widget.collide_point(*touch.pos):
                show_city_lore(popup, image)
                return True
            return False
        city_image.bind(on_touch_down=open_lore)
        right.add_widget(city_image)
        right.add_widget(text_label('Древняя крепость нежити', 12, MUTED, size_hint_y=None, height=dp(28)))
    else:
        count = popup.conn.execute('SELECT COALESCE(SUM(count),0) FROM buildings WHERE city_name=? AND faction=?',
                                   (popup.city_name, popup.city_faction)).fetchone()[0]
        popup.city_building_count = text_label(f'Застройка  {count} / 25', 12, GOLD, size_hint_y=None, height=dp(24))
        right.add_widget(popup.city_building_count)
        popup.buildings_list = ScrollView(do_scroll_x=False, bar_width=dp(3))
        popup.buildings_box = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(8))
        popup.buildings_box.bind(minimum_height=popup.buildings_box.setter('height'))
        popup.buildings_list.add_widget(popup.buildings_box)
        right.add_widget(popup.buildings_list)
    popup.city_columns = CityColumns(left, right, accent)
    if popup._is_undead_city:
        popup.city_columns.buttons[1].text = 'Проклятые земли'
    root.add_widget(popup.city_columns)
    actions = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(9))
    popup.city_action_buttons = {}
    def action(key, text, callback, primary=False):
        button = StrategyButton(text=text, accent=accent, primary=primary)
        button.bind(on_release=callback)
        popup.city_action_buttons[key] = button
        actions.add_widget(button)
    action('move', 'Ввести войска', lambda *_: popup.load_troops_by_type('Любые', None))
    if owned and not popup._is_undead_city:
        action('army', 'Разместить армию', popup.place_army)
        action('build', 'Построить', lambda *_: popup._open_build_menu(), True)
    root.add_widget(actions)
    popup.content = root
    popup.garrison_widgets = {}
    def fit(*args):
        width, height = args[1:3] if len(args) >= 3 else Window.size
        popup.size = (max(dp(1), min(dp(1040), width - dp(16))),
                      max(dp(1), min(dp(620), height - dp(16))))
        compact = height < dp(480)
        header.height = dp(64 if compact else 80)
        portrait.width = header.height
        root.padding = dp(12 if compact else 18)
        root.spacing = dp(8 if compact else 12)
        for panel in popup.city_columns.panels:
            panel.padding = dp(8 if compact else 12)
            panel.spacing = dp(6 if compact else 8)
            panel._section_heading.height = dp(28 if compact else 32) if popup.city_columns._wide else 0
        if hasattr(popup, 'city_building_count'):
            popup.city_building_count.height = dp(20 if compact else 24)
        from window_theme import center_after_resize
        center_after_resize(popup)
    popup._city_fit = fit
    Window.bind(on_resize=fit)
    popup.bind(on_dismiss=lambda *_: Window.unbind(on_resize=fit))
    fit()
    popup.get_garrison()
    popup.load_buildings()


BUILDING_ICONS = {'Больница': 'files/pict/hire/health.png', 'Фабрика': 'files/status/resource_box/workers.png',
                  'Стена': 'files/status/army.png', 'Рынок': 'files/status/economy.png',
                  'Кузница': 'files/pict/hire/sword.png', 'Вышка': 'files/status/icons/building.png'}


def building_row(name, count):
    row = surface(BoxLayout(size_hint_y=None, height=dp(50), padding=[dp(9), dp(5)], spacing=dp(10)),
                  (0.075, 0.098, 0.135, 1), (0.30, 0.37, 0.44, 1))
    row.add_widget(Image(source=BUILDING_ICONS.get(name, 'files/status/icons/building.png'),
                         size_hint=(None, 1), width=dp(34), mipmap=True))
    row.add_widget(text_label(name, 14))
    number = text_label(str(count), 17, GOLD, bold=True, size_hint=(None, 1), width=dp(42))
    number.halign = 'right'
    row.add_widget(number)
    return row


def bind_row_tap(widget, callback):
    """Open details on a tap release, leaving a finger drag to the ScrollView."""
    key = ('city-row', id(widget))
    def down(instance, touch):
        if instance.collide_point(*touch.pos) and not getattr(touch, 'is_mouse_scrolling', False):
            touch.ud[key] = touch.pos
        return False
    def up(instance, touch):
        start = touch.ud.pop(key, None)
        if start and instance.collide_point(*touch.pos):
            distance = (touch.pos[0] - start[0]) ** 2 + (touch.pos[1] - start[1]) ** 2
            if distance <= dp(10) ** 2:
                callback(instance, touch)
                return True
        return False
    widget.bind(on_touch_down=down, on_touch_up=up)


def decorate_hud(screen, **panels):
    from window_theme import theme_tree
    for name, panel in panels.items():
        frame(panel, FACTIONS.get(screen.selected_faction, GOLD) if name == 'faction' else GOLD)
        theme_tree(panel)
    for button in screen.tab_buttons.values():
        button.mipmap = True
    screen.season_icon.mipmap = True
    screen.faction_label.color = TEXT
    screen.turn_label.color = TEXT
    screen._hud_panels = panels
    def fit(*args):
        if getattr(screen, '_hud_fitting', False):
            return
        screen._hud_fitting = True
        try:
            width, height = args[1:3] if len(args) >= 3 else Window.size
            compact = width < dp(800)
            panels['resources'].width = dp(136 if compact else 156)
            panels['end_turn'].size = (panels['resources'].width, dp(60 if height < dp(480) else 72))
            panels['end_turn'].pos_hint = {'x': 0, 'top': 1 - (panels['resources'].height + dp(9)) / max(1, height)}
            panels['faction'].width = dp(110 if compact else 130)
            panels['turn'].width = dp(135 if compact else 185)
            panels['season'].width = dp(100 if compact else 120)
            panels['modes'].width = dp(76 if compact else 90)
            panels['modes'].spacing = dp(10 if compact else 16)
            panels['modes'].size_hint_y = None
            panels['modes'].height = (len(screen.tab_buttons) * dp(48 if compact else 60)
                                      + panels['modes'].spacing * (len(screen.tab_buttons) - 1)
                                      + panels['modes'].padding[1] + panels['modes'].padding[3])
            panels['exit'].padding = 0
            panels['exit'].height = dp(52)
            screen.faction_label.font_size = sp(16 if compact else 20)
            screen.turn_label.font_size = sp(14 if compact else 16)
            screen.end_turn_button.font_size = sp(15 if compact else 17)
            for button in screen.tab_buttons.values():
                button.height = dp(48 if compact else 60)
        finally:
            screen._hud_fitting = False
    screen._hud_fit = fit
    Window.bind(on_resize=fit)
    panels['resources'].bind(size=fit)
    fit()


def show_city_lore(city_popup, image):
    import json
    from kivy.uix.popup import Popup
    with open('files/city/death/lore.json', encoding='utf-8') as source:
        lore = json.load(source).get(city_popup.city_name, 'Проклятое место, где обитает нежить.')
    body = surface(BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(12)), INK)
    body.add_widget(Image(source=image, mipmap=True))
    scroll = ScrollView()
    label = text_label(lore, 14, size_hint_y=None)
    label.bind(width=lambda widget, value: setattr(widget, 'text_size', (value, None)),
               texture_size=lambda widget, value: setattr(widget, 'height', value[1]))
    scroll.add_widget(label)
    body.add_widget(scroll)
    close = StrategyButton(text='Закрыть', size_hint_y=None, height=dp(48))
    body.add_widget(close)
    popup = Popup(title=city_popup.city_name, content=body, size_hint=(0.90, 0.88),
                  title_color=GOLD, separator_color=GOLD, background='', background_color=INK)
    close.bind(on_release=popup.dismiss)
    popup.open()
