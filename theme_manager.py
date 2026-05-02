from kivy.app import App
from kivy.properties import StringProperty, DictProperty, ObjectProperty
from design_system import THEMES, TYPOGRAPHY

class ThemeManager:
    """Менеджер тем приложения"""

    def __init__(self):
        self.current_theme = 'light'
        self.themes = THEMES

    def set_theme(self, theme_name):
        """Устанавливает тему"""
        if theme_name in self.themes:
            self.current_theme = theme_name
            # Применяем тему ко всему приложению
            self._apply_theme()

    def get_theme(self):
        """Возвращает текущую тему"""
        return self.themes[self.current_theme]

    def toggle_theme(self):
        """Переключает между светлой и темной темой"""
        new_theme = 'dark' if self.current_theme == 'light' else 'light'
        self.set_theme(new_theme)

    def _apply_theme(self):
        """Применяет тему ко всем виджетам"""
        app = App.get_running_app()
        if app:
            # Обновляем корневой виджет
            root = app.root
            if root:
                self._update_widget_theme(root)

    def _update_widget_theme(self, widget):
        """Рекурсивно обновляет тему виджета"""
        # Обновляем цвета в зависимости от типа виджета
        if hasattr(widget, 'background_color'):
            # Логика обновления цветов
            pass

        # Рекурсивно для дочерних виджетов
        if hasattr(widget, 'children'):
            for child in widget.children:
                self._update_widget_theme(child)

# Глобальный экземпляр менеджера тем
theme_manager = ThemeManager()

class LocalizationManager:
    """Менеджер локализации"""

    def __init__(self):
        self.current_language = 'ru'
        self.translations = {
            'ru': {
                'resources': 'Ресурсы',
                'army': 'Армия',
                'diplomacy': 'Дипломатия',
                'buildings': 'Здания',
                'turn': 'Ход',
                'end_turn': 'Завершить ход',
                'save_game': 'Сохранить игру',
                'load_game': 'Загрузить игру',
                'settings': 'Настройки',
                'help': 'Помощь',
                'exit': 'Выход',
                'victory': 'Победа!',
                'defeat': 'Поражение...',
                'new_game': 'Новая игра',
                'continue_game': 'Продолжить',
                'tutorial': 'Обучение',
                'achievements': 'Достижения',
                'statistics': 'Статистика'
            },
            'en': {
                'resources': 'Resources',
                'army': 'Army',
                'diplomacy': 'Diplomacy',
                'buildings': 'Buildings',
                'turn': 'Turn',
                'end_turn': 'End Turn',
                'save_game': 'Save Game',
                'load_game': 'Load Game',
                'settings': 'Settings',
                'help': 'Help',
                'exit': 'Exit',
                'victory': 'Victory!',
                'defeat': 'Defeat...',
                'new_game': 'New Game',
                'continue_game': 'Continue',
                'tutorial': 'Tutorial',
                'achievements': 'Achievements',
                'statistics': 'Statistics'
            }
        }

    def set_language(self, language):
        """Устанавливает язык"""
        if language in self.translations:
            self.current_language = language

    def get_text(self, key):
        """Возвращает переведенный текст"""
        return self.translations[self.current_language].get(key, key)

    def get_available_languages(self):
        """Возвращает список доступных языков"""
        return list(self.translations.keys())

# Глобальный экземпляр менеджера локализации
localization_manager = LocalizationManager()</content>
<parameter name="filePath">c:\Users\lerdo\Desktop\AI\Lerdon_2\theme_manager.py