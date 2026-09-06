from kivy.graphics import Rectangle
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.app import App
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.core.image import Image as CoreImage
from kivy.properties import StringProperty, OptionProperty, ObjectProperty, NumericProperty
import math

from kivy.graphics import Color, RoundedRectangle
from kivy.uix.button import Button
from kivy.metrics import dp
from kivy.utils import get_color_from_hex
from kivy.properties import ListProperty, NumericProperty

# Импорт дизайн-системы
from design_system import PRIMARY_COLORS, THEMES, TYPOGRAPHY, FACTION_COLORS, SEMANTIC_COLORS, FONT, SPACING, ANIMATION

class ModernButton(Button):
    normal_color = ListProperty([0.3, 0.7, 0.3, 1])   # зелёный
    pressed_color = ListProperty([0.2, 0.5, 0.2, 1]) # тёмно-зелёный
    shadow_color = ListProperty([0, 0, 0, 0.2])
    radius = NumericProperty(dp(24))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ''
        self.background_down = ''
        self.border = (0, 0, 0, 0)
        self.font_size = dp(18)
        self.bold = True
        self.color = (1, 1, 1, 1)

        with self.canvas.before:
            # Тень
            Color(*self.shadow_color)
            self.shadow_rect = RoundedRectangle(
                pos=(self.x + dp(2), self.y - dp(2)),
                size=self.size,
                radius=[self.radius]
            )
            # Основной цвет (normal)
            self.bg_color = Color(*self.normal_color)
            self.bg_rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[self.radius]
            )

        self.bind(pos=self._update_graphics, size=self._update_graphics,
                  normal_color=self._update_bg_color, pressed_color=self._update_bg_color)

    def _update_graphics(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.shadow_rect.pos = (self.x + dp(2), self.y - dp(2))
        self.shadow_rect.size = self.size

    def _update_bg_color(self, *args):
        # При смене цвета обновляем Color инструкцию, если не нажата
        if not self.state == 'down':
            self.bg_color.rgba = self.normal_color

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.bg_color.rgba = self.pressed_color
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            self.bg_color.rgba = self.normal_color
        return super().on_touch_up(touch)


class ResourceCard(BoxLayout):
    """Карточка ресурса с иконкой и значением"""
    resource_name = StringProperty('')
    resource_value = StringProperty('')
    resource_icon = StringProperty('')
    card_color = ListProperty([0.16, 0.20, 0.27, 0.9])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = dp(60)
        self.padding = dp(12)
        self.spacing = dp(8)

        with self.canvas.before:
            Color(*self.card_color)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])

        self.bind(pos=self._update_bg, size=self._update_bg)

        # Иконка ресурса
        self.icon = Image(
            source=self.resource_icon,
            size_hint=(None, None),
            size=(dp(36), dp(36)),
            pos_hint={'center_y': 0.5}
        )

        # Контейнер для текста
        text_container = BoxLayout(orientation='vertical', spacing=dp(2))

        # Название ресурса
        self.name_label = Label(
            text=self.resource_name,
            font_size=sp(12),
            color=(0.7, 0.7, 0.7, 1),
            size_hint_y=None,
            height=dp(16),
            halign='left'
        )

        # Значение ресурса
        self.value_label = Label(
            text=self.resource_value,
            font_size=sp(16),
            color=(1, 1, 1, 1),
            bold=True,
            size_hint_y=None,
            height=dp(20),
            halign='left'
        )

        text_container.add_widget(self.name_label)
        text_container.add_widget(self.value_label)

        self.add_widget(self.icon)
        self.add_widget(text_container)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size


class NotificationToast(FloatLayout):
    """Всплывающее уведомление в стиле Android/iOS"""
    message = StringProperty('')
    toast_type = OptionProperty('info', options=['info', 'success', 'warning', 'error'])
    duration = NumericProperty(3.0)  # секунды

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(300), dp(60))
        self.pos_hint = {'center_x': 0.5, 'top': 0.95}

        # Цвета для разных типов
        colors = {
            'info': get_color_from_hex(PRIMARY_COLORS['accent']),
            'success': get_color_from_hex(PRIMARY_COLORS['success']),
            'warning': get_color_from_hex(PRIMARY_COLORS['warning']),
            'error': get_color_from_hex(PRIMARY_COLORS['error'])
        }

        with self.canvas.before:
            Color(*colors.get(self.toast_type, colors['info']))
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(30)])

        self.bind(pos=self._update_bg, size=self._update_bg)

        # Иконка типа уведомления
        icons = {
            'info': 'ℹ️',
            'success': '✅',
            'warning': '⚠️',
            'error': '❌'
        }

        icon_label = Label(
            text=icons.get(self.toast_type, 'ℹ️'),
            font_size=sp(20),
            size_hint=(None, None),
            size=(dp(30), dp(30)),
            pos_hint={'center_y': 0.5}
        )

        # Текст уведомления
        message_label = Label(
            text=self.message,
            font_size=sp(14),
            color=(1, 1, 1, 1),
            halign='left',
            valign='center',
            text_size=(dp(240), dp(40))
        )

        # Добавляем виджеты
        self.add_widget(icon_label)
        self.add_widget(message_label)

        # Анимация появления
        self.opacity = 0
        anim = Animation(opacity=1, duration=0.3)
        anim.start(self)

        # Автоматическое исчезновение
        Clock.schedule_once(self._fade_out, self.duration)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def _fade_out(self, dt):
        anim = Animation(opacity=0, duration=0.5)
        anim.bind(on_complete=lambda *args: self.parent.remove_widget(self) if self.parent else None)
        anim.start(self)


