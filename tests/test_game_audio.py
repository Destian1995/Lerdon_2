import ast
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave

from game_audio import AudioManager, EFFECTS, attack_sound


class Sound:
    def __init__(self):
        self.state='stop';self.volume=1;self.loop=False;self.unloaded=False
    def play(self):self.state='play'
    def stop(self):self.state='stop'
    def unload(self):self.unloaded=True


class AudioTests(unittest.TestCase):
    def test_startup_selects_sdl2_before_any_kivy_import(self):
        # Execute only the real startup preamble, without opening the game DB.
        tree=ast.parse(Path('main.py').read_text(encoding='utf-8'))
        preamble=[]
        for node in tree.body:
            if isinstance(node,ast.ImportFrom):break
            preamble.append(node)
        with patch.dict('os.environ',{'KIVY_AUDIO':'ffpyplayer'}):
            namespace={}
            exec(compile(ast.Module(body=preamble,type_ignores=[]),'main.py','exec'),namespace)
            self.assertEqual(namespace['os'].environ['KIVY_AUDIO'],'sdl2')

    def test_game_loader_ignores_ffpyplayer_even_if_it_was_registered_first(self):
        from game_audio import load_game_sound
        from kivy.core.audio import SoundLoader
        class BrokenFFPy:
            @staticmethod
            def extensions():return ['wav']
            def __init__(self,**kwargs):raise AssertionError('FFPy audio must not start')
        with patch.object(SoundLoader,'_classes',[BrokenFFPy]+SoundLoader._classes):
            sound=load_game_sound(str(EFFECTS['victory']))
            self.addCleanup(sound.unload)
            self.assertEqual(type(sound).__name__,'SoundSDL2')
            self.assertGreater(sound.length,0)
            sound.volume=0;sound.play()
            self.assertEqual(sound.state,'play')
            sound.stop()

    def manager(self, **kwargs):
        self.now=0
        self.loaded=[]
        def load(path):
            sound=Sound();self.loaded.append(sound);return sound
        return AudioManager(load,now=lambda:self.now,**kwargs)

    def test_pcm_assets_are_non_silent_not_clipped_and_packaged_for_android(self):
        for path in EFFECTS.values():
            with wave.open(str(path)) as clip:
                self.assertEqual((clip.getnchannels(),clip.getsampwidth(),clip.getframerate()),(1,2,22050))
                samples=struct.unpack('<'+'h'*clip.getnframes(),clip.readframes(clip.getnframes()))
            self.assertGreater(max(abs(v) for v in samples),1000)
            self.assertLess(max(abs(v) for v in samples),30000)
            self.assertEqual(samples[0],0)
            self.assertLess(abs(samples[-1]),150)
        spec=Path('buildozer.spec').read_text(encoding='utf-8')
        extensions=next(line.split('=',1)[1] for line in spec.splitlines() if line.startswith('source.include_exts'))
        self.assertIn('wav',extensions.split(','))

    def test_music_and_effects_fit_native_channels_and_construction_replaces_click(self):
        loaded=[]
        class NativeSound(Sound):
            def play(self):
                if sum(s.state=='play' for s in loaded)>=8:
                    raise AssertionError('SDL2 mixer channels exhausted')
                super().play()
        def load(path):
            sound=NativeSound();loaded.append(sound);return sound
        m=AudioManager(load)
        self.addCleanup(m.close)
        m.start_music(self)
        for key in ('click','rifle','bow','sword','hit','throw','magic'):
            self.assertTrue(m.play(key))
        self.assertEqual(sum(s.state=='play' for s in loaded),8)
        self.assertTrue(m.play('build'))
        self.assertEqual(m.pool['click'][0][0].state,'stop')
        self.assertEqual(m.music_sound.state,'play')
        self.assertEqual(sum(s.state=='play' for s in loaded),8)
        self.assertTrue(m.play('victory'))
        self.assertEqual(sum(s.state=='play' for s in loaded),8)

    def test_rapid_repeated_weapon_actions_retrigger_instead_of_dropping_every_third(self):
        m=self.manager()
        for _ in range(30):
            self.assertTrue(m.play('rifle'))
            self.now+=.01
        self.assertEqual(len(m.pool['rifle']),2)

    def test_trade_coins_replace_click_in_either_callback_order(self):
        m=self.manager()
        self.assertTrue(m.play('click'))
        self.assertTrue(m.play('coins'))
        self.assertEqual(m.pool['click'][0][0].state,'stop')
        self.assertFalse(m.play('click'))
        self.assertFalse(m.play('coins'))
        self.now+=.2
        self.assertTrue(m.play('click'))
        m.set('enabled',False)
        self.assertFalse(m.play('coins'))

    def test_quiet_click_does_not_interrupt_a_full_set_of_important_sounds(self):
        m=self.manager()
        for key in ('rifle','bow','sword','magic','heal','build','victory'):
            self.assertTrue(m.play(key))
        self.assertFalse(m.play('click'))
        self.assertTrue(m.play('explosion'))

    def test_finished_clips_are_reclaimed_even_if_backend_state_callback_is_late(self):
        m=self.manager();self.assertTrue(m.play('rifle'))
        sound=m.pool['rifle'][0][0];sound.length=.1
        self.now=.1;self.assertTrue(m.play('rifle'))
        self.now=1
        self.assertTrue(m.play('rifle'))
        self.assertLessEqual(sum(s.state=='play' for clips in m.pool.values() for s,_ in clips),2)

    def test_simultaneous_area_hits_are_debounced(self):
        m=self.manager()
        for _ in range(20):m.play('explosion')
        self.assertEqual(len(self.loaded),1)

    def test_mute_and_volume_update_active_sounds_immediately(self):
        m=self.manager();m.play('rifle');m.start_music(self)
        m.set('effects',.25);self.assertEqual(self.loaded[0].volume,.25)
        m.set('enabled',False)
        self.assertTrue(all(s.state=='stop' for s in self.loaded))
        self.assertFalse(m.play('rifle'))
        m.set('enabled',True)
        self.assertEqual(m.music_sound.state,'play')
        self.assertEqual(self.loaded[0].state,'stop')

    def test_pause_reasons_do_not_resume_music_or_old_shots_too_early(self):
        m=self.manager();m.play('rifle');m.start_music(self)
        m.pause('focus');m.pause('app')
        self.assertFalse(m.play('bow'))
        m.resume('focus');self.assertEqual(m.music_sound.state,'stop')
        m.resume('app');self.assertEqual(m.music_sound.state,'play')
        self.assertEqual(self.loaded[0].state,'stop')

    def test_close_battle_stops_only_its_sounds_and_releases_music(self):
        m=self.manager();owner=object()
        m.play('click');m.play('explosion',owner);m.start_music(owner)
        m.stop_owner(owner)
        self.assertEqual(self.loaded[0].state,'play')
        self.assertEqual(self.loaded[1].state,'stop')
        self.assertEqual(m.music_sound.state,'stop')
        self.assertFalse(any(source is owner for pool in m.pool.values() for _,source in pool))
        m.close();self.assertTrue(all(s.unloaded for s in self.loaded))
        self.assertFalse(m.play('rifle'))

    def test_missing_and_broken_backends_are_optional_and_not_retried_per_frame(self):
        for loader in (Mock(return_value=None),Mock(side_effect=RuntimeError('no device'))):
            m=AudioManager(loader)
            for _ in range(10):self.assertFalse(m.play('rifle'))
            for _ in range(10):m.start_music(self)
            self.assertEqual(loader.call_count,2)
        m=self.manager();self.assertFalse(m.play('unknown'))

    def test_playback_failure_unloads_clip_and_keeps_game_alive(self):
        sound=Sound();sound.play=Mock(side_effect=RuntimeError('device lost'))
        m=AudioManager(lambda path:sound)
        self.assertFalse(m.play('rifle'));self.assertTrue(sound.unloaded)
        self.assertFalse(m.play('rifle'))

    def test_transient_playback_error_can_recover_on_the_next_action(self):
        now=[0];sounds=[Sound(),Sound()]
        sounds[0].play=Mock(side_effect=RuntimeError('device lost'))
        m=AudioManager(lambda path:sounds.pop(0),now=lambda:now[0])
        self.assertFalse(m.play('build'))
        now[0]=1.1
        self.assertTrue(m.play('build'))

    def test_settings_round_trip_and_corrupt_settings_fallback_without_game_db(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'audio-settings.json'
            m=self.manager(settings_path=path);m.set('music',.1);m.set('enabled',False)
            self.assertTrue(m.save())
            n=AudioManager(lambda path:None,path)
            self.assertEqual(n.settings,m.settings)
            path.write_text('{broken',encoding='utf-8')
            self.assertTrue(AudioManager(lambda path:None,path).settings['enabled'])
            path.write_text(json.dumps(dict(effects=999,music=float('nan'))),encoding='utf-8')
            n=AudioManager(lambda path:None,path)
            self.assertEqual(n.settings['effects'],1)
            self.assertEqual(n.settings['music'],.2)

    def test_failed_settings_write_does_not_raise(self):
        m=self.manager(settings_path=Path('not-used.json'))
        with patch('pathlib.Path.write_text',side_effect=OSError('disk full')):
            self.assertFalse(m.save())

    def test_weapon_sounds_match_rifles_bows_magic_and_melee(self):
        self.assertEqual(attack_sound({'unit_image':'files/army/people/predator.jpg'},'archer'),'rifle')
        self.assertEqual(attack_sound({},'archer'),'bow')
        self.assertEqual(attack_sound({},'mage'),'magic')
        self.assertEqual(attack_sound({},'beast',False),'monster')
        self.assertEqual(attack_sound({},'archer',False),'sword')

    def test_real_app_lifecycle_hooks_pause_and_resume_audio(self):
        tree=ast.parse(Path('main.py').read_text(encoding='utf-8'))
        app=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Lerdon')
        methods=[n for n in app.body if isinstance(n,ast.FunctionDef) and n.name in ('on_pause','on_resume','_audio_focus')]
        namespace={}
        exec(compile(ast.Module(body=methods,type_ignores=[]),'main.py','exec'),namespace)
        cls=type('Lifecycle',(),{m.name:namespace[m.name] for m in methods})
        m=self.manager();obj=cls()
        with patch('game_audio.get_audio',return_value=m):
            self.assertTrue(obj.on_pause());obj._audio_focus(None,False)
            obj.on_resume();self.assertEqual(m.pause_reasons,{'focus'})
            obj._audio_focus(None,True);self.assertEqual(m.pause_reasons,set())


if __name__=='__main__':unittest.main()
