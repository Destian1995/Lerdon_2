"""The shared visual language for the front end and persistent game navigation."""
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, RoundedRectangle
from kivy.metrics import dp, sp
from kivy.properties import NumericProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.image import Image
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.core.text import Label as CoreLabel

from strategy_ui import INK, SURFACE, GOLD, TEXT, MUTED, FACTIONS, StrategyButton, surface, text_label
from responsive_ui import WindowFlow
from ui_motion import enter

VERSION = '7.0.4'
FACTION_ART = {'Север': 'people', 'Эльфы': 'elfs', 'Вампиры': 'vampire', 'Адепты': 'adepts', 'Элины': 'elins'}


class MenuButton(StrategyButton):
    """Compatibility with the old menu button API, using shared chrome/motion."""
    glow_intensity = NumericProperty(0)

    def __init__(self, button_type='default', **kwargs):
        self.button_type = button_type
        super().__init__(primary=button_type == 'start', **kwargs)

    def update_canvas(self, *args):
        self.set_selected(self.glow_intensity > 0)


class FactionChoice(StrategyButton):
    _DEFAULT_COLOR = SURFACE

    def __init__(self, **kwargs):
        self._choice_font = kwargs.get('font_size', sp(14))
        super().__init__(accent=FACTIONS.get(kwargs.get('text'), GOLD), **kwargs)
        self.bind(width=self.fit_caption)
        self.fit_caption()

    def fit_caption(self, *args):
        text = CoreLabel(text=self.text, font_size=self._choice_font, font_name=self.font_name, bold=True)
        text.refresh()
        available = max(1, self.width - dp(22))
        self.font_size = max(sp(10), min(self._choice_font, self._choice_font * available / max(1, text.texture.width)))
        self.shorten = True


class Meter(Widget):
    value = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas:
            Color(*SURFACE)
            self.back = RoundedRectangle(radius=[dp(4)])
            Color(*GOLD)
            self.fill = RoundedRectangle(radius=[dp(4)])
        self.bind(pos=self.draw, size=self.draw, value=self.draw)
        self.draw()

    def draw(self, *args):
        self.back.pos, self.back.size = self.pos, self.size
        self.fill.pos = self.pos
        self.fill.size = (max(0, self.width * min(1, max(0, self.value))), self.height)


class NaturalList(BoxLayout):
    """Content-driven list; rows never inherit the viewport's spare height."""
    def __init__(self, **kwargs):
        kwargs.setdefault('orientation', 'vertical')
        kwargs.setdefault('size_hint_y', None)
        super().__init__(**kwargs)
        self.bind(minimum_height=self.setter('height'))

    def add_widget(self, widget, *args, **kwargs):
        if isinstance(widget, Label) and not isinstance(widget, Button):
            if hasattr(widget, '_strategy_text_sizer'):
                widget.unbind(size=widget._strategy_text_sizer)
            base = widget.height if widget.size_hint_y is None else dp(22)
            widget.size_hint_y = None
            def wrap(*args):
                widget.text_size = (max(1, widget.width - dp(4)), None)
            widget.bind(width=wrap, texture_size=lambda w, value: setattr(w, 'height', max(base, value[1] + dp(4))))
            wrap()
        super().add_widget(widget, *args, **kwargs)


class CampaignColumns(BoxLayout):
    def __init__(self, factions, settings, **kwargs):
        super().__init__(orientation='vertical', spacing=dp(8), **kwargs)
        self.panels, self.selected, self._wide = [], 0, None
        for content in (factions, settings):
            scroll = ScrollView(do_scroll_x=False, bar_width=dp(3), bar_color=GOLD)
            scroll.add_widget(content)
            self.panels.append(scroll)
        self.body = BoxLayout(spacing=dp(24))
        self.tabs = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        for index, caption in enumerate(('Фракция', 'Настройки')):
            button = StrategyButton(text=caption)
            button.bind(on_release=lambda widget, index=index: self.select(index))
            self.tabs.add_widget(button)
        self.bind(width=self.arrange)

    def arrange(self, *args):
        wide = self.width >= dp(440)
        if wide == self._wide:
            return
        self._wide = wide
        self.clear_widgets()
        self.body.clear_widgets()
        for panel in self.panels:
            if panel.parent:
                panel.parent.remove_widget(panel)
        if wide:
            self.panels[0].size_hint_x, self.panels[1].size_hint_x = 0.37, 0.63
            for panel in self.panels:
                self.body.add_widget(panel)
        else:
            self.add_widget(self.tabs)
            self.panels[self.selected].size_hint_x = 1
            self.body.add_widget(self.panels[self.selected])
        self.add_widget(self.body)

    def select(self, index):
        self.selected = index
        self._wide = None
        self.arrange()


