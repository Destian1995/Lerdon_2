"""All playable Mirror appearances have six real animation clips and aliases."""
import hashlib
import json
from pathlib import Path
import unittest

from otherworld_content import unit_catalog
from otherworld_themes import THEMES,image_path

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'files/army/animated'


class MirrorCombatAssetTests(unittest.TestCase):
    def test_complete_mirror_roster_including_city_bosses_and_legacy_recruits(self):
        index=json.loads((ASSETS/'index.json').read_text(encoding='utf-8'))
        expected={f'mirror/{theme["key"]}/{kind}' for theme in THEMES.values()
                  for kind in ('sentinel','archer','rider','weaver','golem','boss')}
        expected|={f'mirror/common/{kind}' for kind in ('sentinel','archer','rider','weaver','golem')}
        actual={key for key in index['characters'] if key.startswith('mirror/')}
        self.assertEqual(actual,expected)
        for faction,theme in THEMES.items():
            for kind,row in zip(('sentinel','archer','rider','weaver','golem'),unit_catalog(faction)):
                key=f'mirror/{theme["key"]}/{kind}'
                self.assertEqual(index['references'][row['image_path']],key)
                legacy=f'atlas://files/otherworld/themes/{theme["key"]}/units/{kind}'
                self.assertEqual(index['references'][legacy],key)
            self.assertEqual(index['references'][image_path(faction,'units','boss')],f'mirror/{theme["key"]}/boss')
        for key in expected:
            path=ASSETS/index['characters'][key];data=json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(set(data['animations']),{'idle','walk','attack','hit','death','melee'})
            self.assertEqual(data['grid'],[6,6])
            self.assertEqual(data['facing'],'right')
            self.assertEqual(hashlib.sha256((path.parent/data['image']).read_bytes()).hexdigest(),data['sha256'])
            for clip in data['animations'].values():self.assertEqual(len(clip['frames']),6)


if __name__=='__main__':unittest.main()
