# ai_models/advisor_view.py
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.behaviors import ButtonBehavior
import os
import random
import sqlite3

from .diplomacy_chat import EnhancedDiplomacyChat
from .relations_manager import RelationsManager

def calculate_font_size():
    from kivy.utils import platform
    base_height = 360
    default_font_size = 14
    scale_factor = Window.height / base_height

    # Увеличиваем шрифт на Android
    if platform == 'android':
        scale_factor *= 1.5

    return max(14, int(default_font_size * scale_factor))


# Словарь для перевода названий
translation_dict = {
    "Север": "people",
    "Эльфы": "elfs",
    "Адепты": "adept",
    "Вампиры": "vampire",
    "Элины": "poly",
}


def transform_filename(file_path):
    path_parts = file_path.split('/')
    for i, part in enumerate(path_parts):
        for ru_name, en_name in translation_dict.items():
            if ru_name in part:
                path_parts[i] = part.replace(ru_name, en_name)
    transformed_path = '/'.join(path_parts)
    return transformed_path


reverse_translation_dict = {v: k for k, v in translation_dict.items()}


class ClickableImage(ButtonBehavior, Image):
    pass

class AdvisorView(FloatLayout):
    def __init__(self, faction, conn, game_screen_instance=None, preselect_faction=None, **kwargs):
        super(AdvisorView, self).__init__(**kwargs)

        self.faction = faction
        self.db_connection = conn
        self.cursor = self.db_connection.cursor()
        self.game_screen = game_screen_instance
        self.preselect_faction = preselect_faction

        # Инициализация менеджеров
        self.relations_manager = RelationsManager(self)
        self.diplomacy_chat = EnhancedDiplomacyChat(self, self.db_connection)

        # Цветовая тема интерфейса
        self.colors = {
            'background': (0.95, 0.95, 0.95, 1),
            'primary': (0.118, 0.255, 0.455, 1),
            'accent': (0.227, 0.525, 0.835, 1),
            'text': (1, 1, 1, 1),
            'card': (1, 1, 1, 1)
        }


        # Главное окно интерфейса - сразу открываем чат
        self.open_ai_chat_directly()

    def open_ai_chat_directly(self):
        """Открывает окно чата с ИИ при запуске"""
        # Создаем основной контейнер
        main_container = BoxLayout(
            orientation='vertical',
            size_hint=(1, 1),
            spacing=0,
            padding=0
        )

        # Создаем интерфейс чата через EnhancedDiplomacyChat
        chat_interface = self.create_chat_interface()
        main_container.add_widget(chat_interface)

        # ========== СОЗДАЕМ POPUP ==========
        background = f'files/sov/parlament/{translation_dict.get(self.faction)}_palace.jpg'
        if not os.path.exists(background):
            background = ''

        self.popup = Popup(
            title="Дипломатия",
            title_size=sp(17),
            title_align="center",
            title_color=(0.65, 0.88, 1, 1),
            content=main_container,
            size_hint=(0.95, 0.95),
            separator_color=(0.20, 0.55, 0.88, 0.6),
            background=background,
            auto_dismiss=False
        )

        # Кнопка закрытия
        close_button = Button(
            text="X",
            size_hint=(None, None),
            size=(dp(40), dp(40)),
            pos_hint={'right': 0.98, 'top': 0.98},
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1),
            font_size=sp(16),
            bold=True
        )
        with close_button.canvas.before:
            close_button._bc = Color(0.65, 0.18, 0.18, 1)
            close_button._br = RoundedRectangle(pos=close_button.pos, size=close_button.size, radius=[dp(10)])
        close_button.bind(
            pos=lambda i, v: setattr(i._br, 'pos', v),
            size=lambda i, v: setattr(i._br, 'size', v),
            on_press=self.close_window
        )
        main_container.add_widget(close_button)

        self.popup.open()

    def create_chat_interface(self):
        """Создает интерфейс чата с ИИ"""
        # Используем существующий метод из EnhancedDiplomacyChat
        return self.diplomacy_chat.create_diplomacy_interface()

    def close_window(self, instance):
        """Закрытие окна"""
        print("Метод close_window вызван.")
        if hasattr(self, 'popup') and self.popup:
            self.popup.dismiss()
        else:
            print("Ошибка: Попап не найден.")