class FrontPage(FloatLayout):
    """Full viewport artwork, readable content surface, one responsive flow."""
    def __init__(self, owner, title, subtitle='', art='files/menu/choise/vampire.jpg', paged=False, **kwargs):
        super().__init__(**kwargs)
        self.paged = paged
        self.art = Image(source=art, fit_mode='cover')
        self.add_widget(self.art)
        shade = Widget()
        with shade.canvas:
            Color(*INK[:3], 0.12 if paged else 0.64)
            rect = Rectangle(pos=shade.pos, size=shade.size)
        shade.bind(pos=lambda w, v: setattr(rect, 'pos', v), size=lambda w, v: setattr(rect, 'size', v))
        self.add_widget(shade)
        self.column = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(8)) if paged else surface(
            NaturalList(padding=dp(16), spacing=dp(12)), (*INK[:3], 0.94))
        header = BoxLayout(orientation='vertical', size_hint_y=None, height=dp(70), spacing=dp(4))
        header.add_widget(text_label('LERDON  /  ЛЕГЕНДЫ ПЯТИ КОРОЛЕВСТВ', 10, GOLD))
        self.title = text_label(title, 27, TEXT, bold=True)
        header.add_widget(self.title)
        if subtitle:
            header.add_widget(text_label(subtitle, 12, MUTED))
            header.height = dp(92)
        self.column.add_widget(header)
        self.header = header
        self.brand_label = header.children[-1]
        self.subtitle_label = header.children[0] if subtitle else None
        if paged:
            surface(header, (*INK[:3], 0.90))
            self.title.font_size = sp(22)
            self.column.size_hint = (None, None)
            self.flow = self.column
        else:
            self.flow = ScrollView(size_hint=(None, None), do_scroll_x=False, bar_width=dp(3), bar_color=GOLD)
            self.flow.add_widget(self.column)
        self.add_widget(self.flow)
        self.bind(size=self.fit, pos=self.fit)
        self.fit()
        owner.add_widget(self)
        owner._front_page = self
        enter(self.column)

    def fit(self, *args):
        width = self.width - dp(24)
        self.flow.size = (max(1, min(dp(1100), width)), max(1, self.height - dp(24)))
        self.flow.center = self.center
        if self.paged:
            compact = self.height < dp(420)
        else:
            compact = False
            short = self.height < dp(420)
            self.column.padding = dp(12 if short else 16)
            self.column.spacing = dp(8 if short else 12)
        for label in self.header.children:
            label.size_hint_y = None
            hidden = self.paged and compact and label in (self.subtitle_label, self.brand_label)
            label.opacity = 0 if hidden else 1
            if hidden:
                label.height = 0
            else:
                text = CoreLabel(text=label.text, font_size=label.font_size, font_name=label.font_name,
                                 bold=label.bold, text_size=(max(dp(160), self.flow.width - dp(40)), None))
                text.refresh()
                label.height = text.texture.height + dp(2)
        self.header.height = sum(label.height for label in self.header.children) + self.header.spacing * (len(self.header.children) - 1)


