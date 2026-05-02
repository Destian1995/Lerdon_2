from kivy.graphics import Rectangle
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
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
from design_system import PRIMARY_COLORS, THEMES, TYPOGRAPHY

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
