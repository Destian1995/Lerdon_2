import hashlib
import json
from pathlib import Path
import struct
import unittest
import wave

from game_audio import AudioManager
from music_catalog import FACTIONS,track_for
from test_game_audio import Sound


class FactionMusicTests(unittest.TestCase):
    def manager(self):
        self.loaded=[]
        def load(path):
            sound=Sound();sound.path=Path(path);self.loaded.append(sound);return sound
        m=AudioManager(load)
        self.addCleanup(m.close)
        return m

    def test_every_faction_has_two_distinct_compatible_non_silent_loop_tracks(self):
        catalog=json.loads(Path('files/music/catalog.json').read_text(encoding='utf-8'))['tracks']
        self.assertEqual(len(catalog),len(FACTIONS)*2)
        digests=set()
        for faction in FACTIONS:
            pair={t['scene']:t for t in catalog if t['faction']==faction}
            self.assertEqual(set(pair),{'background','battle'})
            self.assertGreater(pair['battle']['bpm'],pair['background']['bpm'])
            for scene,entry in pair.items():
                path=track_for(faction,scene)
                digest=hashlib.sha256(path.read_bytes()).hexdigest()
                self.assertEqual(digest,entry['sha256']);digests.add(digest)
                with wave.open(str(path)) as clip:
                    self.assertEqual((clip.getnchannels(),clip.getsampwidth(),clip.getframerate()),(1,2,22050))
                    self.assertAlmostEqual(clip.getnframes()/22050,entry['seconds'],places=3)
                    self.assertGreater(clip.getnframes()/22050,75)
                    first=struct.unpack('<h',clip.readframes(1))[0]
                    clip.setpos(clip.getnframes()-1);last=struct.unpack('<h',clip.readframes(1))[0]
                    self.assertEqual((first,last),(0,0))
                self.assertGreater(entry['rms'],.02)
                self.assertLess(entry['peak'],.9)
        self.assertEqual(len(digests),14)

    def test_battle_overrides_exploration_and_restores_faction_background(self):
        m=self.manager();m.set_background('Вампиры')
        background=m.music_sound
        self.assertEqual(background.path,track_for('Вампиры'))
        owner=object();m.start_music(owner,'Вампиры')
        battle=m.music_sound
        self.assertTrue(background.unloaded)
        self.assertEqual(battle.path,track_for('Вампиры','battle'))
        m.stop_owner(owner)
        self.assertTrue(battle.unloaded)
        self.assertEqual(m.music_sound.path,track_for('Вампиры'))
        self.assertEqual(sum(s.state=='play' for s in self.loaded),1)

    def test_changing_faction_in_background_is_applied_after_current_battle(self):
        m=self.manager();m.set_background('Север');owner=object()
        m.start_music(owner,'Север');battle=m.music_sound
        m.set_background('Нежить')
        self.assertIs(m.music_sound,battle)
        m.stop_owner(owner)
        self.assertEqual(m.music_sound.path,track_for('Нежить'))

    def test_nested_battle_windows_do_not_play_music_twice(self):
        m=self.manager();m.set_background('Эльфы')
        first,second=object(),object()
        m.start_music(first,'Эльфы');m.start_music(second,'Адепты')
        current=m.music_sound;m.stop_owner(first)
        self.assertIs(m.music_sound,current)
        m.stop_owner(second)
        self.assertEqual(m.music_sound.path,track_for('Эльфы'))
        self.assertEqual(sum(s.state=='play' for s in self.loaded),1)

    def test_pause_and_muting_do_not_lose_scene_or_start_another_music_voice(self):
        m=self.manager();m.set_background('Элины');owner=object()
        m.start_music(owner,'Элины')
        music=m.music_sound;m.pause('app');m.set('enabled',False)
        m.resume('app');self.assertEqual(music.state,'stop')
        m.set('enabled',True)
        self.assertIs(m.music_sound,music)
        self.assertEqual(music.state,'play')
        self.assertEqual(sum(s.state=='play' for s in self.loaded),1)

    def test_unknown_faction_and_scene_have_safe_catalog_defaults(self):
        self.assertEqual(track_for('Неизвестная','city'),track_for('Север','background'))


if __name__=='__main__':unittest.main()
