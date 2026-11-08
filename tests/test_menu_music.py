import hashlib
import json
from pathlib import Path
import struct
import unittest
import wave
from game_audio import AudioManager
from music_catalog import track_for,FACTIONS
from test_game_audio import Sound


class MenuMusicTests(unittest.TestCase):
    def manager(self):
        m=AudioManager(lambda path:Sound())
        self.addCleanup(m.close)
        return m

    def test_menu_has_a_separate_quiet_pcm_recording_and_original_score(self):
        path=track_for(scene='menu')
        metadata=json.loads(Path('files/music/menu.json').read_text(encoding='utf-8'))
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(digest,metadata['sha256'])
        self.assertLess(metadata['bpm'],70)
        self.assertLess(metadata['rms'],.075)
        self.assertGreater(metadata['rms'],.02)
        for faction in FACTIONS:
            for scene in ('background','battle'):
                self.assertNotEqual(digest,hashlib.sha256(track_for(faction,scene).read_bytes()).hexdigest())
        with wave.open(str(path)) as clip:
            self.assertEqual((clip.getnchannels(),clip.getsampwidth(),clip.getframerate()),(1,2,22050))
            self.assertGreater(clip.getnframes()/22050,100)
            self.assertEqual(struct.unpack('<h',clip.readframes(1))[0],0)
            clip.setpos(clip.getnframes()-1)
            self.assertEqual(struct.unpack('<h',clip.readframes(1))[0],0)
        score=json.loads(Path('assets/music/scores/menu.json').read_text(encoding='utf-8'))
        self.assertFalse(any(n['channel']==9 for n in score['notes']))

    def test_returning_from_campaign_or_battle_always_restores_menu_theme(self):
        m=self.manager();m.show_menu()
        self.assertEqual(m.music_path,track_for(scene='menu'))
        m.set_background('Вампиры')
        self.assertEqual(m.music_path,track_for('Вампиры'))
        owner=object();m.start_music(owner,'Вампиры')
        self.assertEqual(m.music_path,track_for('Вампиры','battle'))
        m.show_menu();menu=m.music_sound
        self.assertEqual(m.music_contexts,[])
        self.assertEqual(m.music_path,track_for(scene='menu'))
        m.stop_owner(owner)
        self.assertIs(m.music_sound,menu)
        self.assertEqual(menu.state,'play')

    def test_temporary_preview_battle_returns_to_menu_not_north_background(self):
        m=self.manager();m.show_menu();owner=object()
        m.start_music(owner,'Эльфы');m.stop_owner(owner)
        self.assertEqual(m.music_path,track_for(scene='menu'))

    def test_reopening_menu_does_not_restart_the_same_track(self):
        m=self.manager();m.show_menu();sound=m.music_sound
        m.show_menu();self.assertIs(m.music_sound,sound)


if __name__=='__main__':unittest.main()