class ProgressBar(FloatLayout):
    """Современная полоска прогресса"""
    value = NumericProperty(0)
    max_value = NumericProperty(100)
    bar_color = ListProperty([0.3, 0.7, 0.3, 1])
    background_color = ListProperty([0.2, 0.2, 0.2, 0.3])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(8)

        with self.canvas.before:
            # Фон полоски
            Color(*self.background_color)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(4)])

            # Заполненная часть
            Color(*self.bar_color)
            self.progress_rect = RoundedRectangle(pos=self.pos, size=(0, self.height), radius=[dp(4)])

        self.bind(pos=self._update_graphics, size=self._update_graphics, value=self._update_progress)

    def _update_graphics(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self._update_progress()

    def _update_progress(self, *args):
        if self.max_value > 0:
            progress_width = (self.value / self.max_value) * self.width
            self.progress_rect.size = (progress_width, self.height)
            self.progress_rect.pos = self.pos


class TabBar(BoxLayout):
    """Горизонтальная панель вкладок"""
    tabs = ListProperty([])
    active_tab = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = dp(48)
        self.spacing = dp(2)

        # Создаем вкладки
        self._create_tabs()

    def _create_tabs(self):
        self.clear_widgets()
        for i, tab_data in enumerate(self.tabs):
            tab = TabButton(
                text=tab_data.get('text', ''),
                icon=tab_data.get('icon', ''),
                active=i == self.active_tab
            )
            tab.bind(on_release=lambda btn, idx=i: self._switch_tab(idx))
            self.add_widget(tab)

    def _switch_tab(self, tab_index):
        self.active_tab = tab_index
        self._create_tabs()


class TabButton(Button):
    """Кнопка вкладки"""
    icon = StringProperty('')
    active = OptionProperty(False, options=[True, False])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ''
        self.size_hint_x = 1
        self.font_size = sp(14)

        with self.canvas.before:
            if self.active:
                Color(0.3, 0.6, 0.9, 1)
            else:
                Color(0.2, 0.2, 0.2, 0.5)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(8), dp(8), 0, 0])

        self.bind(pos=self._update_bg, size=self._update_bg, active=self._update_bg)

    def _update_bg(self, *args):
        if hasattr(self, 'bg_rect'):
            if self.active:
                self.bg_rect.source.color = (0.3, 0.6, 0.9, 1)
            else:
                self.bg_rect.source.color = (0.2, 0.2, 0.2, 0.5)

class SkipButton(ModernButton):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.normal_color = get_color_from_hex('#F44336')  # красный
        self.pressed_color = get_color_from_hex('#B71C1C') # тёмно-красный
        self.text = 'Пропустить обучение'
        self.font_size = dp(16)
        self.size_hint = (None, None)
        self.size = (dp(200), dp(40))


