import unittest
from game_audio import AudioManager,EFFECT_GAIN
from test_game_audio import Sound


class Event:
    cancelled=False
    def cancel(self):self.cancelled=True


class MusicFadesTests(unittest.TestCase):
    def setUp(self):
        self.now=0.;self.sounds=[];self.events=[]
        def load(path):
            sound=Sound();sound.length=3.;self.sounds.append(sound);return sound
        def schedule(callback,interval):
            event=Event();self.events.append(event);return event
        self.audio=AudioManager(load,now=lambda:self.now,schedule=schedule)

    def tearDown(self):self.audio.close()

    def advance(self,seconds):
        steps=round(seconds/.05)
        for _ in range(steps):
            self.now+=.05
            self.audio.music_playback.tick(.05)

    def test_track_enters_softly_and_event_change_crossfades_then_unloads_old_audio(self):
        m=self.audio;m.set_background('Север');first=m.music_sound
        self.assertEqual(first.volume,0)
        self.advance(.35)
        self.assertGreater(first.volume,0);self.assertLess(first.volume,m.settings['music'])
        self.advance(.5);self.assertAlmostEqual(first.volume,m.settings['music'])
        owner=object();m.start_music(owner,'Вампиры');second=m.music_sound
        self.assertEqual(second.volume,0)
        self.assertEqual(m.music_playback.playing_count,2)
        self.advance(.35)
        self.assertGreater(second.volume,0);self.assertGreater(first.volume,0)
        self.advance(.5)
        self.assertTrue(first.unloaded);self.assertFalse(second.unloaded)
        self.assertEqual(m.music_playback.playing_count,1)

    def test_loop_starts_before_eof_and_crossfades_without_a_silent_gap(self):
        m=self.audio;m.set_background('Эльфы');first=m.music_sound
        self.advance(2.3)
        self.assertIsNot(m.music_sound,first)
        self.assertEqual(first.state,'play')
        self.assertEqual(m.music_playback.playing_count,2)
        self.advance(.85)
        self.assertTrue(first.unloaded)
        self.assertEqual(m.music_playback.playing_count,1)
        self.assertGreater(m.music_sound.volume,0)

    def test_effect_voice_budget_includes_both_crossfading_music_tracks(self):
        m=self.audio;m.set_background('Север');self.advance(.8)
        for key in ('click','rifle','bow','sword','hit','throw','magic'):self.assertTrue(m.play(key))
        m.start_music(object(),'Элины')
        effects=sum(s.state=='play' for clips in m.pool.values() for s,_ in clips)
        self.assertEqual(effects,6)
        self.assertEqual(m.music_playback.playing_count+effects,8)
        self.assertTrue(m.play('build'))
        self.assertLessEqual(m.music_playback.playing_count+sum(s.state=='play' for clips in m.pool.values() for s,_ in clips),8)

    def test_fast_scene_changes_keep_only_two_voices_and_shutdown_cancels_fades(self):
        m=self.audio
        for faction in ('Север','Эльфы','Элины','Адепты','Вампиры')*4:
            m.set_background(faction)
            self.assertLessEqual(m.music_playback.playing_count,2)
        m.close();self.advance(1)
        self.assertTrue(all(s.state=='stop' and s.unloaded for s in self.sounds))
        self.assertTrue(all(e.cancelled for e in self.events))

    def test_pause_mutes_immediately_and_resume_fades_in_without_old_tail(self):
        m=self.audio;m.set_background('Нежить');self.advance(.8)
        first=m.music_sound;m.pause('app')
        self.assertEqual(m.music_playback.playing_count,0)
        self.assertTrue(first.unloaded)
        m.resume('app')
        self.assertEqual(m.music_sound.volume,0)
        self.advance(.8);self.assertGreater(m.music_sound.volume,0)

    def test_event_without_background_fades_out_before_stopping(self):
        m=self.audio;owner=object();m.start_music(owner,'Север');self.advance(.8)
        sound=m.music_sound;m.stop_owner(owner)
        self.assertEqual(sound.state,'play')
        self.advance(.8)
        self.assertEqual(sound.state,'stop');self.assertTrue(sound.unloaded)

    def test_clearing_background_finishes_with_a_fade(self):
        m=self.audio;m.set_background('Север');self.advance(.8)
        sound=m.music_sound;m.set_background(None)
        self.assertEqual(sound.state,'play')
        self.advance(.8)
        self.assertTrue(sound.unloaded)
        self.assertEqual(m.music_playback.playing_count,0)

    def test_ui_tick_is_quieter_than_combat_and_stays_quiet_after_slider_change(self):
        m=self.audio;m.play('click');m.play('rifle')
        click=m.pool['click'][0][0];rifle=m.pool['rifle'][0][0]
        self.assertLess(click.volume,rifle.volume)
        m.set('effects',.4)
        self.assertAlmostEqual(click.volume,.4*EFFECT_GAIN['click'])


if __name__=='__main__':unittest.main()
