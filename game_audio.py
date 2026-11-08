"""Small, optional audio service. No game database or background audio threads."""
import json
import logging
import math
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parent
EFFECTS = {name: ROOT/'files/sounds/effects'/f'{name}.wav' for name in (
    'click', 'step', 'rifle', 'bow', 'sword', 'hit', 'throw', 'explosion',
    'magic', 'frost', 'heal', 'monster', 'victory', 'defeat', 'build')}
MUSIC = ROOT/'files/sounds/battle_theme.wav'
DEFAULTS = dict(enabled=True, effects=.65, music=.20)
LOG = logging.getLogger(__name__)
# SoundSDL2 plays WAV music on an ordinary mixer channel too. Reserve one of
# SDL_mixer's default eight channels for it rather than requesting nine voices.
EFFECT_VOICES = 7
PRIORITY = dict(click=0, step=0, hit=1, explosion=3, build=4, victory=5, defeat=5)
DEBOUNCE = dict(click=.045, step=.10, hit=.035, explosion=.035)


def volume(value, default):
    try:
        number = float(value)
        return min(1., max(0., number)) if math.isfinite(number) else default
    except (ValueError, TypeError):
        return default


class AudioManager:
    """Seven effect voices plus music; important events replace quieter effects."""
    def __init__(self, loader, settings_path=None, now=time.monotonic):
        self.loader, self.now = loader, now
        self.settings_path = Path(settings_path) if settings_path else None
        self.settings = dict(DEFAULTS)
        self.pool, self.failed, self.last_play = {}, set(), {}
        self.started, self.deadlines, self.retry_after = {}, {}, {}
        self.pause_reasons = set()
        self.music_sound = None
        self.music_owner = None
        self.closed = False
        if self.settings_path:
            try:
                data = json.loads(self.settings_path.read_text(encoding='utf-8'))
                if isinstance(data, dict):
                    self.settings.update(enabled=data.get('enabled', True) is True,
                        effects=volume(data.get('effects'), DEFAULTS['effects']),
                        music=volume(data.get('music'), DEFAULTS['music']))
            except (OSError, ValueError):
                pass

    def save(self):
        if not self.settings_path:
            return True
        try:
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.settings_path.with_suffix('.tmp')
            temporary.write_text(json.dumps(self.settings), encoding='utf-8')
            temporary.replace(self.settings_path)
            return True
        except OSError as error:
            LOG.warning('Audio settings could not be saved: %s', error)
            return False

    def _load(self, key, path):
        if key in self.failed:
            return None
        try:
            sound = self.loader(str(path)) if path.is_file() else None
            if sound is not None:
                if getattr(sound,'length',1) <= 0:
                    self._stop(sound,unload=True)
                    self.failed.add(key)
                    return None
                return sound
        except Exception as error:
            LOG.warning('Audio unavailable for %s: %s', key, error)
        self.failed.add(key)
        return None

    @staticmethod
    def _stop(sound, unload=False):
        try:
            sound.stop()
            if unload:
                sound.unload()
        except Exception:
            pass

    def play(self, key, owner=None):
        if (self.closed or self.pause_reasons or not self.settings['enabled']
                or self.settings['effects'] <= 0 or key not in EFFECTS or key in self.failed):
            return False
        now = self.now()
        if now < self.retry_after.get(key,0):
            return False
        if now-self.last_play.get(key, -100) < DEBOUNCE.get(key,0):
            return False
        try:
            # Kivy polls completed clips every 100 ms. A stalled UI can leave
            # stale 'play' states behind; don't count these forever as occupied.
            for clips in self.pool.values():
                for sound, _ in clips:
                    if now >= self.deadlines.get(id(sound),float('inf')):
                        self._stop(sound)
                        self.deadlines.pop(id(sound),None)
            pool = self.pool.setdefault(key, [])
            index = next((i for i, (sound, _) in enumerate(pool) if sound.state!='play'), None)
            if index is None:
                if len(pool) >= 2:
                    index=min(range(len(pool)),key=lambda i:self.started.get(id(pool[i][0]),0))
                    self._stop(pool[index][0])
                else:
                    sound = self._load(key, EFFECTS[key])
                    if sound is None:
                        return False
                    index = len(pool)
                    pool.append((sound, owner))
            sound = pool[index][0]
            playing=[(name,clip) for name,clips in self.pool.items() for clip,_ in clips if clip.state=='play']
            if len(playing)>=EFFECT_VOICES and not self._preempt(key,playing):
                return False
            pool[index] = (sound, owner)
            sound.volume = self.settings['effects']
            sound.play()
            # SDL2 returns silently when no native channel is available.
            # Checking state prevents us from reporting a dropped sound as played.
            if sound.state!='play':
                playing=[(name,clip) for name,clips in self.pool.items() for clip,_ in clips if clip.state=='play']
                if self._preempt(key,playing):sound.play()
                if sound.state!='play':return False
            self.started[id(sound)]=now
            length=float(getattr(sound,'length',0) or 0)
            if length>0:self.deadlines[id(sound)]=now+length+.15
            self.last_play[key] = now
            return True
        except Exception as error:
            LOG.warning('Audio effect %s temporarily unavailable: %s', key, error)
            self.retry_after[key]=now+1
            for sound, _ in self.pool.pop(key, []):
                self._stop(sound, unload=True)
                self.started.pop(id(sound),None);self.deadlines.pop(id(sound),None)
            return False

    def _preempt(self,key,playing):
        candidates=[(name,sound) for name,sound in playing
                    if PRIORITY.get(name,2)<=PRIORITY.get(key,2)]
        if not candidates:return False
        _,sound=min(candidates,key=lambda pair:(PRIORITY.get(pair[0],2),self.started.get(id(pair[1]),0)))
        self._stop(sound)
        self.deadlines.pop(id(sound),None)
        return True

    def set(self, key, value):
        if key not in DEFAULTS:
            raise ValueError(key)
        self.settings[key] = bool(value) if key=='enabled' else volume(value, DEFAULTS[key])
        for pool in self.pool.values():
            for sound, _ in pool:
                try:
                    sound.volume = self.settings['effects'] if self.settings['enabled'] else 0
                    if sound.volume <= 0:
                        self._stop(sound)
                except Exception:
                    pass
        self._sync_music()

    def start_music(self, owner):
        self.music_owner = owner
        self._sync_music()

    def _sync_music(self):
        allowed = (not self.closed and not self.pause_reasons and self.music_owner is not None
                   and self.settings['enabled'] and self.settings['music'] > 0)
        if not allowed:
            if self.music_sound is not None:
                self._stop(self.music_sound)
            return
        if self.music_sound is None:
            self.music_sound = self._load('music', MUSIC)
        if self.music_sound is not None:
            try:
                self.music_sound.volume = self.settings['music']
                self.music_sound.loop = True
                if self.music_sound.state != 'play':
                    self.music_sound.play()
            except Exception as error:
                LOG.warning('Music disabled: %s', error)
                self._stop(self.music_sound, unload=True)
                self.music_sound = None
                self.failed.add('music')

    def stop_owner(self, owner):
        for pool in self.pool.values():
            for index, (sound, source) in enumerate(pool):
                if source is owner:
                    self._stop(sound)
                    pool[index] = (sound, None)
        if self.music_owner is owner:
            self.music_owner = None
            self._sync_music()

    def pause(self, reason='app'):
        self.pause_reasons.add(reason)
        for pool in self.pool.values():
            for sound, _ in pool:
                self._stop(sound)
        self._sync_music()

    def resume(self, reason='app'):
        self.pause_reasons.discard(reason)
        self._sync_music()  # Old one-shot effects are never replayed.

    def close(self):
        self.closed = True
        self.pause()
        for pool in self.pool.values():
            for sound, _ in pool:
                self._stop(sound, unload=True)
        self.pool.clear()
        self.started.clear();self.deadlines.clear()
        if self.music_sound is not None:
            self._stop(self.music_sound, unload=True)
            self.music_sound = None