class TutorialHint(FloatLayout):
    """
    Улучшенный виджет подсказки с эффектом фокуса на целевом виджете,
    стрелкой и текстовым пузырём.
    """

    arrow_direction = OptionProperty('right', options=['right', 'down'])
    message = StringProperty('')
    target_widget = ObjectProperty(None, allownone=True)
    on_complete = ObjectProperty(None)
    on_skip = ObjectProperty(None)
    on_next = ObjectProperty(None)

    def __init__(self, target_widget, arrow_source, message, arrow_direction='right',
                 on_complete=None, on_skip=None, on_next=None, **kwargs):
        super().__init__(**kwargs)
        self.target_widget = target_widget
        self.arrow_direction = arrow_direction
        self.on_complete = on_complete
        self.on_skip = on_skip
        self.on_next = on_next
        self.message = message
        self.spotlight_padding = dp(25)
        self.size_hint = (1, 1)
        self.pos_hint = {'x': 0, 'y': 0}

        # Затемняющий фон
        with self.canvas.before:
            Color(0, 0, 0, 0.65)
            self.bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_bg, size=self._update_bg)

        # 4 прямоугольника для вырезания области
        with self.canvas.before:
            Color(0, 0, 0, 0.85)
            self.top_rect = Rectangle()
            self.left_rect = Rectangle()
            self.right_rect = Rectangle()
            self.bottom_rect = Rectangle()

        # Стрелка
        self.arrow = Image(
            source=arrow_source,
            size_hint=(None, None),
            size=(dp(60), dp(60)),
            allow_stretch=True,
            keep_ratio=True
        )

        # Пузырь (контейнер для текста и кнопки)
        self.bubble = BoxLayout(
            orientation='vertical',
            size_hint=(None, None),
            padding=(dp(20), dp(20), dp(20), dp(16)),  # увеличены отступы
            spacing=dp(16)
        )

        # Текст подсказки
        self.label = Label(
            text=self.message,
            font_size=sp(14),  # уменьшен размер шрифта
            color=(1, 1, 1, 1),
            halign='center',
            valign='middle',
            markup=True,
            size_hint_y=None,
            text_size=(None, None)
        )
        self.label.bind(texture_size=self._update_label_height)

        # Кнопка "Далее" – чуть шире для удобства нажатия
        self.next_btn = ModernButton(
            text='Продолжить',
            size_hint=(None, None),
            size=(dp(400), dp(48)),
            pos_hint={'center_x': 0.5}
        )
        self.next_btn.bind(on_release=self._on_next)

        # Кнопка пропуска
        self.skip_btn = SkipButton()
        self.skip_btn.bind(on_release=self._on_skip)

        # Сборка пузыря
        self.bubble.add_widget(self.label)
        self.bubble.add_widget(self.next_btn)

        # Фон пузыря с тенью и градиентом
        with self.bubble.canvas.before:
            # Тень (чёрная с прозрачностью)
            Color(0, 0, 0, 0.3)
            self.bubble_shadow = RoundedRectangle(
                pos=(self.bubble.x + dp(4), self.bubble.y - dp(4)),
                size=self.bubble.size,
                radius=[dp(24)]
            )
            # Основной фон (синий)
            Color(0.2, 0.4, 0.8, 0.98)
            self.bubble_bg1 = RoundedRectangle(
                pos=self.bubble.pos,
                size=self.bubble.size,
                radius=[dp(24)]
            )
            # Светлая верхушка для эффекта градиента
            Color(0.3, 0.5, 0.9, 0.95)
            self.bubble_bg2 = RoundedRectangle(
                pos=(self.bubble.x, self.bubble.y + self.bubble.height * 0.7),
                size=(self.bubble.width, self.bubble.height * 0.3),
                radius=[(dp(24), dp(24), 0, 0)]
            )

        self.bubble.bind(pos=self._update_bubble_bg, size=self._update_bubble_bg)
        self.bubble.bind(width=self._update_label_text_size)

        # Добавляем виджеты
        self.add_widget(self.arrow)
        self.add_widget(self.bubble)
        self.add_widget(self.skip_btn)

        # Подписка на изменение размера окна (поворот экрана)
        Window.bind(on_resize=self._on_window_resize)

        # Позиционирование после того как layout готов
        Clock.schedule_once(self._position_elements, 0.1)

        # Анимация появления
        self.opacity = 0
        anim = Animation(opacity=1, duration=0.4, t='out_quad')
        anim.start(self)

        # Анимация стрелки
        self._start_arrow_animation()

    def _start_arrow_animation(self):
        """Пульсация стрелки (изменение размера)"""
        base_size = (dp(60), dp(60))
        larger_size = (dp(66), dp(66))
        anim = Animation(size=larger_size, duration=0.8, t='out_elastic') + Animation(size=base_size, duration=0.8, t='out_elastic')
        anim.repeat = True
        anim.start(self.arrow)

    def _update_label_height(self, instance, texture_size):
        instance.height = max(texture_size[1], dp(40))

    def _update_label_text_size(self, instance, width):
        self.label.text_size = (width - dp(40), None)  # отступы внутри пузыря

    def _on_window_resize(self, instance, width, height):
        """Пересчёт позиции при изменении размера окна"""
        if self.parent:
            Clock.schedule_once(self._position_elements, 0.1)

    def _position_elements(self, dt):
        if not self.target_widget or not self.target_widget.get_parent_window():
            return

        target = self.target_widget
        target_x, target_y = target.to_window(*target.pos)
        target_w, target_h = target.size

        win_x, win_y = self.to_widget(target_x, target_y)

        hole_x = win_x - self.spotlight_padding
        hole_y = win_y - self.spotlight_padding
        hole_w = target_w + self.spotlight_padding * 2
        hole_h = target_h + self.spotlight_padding * 2

        window_w, window_h = Window.size

        self.top_rect.pos = (0, hole_y + hole_h)
        self.top_rect.size = (window_w, window_h - (hole_y + hole_h))

        self.left_rect.pos = (0, hole_y)
        self.left_rect.size = (hole_x, hole_h)

        self.right_rect.pos = (hole_x + hole_w, hole_y)
        self.right_rect.size = (window_w - (hole_x + hole_w), hole_h)

        self.bottom_rect.pos = (0, 0)
        self.bottom_rect.size = (window_w, hole_y)

        bubble_center_x = win_x + target_w / 2
        bubble_center_y = win_y + target_h / 2

        # Адаптивная ширина пузыря: максимум 500dp, но с отступами от краёв по 20dp
        max_bubble_width = window_w - dp(40)  # отступы 20 слева и справа
        self.bubble.width = min(dp(600), max_bubble_width)

        # Обновляем text_size метки и пересчитываем высоту
        self._update_label_text_size(self.bubble, self.bubble.width)
        self.label.texture_update()
        self.bubble.height = self.label.height + self.next_btn.height + dp(52)  # padding + spacing

        if self.arrow_direction == 'right':
            self.arrow.pos = (win_x - dp(100), bubble_center_y - dp(30))
            self.bubble.pos = (
                win_x - self.bubble.width - dp(80),
                bubble_center_y - self.bubble.height / 2
            )
        else:  # down
            self.arrow.pos = (bubble_center_x - dp(30), win_y - dp(100))
            self.bubble.pos = (
                bubble_center_x - self.bubble.width / 2,
                win_y - self.bubble.height - dp(80)
            )

        self._ensure_bubble_on_screen()
        self.skip_btn.pos = (window_w / 2 - self.skip_btn.width / 2, dp(30))

    def _update_bubble_bg(self, instance, value):
        self.bubble_bg1.pos = instance.pos
        self.bubble_bg1.size = instance.size
        self.bubble_bg2.pos = (instance.x, instance.y + instance.height * 0.7)
        self.bubble_bg2.size = (instance.width, instance.height * 0.3)
        self.bubble_shadow.pos = (instance.x + dp(4), instance.y - dp(4))
        self.bubble_shadow.size = instance.size

    def _ensure_bubble_on_screen(self):
        window_w, window_h = Window.size
        if self.bubble.x < dp(10):
            self.bubble.x = dp(10)
        elif self.bubble.right > window_w - dp(10):
            self.bubble.x = window_w - self.bubble.width - dp(10)

        if self.bubble.y < dp(80):
            self.bubble.y = dp(80)
        elif self.bubble.top > window_h - dp(10):
            self.bubble.y = window_h - self.bubble.height - dp(10)

    def _on_next(self, instance):
        anim = Animation(opacity=0, duration=0.25, t='out_quad')
        anim.bind(on_complete=lambda *a: self._cleanup())
        anim.start(self)
        if self.on_next:
            Clock.schedule_once(lambda dt: self.on_next(), 0.3)

    def _on_skip(self, instance):
        anim = Animation(opacity=0, duration=0.25, t='out_quad')
        anim.bind(on_complete=lambda *a: self._cleanup())
        anim.start(self)
        if self.on_skip:
            Clock.schedule_once(lambda dt: self.on_skip(), 0.3)

    def _cleanup(self):
        if self.parent:
            self.parent.remove_widget(self)

    def _update_bg(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def on_touch_down(self, touch):
        """Позволяет касаниям проходить сквозь затемнение к целевому виджету"""
        if self.bubble.collide_point(*touch.pos) or self.skip_btn.collide_point(*touch.pos):
            return super().on_touch_down(touch)

        if self.target_widget and self.target_widget.collide_point(*self.target_widget.to_widget(*touch.pos)):
            return False

        return True  # поглощаем касание вне области


class AnimatedHealthBar(Widget):
    """
    Анимированная полоса здоровья с плавным изменением цвета.
    Зелёный (100%) → Жёлтый (50%) → Красный (0%).
    Использует Animation(ratio=...) для плавного перехода.
    """
    ratio = NumericProperty(1.0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(28)
        self.bind(ratio=self._draw, pos=self._draw, size=self._draw)

    @staticmethod
    def _hp_color(r):
        """Цвет полосы по текущему значению ratio (0.0–1.0)."""
        r = max(0.0, min(1.0, r))
        if r >= 0.55:
            # Зелёный → жёлто-зелёный
            t = (r - 0.55) / 0.45
            return (0.15 + (1 - t) * 0.72, 0.58 + t * 0.28, 0.04, 1)
        elif r >= 0.25:
            # Жёлто-зелёный → оранжевый
            t = (r - 0.25) / 0.30
            return (0.94, 0.12 + t * 0.52, 0.02, 1)
        else:
            # Красный
            return (0.88, 0.08, 0.04, 1)

    def _draw(self, *args):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        with self.canvas:
            # Фоновый трек
            Color(0.09, 0.09, 0.15, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(14)])
            # Заполненная часть
            fw = self.width * max(0.0, min(1.0, self.ratio))
            if fw > dp(6):
                Color(*self._hp_color(self.ratio))
                RoundedRectangle(pos=self.pos, size=(fw, self.height), radius=[dp(14)])
                # Блик сверху
                Color(1, 1, 1, 0.15)
                RoundedRectangle(
                    pos=(self.x + dp(4), self.y + self.height * 0.60),
                    size=(max(dp(4), fw - dp(8)), self.height * 0.28),
                    radius=[dp(8)]
                )

    def animate_to(self, new_ratio, duration=0.44):
        """Плавно анимирует полосу к новому значению."""
        Animation.cancel_all(self, 'ratio')
        Animation(ratio=max(0.0, new_ratio), duration=duration, t='out_cubic').start(self)


# ─── Система дипломатических уведомлений (иконки + popup) ─────────

# Маппинг фракций на файлы иконок
FACTION_ICON_MAP = {
    'Север': 'files/sov/people.jpg',
    'Эльфы': 'files/sov/elfs.jpg',
    'Вампиры': 'files/sov/vampire.jpg',
    'Адепты': 'files/sov/adept.jpg',
    'Элины': 'files/sov/poly.jpg',
}


class DiplomacyMailbox(FloatLayout):
    """
    Панель дипломатических иконок-уведомлений.
    Иконки фракций выстраиваются в ряд, не перекрывая друг друга.
    При нажатии — открывается popup с полным сообщением и кнопками ответа.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (Window.width, dp(60))
        self.pos = (0, Window.height - dp(110))
        self._icons = {}  # faction_name -> DiplomacyIcon widget
        self._messages = {}  # faction_name -> list of messages

    def add_message(self, faction_name, message, message_type='info', on_respond=None):
        """Добавляет сообщение. Если иконка фракции уже есть — добавляет к ней."""
        if faction_name not in self._messages:
            self._messages[faction_name] = []
        self._messages[faction_name].append({
            'text': message,
            'type': message_type,
            'on_respond': on_respond,
        })

        if faction_name not in self._icons:
            self._create_icon(faction_name)
        else:
            # Обновляем счётчик
            self._icons[faction_name].update_badge(len(self._messages[faction_name]))

    def _create_icon(self, faction_name):
        """Создаёт анимированную иконку фракции."""
        icon_size = dp(50)
        idx = len(self._icons)
        x_pos = dp(130) + idx * (icon_size + dp(8))

        icon = DiplomacyIcon(
            faction_name=faction_name,
            pos=(x_pos, self.y + dp(5)),
            on_tap=lambda name=faction_name: self._open_message(name),
        )

        # Анимация появления
        icon.opacity = 0
        icon_final_y = icon.y
        icon.y = icon_final_y + dp(40)
        anim = Animation(opacity=1, y=icon_final_y, duration=0.4, t='out_back')
        anim.start(icon)

        self._icons[faction_name] = icon
        self.add_widget(icon)

    def _open_message(self, faction_name):
        """Открывает popup с сообщениями от фракции."""
        messages = self._messages.get(faction_name, [])
        if not messages:
            return

        last_msg = messages[-1]
        popup = DiplomacyMessagePopup(
            faction_name=faction_name,
            message=last_msg['text'],
            message_type=last_msg['type'],
            on_respond=last_msg.get('on_respond'),
        )
        popup.open()

        # Убираем иконку после открытия
        self._remove_icon(faction_name)

    def _remove_icon(self, faction_name):
        """Убирает иконку с анимацией."""
        icon = self._icons.pop(faction_name, None)
        self._messages.pop(faction_name, None)
        if icon:
            anim = Animation(opacity=0, y=icon.y + dp(30), duration=0.25)
            anim.bind(on_complete=lambda *a: self.remove_widget(icon))
            anim.start(icon)
            # Сдвигаем оставшиеся иконки
            Clock.schedule_once(lambda dt: self._reposition_icons(), 0.3)

    def _reposition_icons(self):
        """Перевыстраивает иконки после удаления."""
        icon_size = dp(50)
        for i, (name, icon) in enumerate(self._icons.items()):
            target_x = dp(130) + i * (icon_size + dp(8))
            Animation(x=target_x, duration=0.2, t='out_quad').start(icon)


class DiplomacyIcon(FloatLayout):
    """Иконка фракции с badge-счётчиком непрочитанных."""

    def __init__(self, faction_name, on_tap=None, **kwargs):
        super().__init__(**kwargs)
        self.faction_name = faction_name
        self.on_tap = on_tap
        self.size_hint = (None, None)
        self.size = (dp(50), dp(50))

        icon_path = FACTION_ICON_MAP.get(faction_name, '')
        faction_data = FACTION_COLORS.get(faction_name)
        border_color = faction_data['primary'] if faction_data else (0.5, 0.5, 0.5, 1)

        # Фон (граница фракции)
        with self.canvas.before:
            Color(*border_color)
            self._border = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(25)])
            Color(0.12, 0.12, 0.18, 1)
            self._inner = RoundedRectangle(
                pos=(self.x + dp(3), self.y + dp(3)),
                size=(self.width - dp(6), self.height - dp(6)),
                radius=[dp(22)]
            )

        self.bind(pos=self._update_gfx, size=self._update_gfx)

        # Иконка фракции
        self.icon_img = Image(
            source=icon_path,
            size_hint=(None, None),
            size=(dp(40), dp(40)),
            pos=(self.x + dp(5), self.y + dp(5)),
            allow_stretch=True,
            keep_ratio=True,
        )
        self.add_widget(self.icon_img)

        # Badge (счётчик сообщений)
        self.badge_label = Label(
            text='1',
            font_size=sp(10),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint=(None, None),
            size=(dp(18), dp(18)),
            pos=(self.right - dp(14), self.top - dp(14)),
        )
        with self.badge_label.canvas.before:
            Color(0.9, 0.15, 0.15, 1)
            self._badge_bg = RoundedRectangle(
                pos=self.badge_label.pos, size=self.badge_label.size, radius=[dp(9)]
            )
        self.badge_label.bind(pos=lambda *a: setattr(self._badge_bg, 'pos', self.badge_label.pos))
        self.add_widget(self.badge_label)

        # Пульсация для привлечения внимания
        self._start_pulse()

    def _start_pulse(self):
        anim = (Animation(size=(dp(54), dp(54)), pos=(self.x - dp(2), self.y - dp(2)),
                          duration=0.6, t='out_quad') +
                Animation(size=(dp(50), dp(50)), pos=(self.x, self.y),
                          duration=0.6, t='out_quad'))
        anim.repeat = True
        anim.start(self)

    def update_badge(self, count):
        self.badge_label.text = str(count)

    def _update_gfx(self, *args):
        self._border.pos = self.pos
        self._border.size = self.size
        self._inner.pos = (self.x + dp(3), self.y + dp(3))
        self._inner.size = (self.width - dp(6), self.height - dp(6))
        self.icon_img.pos = (self.x + dp(5), self.y + dp(5))
        self.badge_label.pos = (self.right - dp(14), self.top - dp(14))

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            Animation.cancel_all(self)
            if self.on_tap:
                self.on_tap()
            return True
        return super().on_touch_down(touch)


class DiplomacyMessagePopup(FloatLayout):
    """
    Popup-свиток с полным дипломатическим сообщением.
    Кнопки: Принять / Отклонить / Написать ответ.
    """

    def __init__(self, faction_name, message, message_type='info',
                 on_respond=None, **kwargs):
        super().__init__(**kwargs)
        self.faction_name = faction_name
        self.message = message
        self.on_respond = on_respond
        self.size_hint = (1, 1)

        faction_data = FACTION_COLORS.get(faction_name)
        accent = faction_data['primary'] if faction_data else (0.4, 0.4, 0.5, 1)

        # Затемнение фона
        with self.canvas.before:
            Color(0, 0, 0, 0.6)
            self._overlay = Rectangle(pos=(0, 0), size=Window.size)

        # Карточка сообщения
        card_w = min(dp(500), Window.width - dp(40))
        card_h = dp(340)
        card_x = Window.width / 2 - card_w / 2
        card_y = Window.height / 2 - card_h / 2

        self.card = FloatLayout(
            size_hint=(None, None),
            size=(card_w, card_h),
            pos=(card_x, card_y),
        )

        with self.card.canvas.before:
            # Тень
            Color(0, 0, 0, 0.4)
            RoundedRectangle(pos=(card_x + dp(4), card_y - dp(4)),
                             size=(card_w, card_h), radius=[dp(16)])
            # Фон
            Color(0.11, 0.13, 0.19, 0.97)
            self._card_bg = RoundedRectangle(pos=(card_x, card_y),
                                             size=(card_w, card_h), radius=[dp(16)])
            # Акцент сверху
            Color(*accent[:3], 1)
            RoundedRectangle(pos=(card_x, card_y + card_h - dp(4)),
                             size=(card_w, dp(4)), radius=[dp(16), dp(16), 0, 0])

        # Заголовок: иконка + имя фракции
        icon_path = FACTION_ICON_MAP.get(faction_name, '')
        header = BoxLayout(
            orientation='horizontal', spacing=dp(10),
            size_hint=(None, None), size=(card_w - dp(32), dp(44)),
            pos=(card_x + dp(16), card_y + card_h - dp(56)),
        )
        if icon_path:
            header.add_widget(Image(
                source=icon_path, size_hint=(None, None),
                size=(dp(40), dp(40)), allow_stretch=True, keep_ratio=True,
            ))
        header.add_widget(Label(
            text=f'[b]{faction_name}[/b]', markup=True,
            font_size=sp(18), color=(1, 1, 1, 1),
            halign='left', valign='middle',
            size_hint=(1, None), height=dp(40),
        ))

        # Текст сообщения
        # Убираем теги типа [ТОРГОВЛЯ] из отображения
        clean_msg = message
        for tag in ['[СОЮЗ]', '[ТОРГОВЛЯ]', '[УГРОЗА]', '[ПРЕДУПРЕЖДЕНИЕ]',
                     '[ПОЩАДА]', '[УМОЛЯЮ]', '[ПОМОЩЬ]', '[ПРОСЬБА]', '[ДРУЖБА]']:
            clean_msg = clean_msg.replace(tag, '').strip()

        msg_label = Label(
            text=clean_msg,
            font_size=sp(14),
            color=(0.9, 0.9, 0.9, 1),
            halign='left', valign='top',
            size_hint=(None, None),
            size=(card_w - dp(32), dp(160)),
            pos=(card_x + dp(16), card_y + dp(70)),
            text_size=(card_w - dp(40), dp(160)),
        )

        # Кнопки — зависят от типа сообщения
        btn_row = BoxLayout(
            orientation='horizontal', spacing=dp(10),
            size_hint=(None, None), size=(card_w - dp(32), dp(44)),
            pos=(card_x + dp(16), card_y + dp(14)),
        )

        # Типы с предложениями (торговля, союз, пощада, помощь) — Принять/Отклонить/Ответить
        actionable_types = ('trade', 'alliance', 'mercy', 'help')
        if message_type in actionable_types:
            btn_accept = Button(
                text='Принять', font_size=sp(14), bold=True,
                background_normal='', background_color=(0.2, 0.6, 0.3, 1),
                color=(1, 1, 1, 1), size_hint=(1, 1),
            )
            btn_accept.bind(on_release=lambda *a: self._respond('да'))

            btn_decline = Button(
                text='Отклонить', font_size=sp(14), bold=True,
                background_normal='', background_color=(0.6, 0.2, 0.2, 1),
                color=(1, 1, 1, 1), size_hint=(1, 1),
            )
            btn_decline.bind(on_release=lambda *a: self._respond('нет'))

            btn_reply = Button(
                text='Ответить...', font_size=sp(14), bold=True,
                background_normal='', background_color=(0.25, 0.35, 0.55, 1),
                color=(1, 1, 1, 1), size_hint=(1, 1),
            )
            btn_reply.bind(on_release=lambda *a: self._open_chat())

            btn_row.add_widget(btn_accept)
            btn_row.add_widget(btn_decline)
            btn_row.add_widget(btn_reply)
        else:
            # Информационные/предупреждения (info, warning, дружба) — Ясно/Ответить
            btn_ok = Button(
                text='Ясно', font_size=sp(14), bold=True,
                background_normal='', background_color=(0.3, 0.4, 0.55, 1),
                color=(1, 1, 1, 1), size_hint=(1, 1),
            )
            btn_ok.bind(on_release=lambda *a: self.close())

            btn_reply = Button(
                text='Ответить...', font_size=sp(14), bold=True,
                background_normal='', background_color=(0.25, 0.35, 0.55, 1),
                color=(1, 1, 1, 1), size_hint=(1, 1),
            )
            btn_reply.bind(on_release=lambda *a: self._open_chat())

            btn_row.add_widget(btn_ok)
            btn_row.add_widget(btn_reply)

        self.card.add_widget(header)
        self.card.add_widget(msg_label)
        self.card.add_widget(btn_row)
        self.add_widget(self.card)

        # Анимация
        self.opacity = 0
        self.card.y = card_y + dp(60)
        Animation(opacity=1, duration=0.2).start(self)
        Animation(y=card_y, duration=0.35, t='out_back').start(self.card)

    def _respond(self, answer):
        """Отправляет ответ (да/нет) через callback."""
        if self.on_respond:
            self.on_respond(self.faction_name, answer, self.message)
        self.close()

    def _open_chat(self):
        """Открывает полный чат с этой фракцией."""
        if self.on_respond:
            self.on_respond(self.faction_name, '__open_chat__', self.message)
        self.close()

    def open(self):
        app = App.get_running_app()
        if app and app.root:
            app.root.add_widget(self)

    def close(self):
        anim = Animation(opacity=0, duration=0.2)
        anim.bind(on_complete=lambda *a: self._cleanup())
        anim.start(self)

    def _cleanup(self):
        if self.parent:
            self.parent.remove_widget(self)

    def on_touch_down(self, touch):
        if self.card.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        # Нажатие вне карточки закрывает popup
        self.close()
        return True


# Обратная совместимость
class DiplomacyNotification:
    """Legacy wrapper — теперь используется DiplomacyMailbox."""
    pass


# ─── Единый стильный Popup для всей игры ──────────────────────────

def show_message(title, message):
    """Стильное всплывающее окно в едином дизайне Lerdon."""
    from kivy.uix.popup import Popup

    lines = message.count('\n') + 1
    text_height = max(dp(80), dp(lines * 28))
    popup_height = text_height + dp(130)

    # Контейнер
    content = FloatLayout(size_hint=(1, 1))

    # Фон с градиентом
    with content.canvas.before:
        Color(0.08, 0.09, 0.14, 1)
        content._bg = RoundedRectangle(pos=content.pos, size=content.size, radius=[dp(16)])
    content.bind(
        pos=lambda i, v: setattr(i._bg, 'pos', v),
        size=lambda i, v: setattr(i._bg, 'size', v)
    )

    # Заголовок
    title_label = Label(
        text=f"[b]{title}[/b]",
        markup=True,
        font_size=sp(18),
        color=(0.85, 0.78, 0.55, 1),
        size_hint=(1, None),
        height=dp(36),
        pos_hint={'center_x': 0.5, 'top': 0.95},
        halign='center',
    )
    title_label.bind(size=title_label.setter('text_size'))

    # Разделитель
    separator = Widget(size_hint=(0.9, None), height=dp(1), pos_hint={'center_x': 0.5, 'top': 0.78})
    with separator.canvas:
        Color(0.85, 0.78, 0.55, 0.4)
        separator._line = Rectangle(pos=separator.pos, size=separator.size)
    separator.bind(
        pos=lambda i, v: setattr(i._line, 'pos', v),
        size=lambda i, v: setattr(i._line, 'size', v)
    )

    # Текст сообщения
    msg_label = Label(
        text=message,
        font_size=sp(14),
        color=(0.85, 0.87, 0.92, 1),
        size_hint=(0.9, None),
        height=text_height,
        pos_hint={'center_x': 0.5, 'center_y': 0.52},
        halign='center',
        valign='middle',
    )
    msg_label.bind(size=msg_label.setter('text_size'))

    # Кнопка закрыть
    close_btn = Button(
        text="Закрыть",
        size_hint=(0.85, None),
        height=dp(42),
        pos_hint={'center_x': 0.5, 'y': 0.04},
        background_normal='',
        background_color=(0, 0, 0, 0),
        color=(1, 1, 1, 1),
        font_size=sp(15),
        bold=True,
    )
    with close_btn.canvas.before:
        Color(0.22, 0.45, 0.65, 1)
        close_btn._bg = RoundedRectangle(pos=close_btn.pos, size=close_btn.size, radius=[dp(10)])
    close_btn.bind(
        pos=lambda i, v: setattr(i._bg, 'pos', v),
        size=lambda i, v: setattr(i._bg, 'size', v)
    )

    content.add_widget(title_label)
    content.add_widget(separator)
    content.add_widget(msg_label)
    content.add_widget(close_btn)

    popup = Popup(
        title='',
        separator_height=0,
        content=content,
        size_hint=(0.55, None),
        height=popup_height,
        auto_dismiss=True,
        background='',
        background_color=(0, 0, 0, 0.5),
    )
    close_btn.bind(on_release=popup.dismiss)

    # Анимация появления
    popup.opacity = 0
    popup.open()
    Animation(opacity=1, duration=0.2).start(popup)


def show_error_message(message):
    """Стильное окно ошибки."""
    show_message("Ошибка", message)