def build_main_menu(owner):
    page = FrontPage(owner, 'Лэрдон', 'Создайте королевство. Измените судьбу мира.')
    layout = GridLayout(cols=2, size_hint_y=None, spacing=dp(10))
    layout.bind(minimum_height=layout.setter('height'))
    layout.bind(width=lambda w, value: setattr(w, 'cols', 2 if value >= dp(560) else 1))
    owner.buttons, owner.selected_button = [], None
    actions = [('Начать игру', 'start', owner.start_game), ('Обучение', 'tutorial', owner.open_tutorial),
               ('Рейтинг', 'rating', owner.open_dossier), ('История Лэрдона', 'help', owner.open_how_to_play),
               ('Об авторе', 'author', owner.open_author), ('Выход', 'exit', owner.exit_game)]
    for title, kind, callback in actions:
        button = MenuButton(text=title, button_type=kind, size_hint_y=None, height=dp(64), font_size=sp(17))
        button.bind(on_press=lambda widget: owner.select_button(widget), on_release=callback)
        owner.buttons.append(button)
        layout.add_widget(button)
    owner.button_container = layout
    def fit_buttons(*args):
        for button in owner.buttons:
            button.height = dp(48 if page.height < dp(420) else 64)
    page.bind(size=fit_buttons)
    fit_buttons()
    page.column.add_widget(layout)
    page.column.add_widget(text_label('СТРАТЕГИЯ  ·  КОРОЛЕВСТВА  ·  ГЕРОИ', 11, MUTED,
                                      size_hint_y=None, height=dp(28)))
    page.column.add_widget(text_label('v' + VERSION, 11, GOLD, size_hint_y=None, height=dp(24)))
    owner.select_button(owner.buttons[0])


def build_campaign_setup(owner):
    owner.selected_button = None
    owner.selected_ideology = owner.selected_allies = 'random'
    owner.bg_video = owner._video_check_event = None
    owner.tutorial_enabled = owner.buttons_locked = False
    page = FrontPage(owner, 'Новая кампания', 'Выберите фракцию и условия нового мира.', paged=True)
    owner.main_container = page.column
    factions = surface(NaturalList(padding=dp(12), spacing=dp(8)), (*INK[:3], 0.88))
    factions.add_widget(text_label('ВАША ФРАКЦИЯ', 12, GOLD, size_hint_y=None, height=dp(28)))
    owner.kingdom_buttons = GridLayout(cols=1, size_hint_y=None, spacing=dp(6))
    owner.kingdom_buttons.bind(minimum_height=owner.kingdom_buttons.setter('height'))
    owner.kingdom_buttons.bind(width=lambda widget, width: setattr(widget, 'cols', 2 if width < dp(260) else 1))
    owner.faction_data = owner.load_factions_from_db()
    owner.kingdom_button_widgets = {}
    for data in owner.faction_data:
        name = data['name']
        button = FactionChoice(text=name, size_hint_y=None, height=dp(48), font_size=sp(14))
        button.bind(on_release=owner.select_kingdom)
        owner.kingdom_buttons.add_widget(button)
        owner.kingdom_button_widgets[name] = button
    factions.add_widget(owner.kingdom_buttons)
    settings = surface(NaturalList(padding=dp(12), spacing=dp(10)), (*INK[:3], 0.88))
    owner.faction_panel_container, owner.settings_panel_container = factions, settings
    owner.settings_content_container = settings
    settings.add_widget(text_label('УСЛОВИЯ КАМПАНИИ', 12, GOLD, size_hint_y=None, height=dp(28)))
    from window_theme import skin_button, StrategySpinnerOption
    for caption, name, values, callback in (
            ('Идеология', 'ideology_spinner', ('Случайная', 'Смирение', 'Борьба'), owner.on_ideology_selected),
            ('Единомышленники', 'allies_spinner', ('Случайное количество', '1', '2'), owner.on_allies_selected)):
        settings.add_widget(text_label(caption, 13, MUTED, size_hint_y=None, height=dp(26)))
        spinner = Spinner(text=values[0], values=values, option_cls=StrategySpinnerOption,
                          size_hint_y=None, height=dp(48), font_size=sp(14))
        skin_button(spinner)
        spinner.bind(text=callback)
        setattr(owner, name, spinner)
        settings.add_widget(spinner)
    owner.ideology_bonus_icon = Image(source='files/pict/menu/bonus_icon.png', size_hint_x=None, width=dp(24))
    bonus = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(8))
    bonus.add_widget(owner.ideology_bonus_icon)
    owner.ideology_bonus_label = text_label('Идеология будет выбрана случайно', 12, MUTED)
    bonus.add_widget(owner.ideology_bonus_label)
    settings.add_widget(bonus)
    owner.allies_count_label = text_label('Случайно 1 или 2 союзника', 12, MUTED, size_hint_y=None, height=dp(32))
    settings.add_widget(owner.allies_count_label)
    owner._stat_bars = {}
    for name in ('Экономика', 'Кристаллы', 'Армия'):
        row = BoxLayout(size_hint_y=None, height=dp(28), spacing=dp(10))
        row.add_widget(text_label(name, 12, MUTED))
        meter = Meter(size_hint_y=None, height=dp(12), pos_hint={'center_y': 0.5})
        row.add_widget(meter)
        holder = [0]
        def update(meter=meter, holder=holder):
            Animation.cancel_all(meter, 'value')
            Animation(value=holder[0], duration=0.22, t='out_quad').start(meter)
        owner._stat_bars[name] = dict(ratio=holder, updater=update)
        settings.add_widget(row)
    owner.faction_ability_label = text_label('', 13, GOLD, markup=True, size_hint_y=None, height=dp(64))
    settings.add_widget(owner.faction_ability_label)
    columns = CampaignColumns(factions, settings)
    owner.campaign_columns = columns
    page.column.add_widget(columns)
    actions = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))
    owner.back_btn = StrategyButton(text='В меню')
    owner.start_game_button = StrategyButton(text='Начать игру', primary=True, disabled=True)
    owner.back_btn.bind(on_release=owner.back_to_menu)
    owner.start_game_button.bind(on_release=owner.start_game)
    actions.add_widget(owner.back_btn)
    actions.add_widget(owner.start_game_button)
    page.column.add_widget(actions)
    owner._faction_bg_images = {name: f'files/menu/choise/{path}.jpg' for name, path in FACTION_ART.items()}
    first = owner.kingdom_button_widgets.get('Вампиры') or next(iter(owner.kingdom_button_widgets.values()), None)
    if first:
        owner.select_kingdom(first)


