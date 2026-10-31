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
from kivy.clock import Clock
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
        self._strategy_no_theme = True
        self._closed = False

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
        self.popup.bind(on_dismiss=self._dispose)

        # Кнопка закрытия
        close_button = Button(
            text="X",
            size_hint=(None, None),
            size=(dp(48), dp(48)),
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
            on_release=self.close_window
        )
        from strategy_ui import text_label, GOLD
        from window_theme import prepare_custom_popup, theme_tree
        header = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        header.add_widget(text_label('Дипломатия', 18, GOLD, bold=True))
        header.add_widget(close_button)
        main_container.padding = dp(10)
        main_container.spacing = dp(8)
        main_container.add_widget(header, index=len(main_container.children))
        prepare_custom_popup(self.popup)
        theme_tree(main_container)

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

    def _dispose(self, *args):
        if self._closed:
            return
        self._closed = True
        chat = getattr(self, 'diplomacy_chat', None)
        try:
            if chat is not None and hasattr(chat, 'dispose'):
                chat.dispose()
        finally:
            # Remove the owner after Popup finishes dispatching its dismissal.
            Clock.schedule_once(self._remove_owner, 0)

    def _remove_owner(self, *args):
        if self.parent:
            self.parent.remove_widget(self)

    def on_parent(self, widget, parent):
        # Dismissal can occur before the owner is added to game_area.
        if parent is not None and getattr(self, '_closed', False):
            parent.remove_widget(self)