_silent = AudioManager(lambda path: None)


def load_game_sound(path):
    """Pin PCM playback even if another module already registered SoundFFPy.

    SoundLoader prefers ffpyplayer when installed. Its FFmpeg filter graph can
    fail asynchronously on a channel-layout change, beyond play()'s try/except.
    Our packaged WAVs use SDL2_mixer directly, on both desktop and Android.
    """
    from kivy.core.audio.audio_sdl2 import SoundSDL2
    return SoundSDL2(source=path)


def get_audio():
    from kivy.app import App
    app = App.get_running_app()
    if app is None:
        return _silent
    if not hasattr(app, '_game_audio'):
        try:
            app._game_audio = AudioManager(load_game_sound, Path(app.user_data_dir)/'audio-settings.json')
        except Exception as error:
            LOG.warning('Audio backend unavailable: %s', error)
            app._game_audio = _silent
    return app._game_audio


def attack_sound(unit, role, ranged=True):
    image = str(unit.get('unit_image') or unit.get('image_path') or '').replace('\\', '/').lower()
    if ranged and any(image.endswith(name) for name in ('people/predator.jpg', 'people/vlad.jpg')):
        return 'rifle'
    if role in ('mage', 'siege'):
        return 'magic' if role=='mage' else 'explosion'
    if role=='beast':
        return 'monster'
    return 'bow' if ranged and role=='archer' else 'sword'


def play_effect(key):
    """Notify a successful player action, scheduling audio on the UI thread."""
    from kivy.app import App
    from threading import current_thread, main_thread
    app=App.get_running_app()
    if app is None:return False
    if current_thread() is not main_thread():
        from kivy.clock import Clock
        Clock.schedule_once(lambda dt: get_audio().play(key) if App.get_running_app() is app else None,0)
        return True
    return get_audio().play(key)


def bind_button_sound(button):
    """Legacy and new buttons share one click callback, including image buttons."""
    if getattr(button,'_game_audio_bound',False):return
    def click(widget,*args):
        if not widget.disabled:get_audio().play('click')
    button.bind(on_release=click)
    button._game_audio_bound=True
