"""Small, optional audio service. No game database or background audio threads."""
import json
import logging
import math
from pathlib import Path
import time
from music_catalog import track_for

ROOT = Path(__file__).resolve().parent
EFFECTS = {name: ROOT/'files/sounds/effects'/f'{name}.wav' for name in (
    'click', 'step', 'rifle', 'bow', 'sword', 'hit', 'throw', 'explosion',
    'magic', 'frost', 'heal', 'monster', 'victory', 'defeat', 'build', 'coins')}
MUSIC = track_for('Север','background')
DEFAULTS = dict(enabled=True, effects=.65, music=.20)
LOG = logging.getLogger(__name__)
# SoundSDL2 plays WAV music on an ordinary mixer channel too. Reserve one of
# SDL_mixer's default eight channels for it rather than requesting nine voices.
# During a music overlap the effect budget drops to six automatically.
EFFECT_VOICES = 7
PRIORITY = dict(click=0, step=0, hit=1, explosion=3, build=4, coins=4, victory=5, defeat=5,music=6)
DEBOUNCE = dict(click=.045, step=.10, hit=.035, explosion=.035, coins=.12)
EFFECT_GAIN = dict(click=.48,step=.65,hit=.8,throw=.75,build=.82,coins=.68,victory=.85,defeat=.8)


def volume(value, default):
    try:
        number = float(value)
        return min(1., max(0., number)) if math.isfinite(number) else default
    except (ValueError, TypeError):
        return default


class AudioManager:
    """Eight mixer channels shared by effects and smoothly overlapping music."""
    def __init__(self, loader, settings_path=None, now=time.monotonic, schedule=None):
        self.loader, self.now = loader, now
        self.settings_path = Path(settings_path) if settings_path else None
        self.settings = dict(DEFAULTS)
        self.pool, self.failed, self.last_play = {}, set(), {}
        self.started, self.deadlines, self.retry_after = {}, {}, {}
        self.pause_reasons = set()
        self.music_sound = None
        self.music_owner = None
        self.music_contexts=[]
        self.background_faction=None
        self.background_scene='background'
        self.background_owner=object()
        self.music_path=None
        self.closed = False
        self.music_playback=None
        if schedule is not None:
            from music_playback import MusicPlayback
            self.music_playback=MusicPlayback(self._load,self._stop,schedule,now,self._reserve_music,
                lambda sound:setattr(self,'music_sound',sound))
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
        # Successful trades replace the release click regardless of Kivy callback order.
        if key == 'click' and now-self.last_play.get('coins', -100) < .12:
            return False
        if now < self.retry_after.get(key,0):
            return False
        if now-self.last_play.get(key, -100) < DEBOUNCE.get(key,0):
            return False
        try:
            if key == 'coins':
                for click, _ in self.pool.get('click', []):
                    self._stop(click)
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
            music_voices=self.music_playback.playing_count if self.music_playback else int(self.music_sound is not None and self.music_sound.state=='play')
            if len(playing)>=min(EFFECT_VOICES,8-music_voices) and not self._preempt(key,playing):
                return False
            pool[index] = (sound, owner)
            sound.volume = self.settings['effects']*EFFECT_GAIN.get(key,1)
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
        for effect,pool in self.pool.items():
            for sound, _ in pool:
                try:
                    sound.volume = self.settings['effects']*EFFECT_GAIN.get(effect,1) if self.settings['enabled'] else 0
                    if sound.volume <= 0:
                        self._stop(sound)
                except Exception:
                    pass
        self._sync_music()

    def _reserve_music(self,count):
        playing=[(name,clip) for name,clips in self.pool.items() for clip,_ in clips if clip.state=='play']
        while len(playing)>8-count:
            if not self._preempt('music',playing):break
            playing=[(name,clip) for name,clip in playing if clip.state=='play']

    def set_background(self,faction):
        self.background_faction=faction
        self.background_scene='background'
        if not self.music_contexts:self.music_owner=self.background_owner if faction is not None else None
        self._sync_music()

    def show_menu(self):
        self.music_contexts.clear()
        self.background_faction=None
        self.background_scene='menu'
        self.music_owner=self.background_owner
        self._sync_music()

    def start_music(self, owner, faction=None, scene='battle'):
        self.music_contexts=[item for item in self.music_contexts if item[0] is not owner]
        self.music_contexts.append((owner,faction or self.background_faction or 'Север',scene))
        self.music_owner = owner
        self._sync_music()

    def _sync_music(self):
        allowed = (not self.closed and not self.pause_reasons and self.music_owner is not None
                   and self.settings['enabled'] and self.settings['music'] > 0)
        faction,scene=(self.music_contexts[-1][1:] if self.music_contexts else (self.background_faction,self.background_scene))
        path=track_for(faction,scene) if allowed else None
        if self.music_playback is not None:
            immediate=bool(self.closed or self.pause_reasons or not self.settings['enabled'] or self.settings['music']<=0)
            self.music_path=path
            self.music_playback.request(path,self.settings['music'],immediate=immediate)
            return
        if not allowed:
            if self.music_sound is not None:
                self._stop(self.music_sound)
            return
        if self.music_path!=path:
            if self.music_sound is not None:self._stop(self.music_sound,unload=True)
            self.music_sound=None
            self.music_path=path
        if self.music_sound is None:
            self.music_sound = self._load('music:'+path.stem, path)
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
                self.failed.add('music:'+path.stem)

    def stop_owner(self, owner):
        for pool in self.pool.values():
            for index, (sound, source) in enumerate(pool):
                if source is owner:
                    self._stop(sound)
                    pool[index] = (sound, None)
        self.music_contexts=[item for item in self.music_contexts if item[0] is not owner]
        if self.music_owner is owner:
            self.music_owner = (self.music_contexts[-1][0] if self.music_contexts else
                                self.background_owner if self.background_faction is not None or self.background_scene=='menu' else None)
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
        self.music_contexts.clear()
        self.music_owner=None
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
            from kivy.clock import Clock
            app._game_audio = AudioManager(load_game_sound, Path(app.user_data_dir)/'audio-settings.json',schedule=Clock.schedule_interval)
        except Exception as error:
            LOG.warning('Audio backend unavailable: %s', error)
            app._game_audio = _silent
    return app._game_audio


def attack_sound(unit, role, ranged=True):
    image = str(unit.get('unit_image') or unit.get('image_path') or '').replace('\\', '/').lower()
    if not ranged and (role=='mage' or any(image.endswith(name) for name in ('people/predator.jpg','people/vlad.jpg'))):
        return 'hit'
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


def set_background_music(faction):
    from kivy.app import App
    if App.get_running_app() is not None:get_audio().set_background(faction)


def set_menu_music():
    from kivy.app import App
    if App.get_running_app() is not None:get_audio().show_menu()
