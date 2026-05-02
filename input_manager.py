from kivy.core.window import Window
from kivy.app import App
from collections import defaultdict
import json
import os

class HotkeyManager:
    """Менеджер горячих клавиш"""

    def __init__(self):
        self.hotkeys_file = 'hotkeys.json'
        self.hotkeys = defaultdict(list)
        self._load_hotkeys()
        self._setup_default_hotkeys()

    def _setup_default_hotkeys(self):
        """Устанавливает горячие клавиши по умолчанию"""
        default_hotkeys = {
            'end_turn': ['enter', 'space'],
            'save_game': ['ctrl+s'],
            'load_game': ['ctrl+l'],
            'toggle_fullscreen': ['f11'],
            'toggle_music': ['m'],
            'toggle_sfx': ['s'],
            'open_diplomacy': ['d'],
            'open_army': ['a'],
            'open_buildings': ['b'],
            'open_resources': ['r'],
            'zoom_in': ['+', 'equals'],
            'zoom_out': ['-', 'minus'],
            'reset_zoom': ['0'],
            'help': ['f1'],
            'settings': ['f2'],
            'quit': ['ctrl+q', 'escape']
        }

        # Добавляем только если не установлены пользователем
        for action, keys in default_hotkeys.items():
            if action not in self.hotkeys:
                self.hotkeys[action] = keys

    def _load_hotkeys(self):
        """Загружает пользовательские горячие клавиши"""
        try:
            if os.path.exists(self.hotkeys_file):
                with open(self.hotkeys_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for action, keys in data.items():
                        self.hotkeys[action] = keys
        except Exception as e:
            print(f"Ошибка загрузки горячих клавиш: {e}")

    def _save_hotkeys(self):
        """Сохраняет горячие клавиши"""
        try:
            with open(self.hotkeys_file, 'w', encoding='utf-8') as f:
                json.dump(dict(self.hotkeys), f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения горячих клавиш: {e}")

    def register_hotkey(self, action, key_combination):
        """Регистрирует горячую клавишу"""
        if action not in self.hotkeys:
            self.hotkeys[action] = []
        if key_combination not in self.hotkeys[action]:
            self.hotkeys[action].append(key_combination)
            self._save_hotkeys()

    def unregister_hotkey(self, action, key_combination):
        """Удаляет горячую клавишу"""
        if action in self.hotkeys and key_combination in self.hotkeys[action]:
            self.hotkeys[action].remove(key_combination)
            self._save_hotkeys()

    def get_hotkeys_for_action(self, action):
        """Возвращает горячие клавиши для действия"""
        return self.hotkeys.get(action, [])

    def get_all_hotkeys(self):
        """Возвращает все горячие клавиши"""
        return dict(self.hotkeys)

    def check_hotkey(self, key_combination, action):
        """Проверяет, соответствует ли комбинация клавиш действию"""
        return key_combination in self.hotkeys.get(action, [])

    def get_action_for_hotkey(self, key_combination):
        """Возвращает действие для комбинации клавиш"""
        for action, keys in self.hotkeys.items():
            if key_combination in keys:
                return action
        return None


class SettingsManager:
    """Менеджер настроек игры"""

    def __init__(self):
        self.settings_file = 'game_settings.json'
        self.settings = self._load_settings()

    def _load_settings(self):
        """Загружает настройки"""
        default_settings = {
            'audio': {
                'music_enabled': True,
                'sfx_enabled': True,
                'music_volume': 0.5,
                'sfx_volume': 0.7
            },
            'video': {
                'fullscreen': False,
                'resolution': 'auto',
                'vsync': True,
                'theme': 'light'
            },
            'gameplay': {
                'autosave': True,
                'autosave_interval': 5,  # минут
                'difficulty': 'normal',
                'tutorial_enabled': True,
                'tooltips_enabled': True
            },
            'controls': {
                'mouse_sensitivity': 1.0,
                'scroll_speed': 1.0,
                'hotkeys_enabled': True
            },
            'language': 'ru'
        }

        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                    self._deep_update(default_settings, loaded_settings)
        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")

        return default_settings

    def _deep_update(self, base_dict, update_dict):
        """Рекурсивно обновляет словарь"""
        for key, value in update_dict.items():
            if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

    def _save_settings(self):
        """Сохраняет настройки"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения настроек: {e}")

    def get_setting(self, category, key):
        """Возвращает настройку"""
        return self.settings.get(category, {}).get(key)

    def set_setting(self, category, key, value):
        """Устанавливает настройку"""
        if category not in self.settings:
            self.settings[category] = {}
        self.settings[category][key] = value
        self._save_settings()
        self._apply_setting(category, key, value)

    def _apply_setting(self, category, key, value):
        """Применяет настройку"""
        from theme_manager import theme_manager
        from audio_manager import audio_manager

        if category == 'audio':
            if key == 'music_enabled':
                audio_manager.music_enabled = value
            elif key == 'sfx_enabled':
                audio_manager.sfx_enabled = value
            elif key == 'music_volume':
                audio_manager.set_music_volume(value)
            elif key == 'sfx_volume':
                audio_manager.set_sfx_volume(value)

        elif category == 'video':
            if key == 'theme':
                theme_manager.set_theme(value)
            elif key == 'fullscreen':
                Window.fullscreen = value

    def get_all_settings(self):
        """Возвращает все настройки"""
        return self.settings.copy()

    def reset_to_defaults(self):
        """Сбрасывает настройки к умолчанию"""
        if os.path.exists(self.settings_file):
            os.remove(self.settings_file)
        self.settings = self._load_settings()
        self._save_settings()


class InputHandler:
    """Обработчик ввода с поддержкой горячих клавиш"""

    def __init__(self, hotkey_manager, settings_manager):
        self.hotkey_manager = hotkey_manager
        self.settings_manager = settings_manager
        self.key_modifiers = set()
        self._setup_keyboard_handlers()

    def _setup_keyboard_handlers(self):
        """Настраивает обработчики клавиатуры"""
        Window.bind(on_key_down=self._on_key_down)
        Window.bind(on_key_up=self._on_key_up)

    def _on_key_down(self, window, key, scancode, codepoint, modifier):
        """Обработчик нажатия клавиши"""
        if not self.settings_manager.get_setting('controls', 'hotkeys_enabled'):
            return

        # Отслеживаем модификаторы
        if modifier:
            self.key_modifiers.update(modifier)

        # Формируем комбинацию клавиш
        key_combination = self._format_key_combination(key, modifier)

        # Проверяем горячую клавишу
        action = self.hotkey_manager.get_action_for_hotkey(key_combination)
        if action:
            self._execute_action(action)

    def _on_key_up(self, window, key, scancode):
        """Обработчик отпускания клавиши"""
        # Очищаем модификаторы при отпускании
        key_name = self._get_key_name(key)
        if key_name in ['lctrl', 'rctrl', 'lalt', 'ralt', 'lshift', 'rshift']:
            self.key_modifiers.discard(key_name)

    def _format_key_combination(self, key, modifiers):
        """Форматирует комбинацию клавиш"""
        key_name = self._get_key_name(key)
        if not modifiers:
            return key_name

        # Сортируем модификаторы для консистентности
        sorted_modifiers = sorted(modifiers)
        return '+'.join(sorted_modifiers + [key_name])

    def _get_key_name(self, key):
        """Возвращает имя клавиши"""
        # Специальные клавиши
        special_keys = {
            13: 'enter',
            32: 'space',
            27: 'escape',
            9: 'tab',
            8: 'backspace',
            127: 'delete',
            276: 'left',
            275: 'right',
            274: 'down',
            273: 'up',
            278: 'home',
            279: 'end',
            280: 'pageup',
            281: 'pagedown',
            282: 'f1',
            283: 'f2',
            284: 'f3',
            285: 'f4',
            286: 'f5',
            287: 'f6',
            288: 'f7',
            289: 'f8',
            290: 'f9',
            291: 'f10',
            292: 'f11',
            293: 'f12'
        }

        if key in special_keys:
            return special_keys[key]

        # Буквенно-цифровые клавиши
        try:
            return chr(key).lower()
        except ValueError:
            return f'key_{key}'

    def _execute_action(self, action):
        """Выполняет действие горячей клавиши"""
        app = App.get_running_app()
        if not app:
            return

        # Словарь действий
        actions = {
            'end_turn': lambda: self._end_turn(app),
            'save_game': lambda: self._save_game(app),
            'load_game': lambda: self._load_game(app),
            'toggle_fullscreen': lambda: self._toggle_fullscreen(),
            'toggle_music': lambda: self._toggle_music(),
            'toggle_sfx': lambda: self._toggle_sfx(),
            'help': lambda: self._show_help(),
            'settings': lambda: self._show_settings(),
            'quit': lambda: self._quit_game()
        }

        if action in actions:
            actions[action]()

    def _end_turn(self, app):
        """Завершает ход"""
        if hasattr(app, 'end_turn'):
            app.end_turn()

    def _save_game(self, app):
        """Сохраняет игру"""
        if hasattr(app, 'save_game'):
            app.save_game()

    def _load_game(self, app):
        """Загружает игру"""
        if hasattr(app, 'load_game'):
            app.load_game()

    def _toggle_fullscreen(self):
        """Переключает полноэкранный режим"""
        Window.fullscreen = not Window.fullscreen

    def _toggle_music(self):
        """Переключает музыку"""
        from audio_manager import audio_manager
        audio_manager.toggle_music()

    def _toggle_sfx(self):
        """Переключает звуки"""
        from audio_manager import audio_manager
        audio_manager.toggle_sfx()

    def _show_help(self):
        """Показывает справку"""
        # TODO: Реализовать показ справки
        pass

    def _show_settings(self):
        """Показывает настройки"""
        # TODO: Реализовать показ настроек
        pass

    def _quit_game(self):
        """Выходит из игры"""
        App.get_running_app().stop()


# Глобальные экземпляры
hotkey_manager = HotkeyManager()
settings_manager = SettingsManager()
input_handler = InputHandler(hotkey_manager, settings_manager)</content>
<parameter name="filePath">c:\Users\lerdo\Desktop\AI\Lerdon_2\input_manager.py