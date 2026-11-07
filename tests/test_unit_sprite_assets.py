"""Check actual animation art, alpha, coverage and Android atlas dimensions."""
import hashlib
import json
from pathlib import Path
import unittest
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]/'files/army/animated'
STATES={'idle','walk','attack','hit','death'}


class UnitSpriteAssetTests(unittest.TestCase):
    def test_complete_roster_has_all_five_actions_without_missing_or_opaque_sheets(self):
        registry=json.loads((ROOT/'index.json').read_text(encoding='utf-8'))
        self.assertEqual(len(registry['characters']),73)
        self.assertEqual(len(registry['references']),73)
        for key,relative in registry['characters'].items():
            with self.subTest(character=key):
                path=ROOT/relative;data=json.loads(path.read_text(encoding='utf-8'))
                image_path=path.parent/data['image']
                self.assertEqual(hashlib.sha256(image_path.read_bytes()).hexdigest(),data['sha256'])
                with Image.open(image_path) as image:
                    self.assertEqual(image.mode,'RGBA')
                    self.assertLessEqual(max(image.size),2048)
                    histogram=image.getchannel('A').histogram()
                    self.assertGreater(sum(histogram[:11])/(image.width*image.height),.4)
                    self.assertEqual(set(data['animations']),STATES)
                    self.assertEqual(registry['references'][data['reference']],key)
                    for state,clip in data['animations'].items():
                        self.assertEqual(len(clip['frames']),6)
                        self.assertGreater(clip['fps'],0)
                        self.assertEqual(clip['loop'],state in ('idle','walk'))
                        drawings=set()
                        for frame in clip['frames']:
                            x,y,w,h=frame['rect']
                            self.assertGreater(w,0);self.assertEqual(w,h)
                            self.assertGreaterEqual(min(x,y),0)
                            self.assertLessEqual(x+w,image.width);self.assertLessEqual(y+h,image.height)
                            cut=image.crop((x,y,x+w,y+h))
                            alpha=cut.getchannel('A')
                            self.assertIsNotNone(alpha.point(lambda a:255 if a>48 else 0).getbbox())
                            edges=(alpha.crop((0,0,1,h)),alpha.crop((w-1,0,w,h)),
                                   alpha.crop((0,0,w,1)),alpha.crop((0,h-1,w,h)))
                            self.assertLess(max(sum(edge.histogram()[240:]) for edge in edges),8,
                                            (key,state,'opaque figure touches cell edge'))
                            drawings.add(hashlib.sha256(cut.tobytes()).digest())
                        self.assertEqual(len(drawings),6,(key,state,'duplicate drawn frames'))