def switch_faction_art(owner, name):
    path = owner._faction_bg_images.get(name)
    if path:
        owner._front_page.art.source = path
    owner.start_game_button.disabled = False


def build_tutorial_picker(owner):
    page = FrontPage(owner, 'Обучение', 'Освойте управление выбранной фракцией.')
    owner._faction_btns = {}
    for name in owner.FACTIONS:
        button = FactionChoice(text=name, size_hint_y=None, height=dp(52))
        button.bind(on_release=lambda widget, name=name: owner._select_faction(name))
        page.column.add_widget(button)
        page.column.add_widget(text_label(owner.FACTION_HINT.get(name, ''), 12, MUTED,
                                          size_hint_y=None, height=dp(30)))
        owner._faction_btns[name] = button
    actions = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))
    back = StrategyButton(text='В меню')
    back.bind(on_release=owner._go_back)
    owner.start_btn = StrategyButton(text='Начать обучение', primary=True, disabled=True)
    owner.start_btn.bind(on_release=owner._start_tutorial)
    actions.add_widget(back)
    actions.add_widget(owner.start_btn)
    page.column.add_widget(actions)


def build_author(owner):
    page = FrontPage(owner, 'Об авторе', 'Добро пожаловать в мир Лэрдона.')
    page.column.add_widget(text_label('Желаю вам приятно провести время в моём мире!', 20, GOLD,
                                      size_hint_y=None, height=dp(80)))
    for caption, address in (('Автор ВКонтакте', 'https://vk.com/destianfarbius'),
                              ('Сообщество Telegram', 'https://t.me/+scOGK6ph6r03YmU6')):
        button = StrategyButton(text=caption, size_hint_y=None, height=dp(52))
        button.bind(on_release=lambda widget, address=address: owner.open_link(widget, address))
        page.column.add_widget(button)
    page.column.add_widget(text_label('Иконки и изображения: Flaticon.com, Qwen, ChatGPT', 12, MUTED,
                                      size_hint_y=None, height=dp(56)))
    back = StrategyButton(text='В меню', size_hint_y=None, height=dp(52))
    back.bind(on_release=owner.go_back)
    page.column.add_widget(back)


