from kivy.core.audio import SoundLoader
from kivy.clock import Clock
import os
import random

class AudioManager:
    """Менеджер аудио для игры"""

    def __init__(self):
        self.music_enabled = True
        self.sfx_enabled = True
        self.music_volume = 0.5
        self.sfx_volume = 0.7

        self.current_music = None
        self.sound_effects = {}

        # Загружаем звуковые эффекты
        self._load_sound_effects()

        # Музыкальные треки
        self.music_tracks = {
            'menu': ['menu_theme.mp3'],
            'game': ['game_theme1.mp3', 'game_theme2.mp3'],
            'battle': ['battle_theme.mp3'],
            'victory': ['victory_theme.mp3'],
            'defeat': ['defeat_theme.mp3']
        }

    def _load_sound_effects(self):
        """Загружает звуковые эффекты"""
        sfx_files = {
            'button_click': 'button_click.wav',
            'building_complete': 'building_complete.wav',
            'battle_start': 'battle_start.wav',
            'victory': 'victory.wav',
            'defeat': 'defeat.wav',
            'level_up': 'level_up.wav',
            'resource_gained': 'resource_gained.wav',
            'alliance_formed': 'alliance_formed.wav',
            'war_declared': 'war_declared.wav',
            'notification': 'notification.wav'
        }

        for sfx_name, filename in sfx_files.items():
            filepath = os.path.join('files', 'sounds', filename)
            if os.path.exists(filepath):
                sound = SoundLoader.load(filepath)
                if sound:
                    self.sound_effects[sfx_name] = sound

    def play_music(self, category, loop=True):
        """Воспроизводит музыку определенной категории"""
        if not self.music_enabled:
            return

        if category in self.music_tracks:
            track = random.choice(self.music_tracks[category])
            filepath = os.path.join('files', 'sounds', track)

            if os.path.exists(filepath):
                # Останавливаем текущую музыку
                if self.current_music:
                    self.current_music.stop()

                # Загружаем и воспроизводим новую
                self.current_music = SoundLoader.load(filepath)
                if self.current_music:
                    self.current_music.volume = self.music_volume
                    self.current_music.loop = loop
                    self.current_music.play()

    def stop_music(self):
        """Останавливает музыку"""
        if self.current_music:
            self.current_music.stop()
            self.current_music = None

    def play_sound(self, sound_name):
        """Воспроизводит звуковой эффект"""
        if not self.sfx_enabled:
            return

        if sound_name in self.sound_effects:
            sound = self.sound_effects[sound_name]
            sound.volume = self.sfx_volume
            sound.play()

    def set_music_volume(self, volume):
        """Устанавливает громкость музыки"""
        self.music_volume = max(0.0, min(1.0, volume))
        if self.current_music:
            self.current_music.volume = self.music_volume

    def set_sfx_volume(self, volume):
        """Устанавливает громкость эффектов"""
        self.sfx_volume = max(0.0, min(1.0, volume))

    def toggle_music(self):
        """Включает/выключает музыку"""
        self.music_enabled = not self.music_enabled
        if not self.music_enabled:
            self.stop_music()
        else:
            self.play_music('menu')  # Возобновляем музыку меню

    def toggle_sfx(self):
        """Включает/выключает звуковые эффекты"""
        self.sfx_enabled = not self.sfx_enabled

    def play_ui_sound(self, action_type):
        """Воспроизводит звук для UI действия"""
        sound_map = {
            'button': 'button_click',
            'build': 'building_complete',
            'battle': 'battle_start',
            'win': 'victory',
            'lose': 'defeat',
            'level': 'level_up',
            'resource': 'resource_gained',
            'alliance': 'alliance_formed',
            'war': 'war_declared',
            'notify': 'notification'
        }

        if action_type in sound_map:
            self.play_sound(sound_map[action_type])


class BackgroundMusicController:
    """Контроллер фоновой музыки"""

    def __init__(self, audio_manager):
        self.audio_manager = audio_manager
        self.current_context = None

    def update_context(self, context):
        """Обновляет музыкальный контекст"""
        if context != self.current_context:
            self.current_context = context
            self.audio_manager.play_music(context)

    def set_menu_music(self):
        """Устанавливает музыку меню"""
        self.update_context('menu')

    def set_game_music(self):
        """Устанавливает игровую музыку"""
        self.update_context('game')

    def set_battle_music(self):
        """Устанавливает музыку боя"""
        self.update_context('battle')

    def set_victory_music(self):
        """Устанавливает музыку победы"""
        self.update_context('victory')

    def set_defeat_music(self):
        """Устанавливает музыку поражения"""
        self.update_context('defeat')


# Глобальные экземпляры
audio_manager = AudioManager()
music_controller = BackgroundMusicController(audio_manager)</content>
<parameter name="filePath">c:\Users\lerdo\Desktop\AI\Lerdon_2\audio_manager.py