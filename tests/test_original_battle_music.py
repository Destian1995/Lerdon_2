"""The battle theme is an editable original score rather than a reference mix."""
import json
from pathlib import Path
import unittest
import wave

import numpy as np
from tools.compose_mirror_battle_music import compose
from music_catalog import BATTLE_THEME


class OriginalBattleMusicTests(unittest.TestCase):
    def test_score_is_original_deterministic_and_has_two_themes_and_a_dynamic_arc(self):
        a=compose();b=compose()
        self.assertEqual(a,b)
        self.assertTrue(a['original_composition']);self.assertFalse(a['uses_reference_audio'])
        self.assertEqual(a['bars'],72)
        self.assertGreater(len(a['notes']),1000)
        first=[n['note'] for n in a['notes'] if n['channel']==0 and 32<=n['beat']<64]
        second=[n['note'] for n in a['notes'] if n['channel']==0 and 96<=n['beat']<128]
        self.assertNotEqual(first,second)
        archived=json.loads(Path('assets/music/scores/battle_mirror_overture.json').read_text(encoding='utf-8'))
        self.assertEqual(archived,a)
        self.assertTrue(Path('assets/music/scores/battle_mirror_overture.mid').read_bytes().startswith(b'MThd'))

    def test_recording_has_real_dynamic_sections_and_clean_loop_edges(self):
        score=compose()
        with wave.open(str(BATTLE_THEME)) as clip:
            rate=clip.getframerate();audio=np.frombuffer(clip.readframes(clip.getnframes()),dtype='<i2').astype(float)/32768
        bar=4*60/score['bpm']
        intro=audio[:round(8*bar*rate)]
        climax=audio[round(48*bar*rate):round(64*bar*rate)]
        rms=lambda a:float(np.sqrt(np.mean(a*a)))
        self.assertGreater(rms(climax),rms(intro)*1.1)
        self.assertEqual((audio[0],audio[-1]),(0,0))
        self.assertFalse(Path('files/music/battle_chifang_mix.wav').exists())


if __name__=='__main__':unittest.main()
