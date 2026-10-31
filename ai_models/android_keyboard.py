from kivy import platform
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.metrics import dp

class AndroidKeyboardHelper:
    """Помощник для адаптации интерфейса под Android клавиатуру"""

    def __init__(self, chat_instance):
        self.chat = chat_instance
        self.keyboard_height = 0
        self.original_padding = None
        self.keyboard_shown = False
        self._disposed = False
        self._scroll_event = None

        # Биндим события клавиатуры (только на Android)
        if platform == 'android':
            from jnius import autoclass
            from android import mActivity

            # Получаем контекст Android
            Context = autoclass('android.content.Context')
            self.input_method_manager = mActivity.getSystemService(
                Context.INPUT_METHOD_SERVICE
            )

            # Назначаем обработчики
            Window.bind(on_keyboard=self._on_keyboard)
            Window.bind(on_keyboard_height=self._on_keyboard_height)

    def _on_keyboard(self, window, keyboard_height, keyboard_width, *args, **kwargs):
        """Обработчик появления/скрытия клавиатуры"""
        # Используем только первые 3 аргумента, остальные игнорируем
        if keyboard_height > 0:
            self.keyboard_shown = True
            self.keyboard_height = keyboard_height
            self.adjust_for_keyboard(True, keyboard_height)
        else:
            self.keyboard_shown = False
            self.adjust_for_keyboard(False, 0)

    def _on_keyboard_height(self, window, height, *args, **kwargs):
        """Обработчик изменения высоты клавиатуры"""
        # Используем только первые 2 аргумента
        if height > 0:
            self.keyboard_height = height
            self.adjust_for_keyboard(True, height)

    def adjust_for_keyboard(self, shown, height):
        """Адаптирует интерфейс под клавиатуру"""
        if self._disposed or not hasattr(self.chat, 'chat_container') or not self.chat.chat_container:
            return

        if shown:
            # Сохраняем оригинальные отступы если еще не сохранены
            if self.original_padding is None:
                self.original_padding = self.chat.chat_container.padding[:]

            # Рассчитываем новую высоту с учетом клавиатуры
            # Преобразуем пиксели в dp для Kivy
            keyboard_dp = height / (Window.dpi / 160.0)

            # Устанавливаем нижний отступ равный высоте клавиатуры + небольшой запас
            new_padding = [
                self.original_padding[0],  # left
                self.original_padding[1],  # top
                self.original_padding[2],  # right
                keyboard_dp + dp(20)       # bottom (высота клавиатуры + запас)
            ]

            self.chat.chat_container.padding = new_padding

            # Прокручиваем чат вниз с задержкой
            self._queue_scroll()
        else:
            # Восстанавливаем оригинальные отступы
            if self.original_padding:
                self.chat.chat_container.padding = self.original_padding
                self.original_padding = None

            # Прокручиваем чат вниз
            self._queue_scroll()

    def _queue_scroll(self):
        if self._scroll_event:
            self._scroll_event.cancel()
        self._scroll_event = Clock.schedule_once(
            lambda dt: self.chat.scroll_chat_to_bottom() if not self._disposed else None, 0.1)

    def dispose(self):
        self._disposed = True
        if self._scroll_event:
            self._scroll_event.cancel()
            self._scroll_event = None
        Window.unbind(on_keyboard=self._on_keyboard, on_keyboard_height=self._on_keyboard_height)
        Window.softinput_mode = ''

    def is_keyboard_shown(self):
        """Проверяет, показана ли клавиатура"""
        return self.keyboard_shown