def finish_legacy_page(owner, root):
    """Apply the same chrome to lore/rating, retaining their content and actions."""
    from window_theme import theme_tree
    theme_tree(root)
    owner.add_widget(WindowFlow(root))
    enter(root)


def restyle_loading(owner):
    for widget in list(owner.children):
        owner.remove_widget(widget)
    page = FrontPage(owner, 'Подготовка мира', 'Загружаем королевства, героев и хроники.')
    for label in (owner.label, owner.percent_label, owner.tip_label):
        label.pos_hint = {}
        label.size_hint = (1, None)
        label.height = dp(52)
        label.color = TEXT if label is owner.label else GOLD if label is owner.percent_label else MUTED
        label.halign = 'center'
        page.column.add_widget(label)
    owner.pb_container = Meter(size_hint_y=None, height=dp(12))
    page.column.add_widget(owner.pb_container, index=1)


def build_rating(owner):
    page = FrontPage(owner, 'Рейтинг', 'История кампаний и воинские звания.', paged=True)
    from window_theme import skin_button, StrategySpinnerOption
    selector = Spinner(text='Все фракции', values=('Все фракции',), size_hint_y=None,
                       height=dp(48), font_size=sp(14), option_cls=StrategySpinnerOption)
    skin_button(selector)
    page.column.add_widget(selector)
    scroll = ScrollView(do_scroll_x=False, bar_width=dp(3), bar_color=GOLD)
    records = NaturalList(spacing=dp(10))
    scroll.add_widget(records)
    page.column.add_widget(scroll)
    owner.rating_selector, owner.rating_records = selector, records

    def refresh(*args):
        records.clear_widgets()
        try:
            rows = owner.conn.execute('SELECT * FROM dossier').fetchall()
        except Exception:
            rows = []
        selector.values = ('Все фракции',) + tuple(dict.fromkeys(row[1] for row in rows))
        for row in rows:
            if selector.text != 'Все фракции' and row[1] != selector.text:
                continue
            faction = row[1]
            card = surface(NaturalList(padding=dp(12), spacing=dp(6)), (*INK[:3], 0.94), FACTIONS.get(faction, GOLD))
            card.add_widget(text_label(faction, 17, FACTIONS.get(faction, GOLD), bold=True))
            card.add_widget(text_label(str(row[2] or 'Без звания'), 15, TEXT))
            card.add_widget(text_label(f'Военный рейтинг: {row[3] or 0}  ·  Потери от голода: {row[4] or 0}', 12, MUTED))
            card.add_widget(text_label(f'Сражения: {row[5] or 0} побед  ·  {row[6] or 0} поражений', 14, TEXT))
            card.add_widget(text_label(f'Кампании: {row[7] or 0} побед  ·  {row[8] or 0} поражений', 14, GOLD))
            if row[9]:
                card.add_widget(text_label(str(row[9]), 11, MUTED))
            records.add_widget(card)
        if not records.children:
            empty = surface(NaturalList(padding=dp(18), spacing=dp(8)), (*INK[:3], 0.94))
            empty.add_widget(text_label('История ещё не написана', 20, GOLD, bold=True))
            empty.add_widget(text_label('Завершите первую кампанию, чтобы здесь появились ваши достижения.', 14, MUTED))
            records.add_widget(empty)
    owner.refresh_rating = refresh
    selector.bind(text=refresh)
    actions = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(10))
    for caption, callback in (('В меню', owner.go_back), ('Очистить историю', owner.clear_dossier)):
        button = StrategyButton(text=caption)
        button.bind(on_release=callback)
        actions.add_widget(button)
    page.column.add_widget(actions)
    refresh()
