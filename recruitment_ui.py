"""A single themed recruitment window, with lazy cards and independent quantities."""
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.carousel import Carousel
from kivy.uix.image import AsyncImage, Image
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.slider import Slider
from slider_ui import StrategySlider
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget

from strategy_ui import (GOLD, INK, SURFACE, TEXT, MUTED, FACTIONS,
                         StrategyButton, frame, surface, text_label)
from utils.helpers import format_number


class RecruitmentSession(Widget):
    """Owner in game_area; the modal closes when its owner is removed."""
    def __init__(self, faction, army_hire, units, hire_callback, **kwargs):
        super().__init__(size_hint=(None, None), size=(0, 0), **kwargs)
        self._strategy_no_theme = True
        self.army_hire, self.hire_callback = army_hire, hire_callback
        self.units = sorted(units.items(), key=lambda item: int(item[1]['stats']['Класс юнита'].split()[0]))
        self.built = set()
        self.cards = {}
        self.warmup_event = None
        self.released = False
        self.accent = FACTIONS.get(faction, GOLD)
        root = surface(BoxLayout(orientation='vertical', padding=dp(8), spacing=dp(8)), INK, self.accent)
        root._strategy_fixed_layout = True
        header = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(10))
        header.add_widget(Image(source='files/status/army.png', size_hint=(None, 1), width=dp(40), mipmap=True))
        heading = BoxLayout(orientation='vertical')
        heading.add_widget(text_label('ВОЕННОЕ ДЕЛО  /  ' + faction, 10, self.accent))
        heading.add_widget(text_label('Найм войск', 21, bold=True))
        header.add_widget(heading)
        self.header_nav = BoxLayout(size_hint_x=None, width=0, spacing=dp(4))
        for caption, direction in (('‹', -1), ('›', 1)):
            arrow = StrategyButton(text=caption, accent=self.accent)
            arrow.font_size = sp(24)
            arrow.bind(on_release=lambda widget, direction=direction:
                       self.carousel.load_previous() if direction < 0 else self.carousel.load_next())
            self.header_nav.add_widget(arrow)
        header.add_widget(self.header_nav)
        close = StrategyButton(text='×', size_hint=(None, 1), width=dp(48), accent=self.accent)
        close._strategy_close = True
        header.add_widget(close)
        root.add_widget(header)
        self.carousel = Carousel(direction='right', loop=True, scroll_distance=dp(30))
        self.slides = []
        for _ in self.units:
            slide = BoxLayout()
            self.slides.append(slide)
            self.carousel.add_widget(slide)
        root.add_widget(self.carousel)
        navigation = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(12))
        self.navigation = navigation
        previous = StrategyButton(text='‹', size_hint_x=None, width=dp(56), accent=self.accent)
        next_button = StrategyButton(text='›', size_hint_x=None, width=dp(56), accent=self.accent)
        previous.font_size = next_button.font_size = sp(26)
        previous.bind(on_release=lambda *_: self.carousel.load_previous())
        next_button.bind(on_release=lambda *_: self.carousel.load_next())
        self.page = text_label('', 12, MUTED)
        self.page.halign = 'center'
        navigation.add_widget(previous)
        navigation.add_widget(self.page)
        navigation.add_widget(next_button)
        root.add_widget(navigation)
        if not self.units:
            self.carousel.add_widget(text_label('Нет доступных войск', 16, MUTED))
            previous.disabled = next_button.disabled = True
        self.popup = Popup(title='', content=root, size_hint=(None, None), auto_dismiss=False,
                           background='', background_color=INK)
        from window_theme import prepare_custom_popup
        prepare_custom_popup(self.popup)
        self.popup.bind(on_dismiss=lambda *_: self.release(dismiss=False))
        close.bind(on_release=self.popup.dismiss)
        self.close_button = close
        self.carousel.bind(index=self.prepare_current)
        Window.bind(on_resize=self.fit)
        self.fit()

    def open(self):
        self.popup.open()
        self.prepare_current(self.carousel, self.carousel.index)

    def fit(self, *args):
        width, height = args[1:3] if len(args) >= 3 else Window.size
        self.popup.size = (max(1, min(dp(1240), width - dp(12))),
                           max(1, min(dp(820), height - dp(12))))
        compact = height < dp(480)
        self.header_nav.width = dp(104) if compact else 0
        self.header_nav.opacity = 1 if compact else 0
        self.header_nav.disabled = not compact
        self.navigation.height = 0 if compact else dp(48)
        self.navigation.opacity = 0 if compact else 1
        self.navigation.disabled = compact
        for card in self.cards.values():
            card.stat_grid.cols = 2 if height < dp(330) else 1
            slider = card.quantity_slider
            if slider is not None:
                # Inline quantity selection leaves room for the portrait and
                # readable stats even on a short phone screen.
                inline = width >= dp(520)
                destination = card.controls if inline else card
                if slider.parent is not destination:
                    slider.parent.remove_widget(slider)
                    destination.add_widget(slider, index=1)
                slider.size_hint = (1, 1) if inline else (1, None)
                slider.height = dp(48)
                slider.opacity = 1
                slider.disabled = slider.max <= slider.min
            for row, caption, value in card.stat_rows:
                row.height = dp(32 if compact else 48)
                caption.font_size = sp(15 if compact else 18)
                value.font_size = sp(20 if compact else 24)
            for icon in card.stat_icons:
                icon.width = dp(30 if compact else 38)
        from window_theme import center_after_resize
        center_after_resize(self.popup)

    def maximum(self, info):
        crowns, workers = info['cost']
        economy = self.army_hire.class_faction
        cash = max(0, int(economy.get_resource_now('Кроны') or 0))
        labor = max(0, int(economy.get_resource_now('Рабочие') or 0))
        return max(0, min(cash // crowns if crowns > 0 else 99999,
                          labor // workers if workers > 0 else 99999))

    def build_card(self, index):
        name, info = self.units[index]
        unit_class = int(info['stats']['Класс юнита'].split()[0])
        card = surface(BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(4)), SURFACE,
                       self.accent if unit_class == 1 else GOLD)
        card.quantity_slider = None
        title = BoxLayout(size_hint_y=None, height=dp(30), spacing=dp(8))
        title.add_widget(text_label(name, 21, bold=True))
        rank = text_label({1: 'Рекрут', 2: 'Герой', 3: 'Чемпион', 4: 'Легенда'}.get(unit_class, 'Воин'),
                          11, GOLD, size_hint_x=None, width=dp(84))
        rank.halign = 'right'
        title.add_widget(rank)
        card.add_widget(title)
        body = BoxLayout(spacing=dp(10))
        stats = GridLayout(cols=1, size_hint_x=0.56, spacing=dp(2))
        card.stat_grid = stats
        card.stat_rows = []
        card.stat_icons = []
        for caption, icon, key in (
                ('Урон', 'sword', 'Урон'), ('Защита', 'shield', 'Защита'),
                ('Живучесть', 'health', 'Живучесть'), ('Расход', 'consumption', 'Потребление Кристаллов')):
            row = BoxLayout(size_hint_y=None, height=dp(22), spacing=dp(6))
            icon_widget = Image(source=f'files/pict/hire/{icon}.png', size_hint_x=None, width=dp(32), mipmap=True)
            row.add_widget(icon_widget)
            card.stat_icons.append(icon_widget)
            caption_label = text_label(caption, 11, MUTED)
            caption_label.shorten = True
            row.add_widget(caption_label)
            value = text_label(format_number(info['stats'].get(key, 0)), 13, TEXT,
                               bold=True, size_hint_x=0.65)
            value.halign = 'right'
            row.add_widget(value)
            stats.add_widget(row)
            card.stat_rows.append((row, caption_label, value))
        body.add_widget(stats)
        card.portrait = AsyncImage(source=info['image'], size_hint_x=0.44, fit_mode='contain', mipmap=True)
        body.add_widget(card.portrait)
        card.add_widget(body)
        price = text_label('', 13, GOLD, size_hint_y=None, height=dp(26))
        card.add_widget(price)
        controls = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        card.controls = controls
        hire = StrategyButton(text='НАНЯТЬ' if unit_class == 1 else 'НАНЯТЬ ГЕРОЯ',
                              primary=True, accent=self.accent)
        if unit_class == 1:
            slider = StrategySlider(min=1, max=max(1, self.maximum(info)), value=1, step=1,
                                    size_hint_y=None, height=dp(48))
            card.quantity_slider = slider
            card.add_widget(slider)
            quantity = TextInput(text='1', multiline=False, input_filter='int',
                                 size_hint_x=None, width=dp(74), font_size=sp(16),
                                 background_normal='', background_active='', background_color=INK,
                                 foreground_color=TEXT, cursor_color=GOLD, halign='center', padding=dp(12))
            frame(quantity)
            minus = StrategyButton(text='−', size_hint_x=None, width=dp(48))
            plus = StrategyButton(text='+', size_hint_x=None, width=dp(48))
            state = {'n': 1, 'sync': False}
            def set_quantity(value, *args):
                if state['sync']:
                    return
                state['sync'] = True
                try:
                    maximum = self.maximum(info)
                    number = min(max(1, int(value or 1)), max(1, maximum))
                    state['n'] = number
                    quantity.text = str(number)
                    slider.max, slider.value = max(1, maximum), number
                    hire.disabled = maximum < 1
                    price.text = f'Итого: {format_number(info["cost"][0] * number)} крон  ·  {format_number(info["cost"][1] * number)} раб.'
                except ValueError:
                    pass
                finally:
                    state['sync'] = False
            quantity.bind(text=lambda widget, value: set_quantity(value) if value else None,
                          focus=lambda widget, value: set_quantity(widget.text) if not value else None)
            slider.bind(value=lambda widget, value: set_quantity(value))
            minus.bind(on_release=lambda *_: set_quantity(state['n'] - 1))
            plus.bind(on_release=lambda *_: set_quantity(state['n'] + 1))
            for widget in (minus, quantity, plus):
                controls.add_widget(widget)
            def do_hire(*args):
                set_quantity(state['n'])
                if not hire.disabled:
                    self.hire_callback(name, info['cost'], quantity, self.army_hire, info['image'], info['stats'])
                    set_quantity(state['n'])
            hire.bind(on_release=do_hire)
            set_quantity(1)
        else:
            price.text = f'Цена: {format_number(info["cost"][0])} крон  ·  {format_number(info["cost"][1])} раб.'
            hire.disabled = self.maximum(info) < 1
            hire.bind(on_release=lambda *_: self.hire_callback(
                name, info['cost'], None, self.army_hire, info['image'], info['stats']))
        controls.add_widget(hire)
        card.add_widget(controls)
        # Let the portrait span the title, statistics and price, instead of
        # confining it to the shrinking middle row on Android.
        for widget in (title, body, price):
            card.remove_widget(widget)
        body.remove_widget(stats)
        body.remove_widget(card.portrait)
        details = BoxLayout(orientation='vertical', size_hint_x=.56, spacing=dp(4))
        stats.size_hint_x = 1
        for widget in (title, stats, price):
            details.add_widget(widget)
        display = BoxLayout(spacing=dp(12))
        display.add_widget(details)
        display.add_widget(card.portrait)
        card.add_widget(display, index=len(card.children))
        self.slides[index].add_widget(card)
        self.cards[index] = card
        self.built.add(index)
        self.fit()

    def prepare_current(self, carousel, index):
        if self.released or not self.units:
            return
        index = index or 0
        if index not in self.built:
            self.build_card(index)
        self.page.text = f'{index + 1} / {len(self.units)}  ·  Листайте, чтобы выбрать войска'
        if self.warmup_event:
            self.warmup_event.cancel()
        self.warmup_event = Clock.schedule_once(self.warm_neighbor, 0.1)

    def warm_neighbor(self, dt):
        self.warmup_event = None
        if self.released or self.parent is None or not self.units:
            return
        index = self.carousel.index or 0
        for neighbor in ((index + 1) % len(self.units), (index - 1) % len(self.units)):
            if neighbor not in self.built:
                self.build_card(neighbor)
                self.warmup_event = Clock.schedule_once(self.warm_neighbor, 0.1)
                break

    def release(self, *args, dismiss=True):
        if self.released:
            return
        self.released = True
        if self.warmup_event:
            self.warmup_event.cancel()
            self.warmup_event = None
        Window.unbind(on_resize=self.fit)
        if self.parent:
            self.parent.remove_widget(self)
        pending = getattr(self.popup, '_strategy_center_event', None)
        if pending:
            pending.cancel()
            self.popup._strategy_center_event = None
        if dismiss and self.popup.parent:
            self.popup.dismiss(animation=False)

    def on_parent(self, widget, parent):
        if parent is None and hasattr(self, 'popup'):
            self.release()
