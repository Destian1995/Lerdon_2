# ai_models/ui/chat_widgets.py
import os

from kivy.core.image import Image
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.core.window import Window


class ChatMessage(BoxLayout):
    """Виджет сообщения в чате"""
    def __init__(self, message, sender, timestamp, is_player=False, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.size_hint_y = None
        self.spacing = dp(2)

        # Выравнивание сообщений
        if is_player:
            self.pos_hint = {'right': 1}
            bg_color = (0.2, 0.4, 0.6, 0.8)
        else:
            self.pos_hint = {'x': 0}
            bg_color = (0.3, 0.3, 0.4, 0.8)

        # Заголовок сообщения
        header = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=dp(20)
        )

        sender_label = Label(
            text=f"{'[Я]' if is_player else '[ИИ]'} {sender}",
            font_size='11sp',
            color=(0.8, 0.8, 0.8, 1) if is_player else (0.7, 0.8, 1, 1),
            size_hint=(0.7, 1),
            halign='left'
        )

        time_label = Label(
            text=timestamp,
            font_size='10sp',
            color=(0.6, 0.6, 0.6, 1),
            size_hint=(0.3, 1),
            halign='right'
        )

        header.add_widget(sender_label)
        header.add_widget(time_label)

        # Текст сообщения
        max_width = Window.width * 0.6
        message_label = Label(
            text=message,
            font_size='13sp',
            color=(1, 1, 1, 1) if is_player else (0.9, 0.9, 0.9, 1),
            size_hint=(None, None),
            width=max_width,
            halign='left',
            valign='top',
            text_size=(max_width - dp(20), None)
        )

        # Привязываем высоту к тексту
        message_label.bind(
            texture_size=lambda *x: message_label.setter('height')(
                message_label, message_label.texture_size[1] + dp(10))
        )

        # Контейнер с фоном
        message_container = BoxLayout(
            orientation='vertical',
            padding=[dp(10), dp(8)],
            size_hint=(None, None)
        )

        total_height = dp(20) + message_label.height + dp(8)
        message_container.size = (max_width, total_height)

        # Фон сообщения
        with message_container.canvas.before:
            Color(*bg_color)
            RoundedRectangle(
                pos=message_container.pos,
                size=message_container.size,
                radius=[dp(10)]
            )

        # Собираем виджет
        self.add_widget(header)
        self.add_widget(message_label)
        message_container.add_widget(self)

        self.container = message_container

    def get_widget(self):
        """Возвращает готовый виджет для добавления в контейнер"""
        return self.container


class ChatHeader(BoxLayout):
    """Шапка чата с информацией о фракции"""
    def __init__(self, faction, relation_data=None, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint = (1, None)
        self.height = dp(50)
        self.padding = [dp(10), 0]

        # Иконка фракции
        self.icon = Image(
            source='files/pict/question.png',
            size_hint=(None, None),
            size=(dp(40), dp(40)),
            allow_stretch=True
        )

        # Информация
        self.info_box = BoxLayout(
            orientation='vertical',
            size_hint=(0.8, 1),
            spacing=dp(2)
        )

        self.title = Label(
            text=f"Переписка с {faction}",
            font_size='16sp',
            bold=True,
            color=(1, 1, 1, 1),
            halign='left'
        )

        self.relation_status = Label(
            text="Отношения: ---",
            font_size='12sp',
            color=(0.7, 0.7, 0.7, 1),
            halign='left'
        )

        self.info_box.add_widget(self.title)
        self.info_box.add_widget(self.relation_status)

        self.add_widget(self.icon)
        self.add_widget(self.info_box)

    def update_info(self, faction, relation_data):
        """Обновляет информацию в шапке"""
        from ..translation import translation_dict

        # Обновляем иконку
        icon_path = f"files/pict/factions/{translation_dict.get(faction, faction.lower())}.png"
        if os.path.exists(icon_path):
            self.icon.source = icon_path

        # Обновляем заголовок
        self.title.text = f"Переписка с {faction}"

        # Обновляем статус отношений
        if relation_data:
            rel_color = self.get_relation_color(relation_data.get("relation_level", 0))
            self.relation_status.text = f"Отношения: {relation_data.get('relation_level', 0)}/100 ({relation_data.get('status', 'нейтралитет')})"
            self.relation_status.color = rel_color

    def get_relation_color(self, value):
        """Возвращает цвет в зависимости от значения"""
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = 50

        if value <= 15:
            return (0.8, 0.1, 0.1, 1)
        elif 15 < value <= 25:
            return (1.0, 0.5, 0.0, 1)
        elif 25 < value <= 35:
            return (1.0, 0.8, 0.0, 1)
        elif 35 < value <= 50:
            return (0.2, 0.7, 0.3, 1)
        elif 50 < value <= 60:
            return (0.0, 0.8, 0.8, 1)
        elif 60 < value <= 75:
            return (0.0, 0.6, 1.0, 1)
        elif 75 < value <= 90:
            return (0.1, 0.3, 0.9, 1)
        else:
            return (1, 1, 1, 1)


class ChatInputPanel(BoxLayout):
    """Панель ввода сообщения"""
    def __init__(self, send_callback, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint = (1, None)
        self.height = dp(60)
        self.spacing = dp(10)
        self.padding = [dp(5), dp(5)]

        # Поле ввода
        self.input_field = TextInput(
            hint_text="Введите ваше сообщение...",
            multiline=False,
            size_hint=(0.7, 1),
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            padding=[dp(10), dp(10)],
            font_size='14sp'
        )

        # Кнопка отправки
        self.send_button = Button(
            text="Отправить",
            size_hint=(0.3, 1),
            background_color=(0.2, 0.5, 0.8, 1),
            background_normal='',
            font_size='16sp',
            bold=True
        )

        # Привязываем callback
        if send_callback:
            self.send_button.bind(on_press=send_callback)

        self.add_widget(self.input_field)
        self.add_widget(self.send_button)

    def get_text(self):
        """Возвращает текст из поля ввода и очищает его"""
        text = self.input_field.text.strip()
        self.input_field.text = ""
        return text

    def set_text(self, text):
        """Устанавливает текст в поле ввода"""
        self.input_field.text = text