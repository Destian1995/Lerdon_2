import hashlib
import json
from pathlib import Path
import unittest
from PIL import Image
from mirror_city_visuals import city_scale,depth_order
from otherworld_themes import THEMES,image_path


class MirrorCityVisualTests(unittest.TestCase):
    def test_all_factions_have_seven_distinct_transparent_city_sprites(self):
        for faction,theme in THEMES.items():
            with self.subTest(faction=faction):
                base=Path('files/otherworld/themes')/theme['key']
                atlas=json.loads((base/'cities-v2.atlas').read_text())
                regions=atlas['cities-v2.png']
                self.assertEqual(set(regions),{'city_'+str(i) for i in range(1,8)})
                with Image.open(base/'cities-v2.png') as source:
                    self.assertEqual(source.mode,'RGBA')
                    hashes=set()
                    for name,(x,y,w,h) in regions.items():
                        self.assertGreaterEqual(x,0);self.assertGreaterEqual(y,0)
                        self.assertLessEqual(x+w,source.width);self.assertLessEqual(y+h,source.height)
                        crop=source.crop((x,source.height-y-h,x+w,source.height-y))
                        alpha=crop.getchannel('A')
                        self.assertIsNotNone(alpha.getbbox(),name)
                        self.assertEqual(alpha.getextrema()[0],0,name)
                        hashes.add(hashlib.sha256(crop.tobytes()).hexdigest())
                        self.assertIn('/cities-v2/'+name,image_path(faction,'cities',name))
                    self.assertEqual(len(hashes),7)

    def test_depth_is_presentation_only_and_near_cities_are_larger(self):
        nodes=[dict(id=1,y=100),dict(id=2,y=600),dict(id=3,y=300)]
        self.assertEqual([c['id'] for c in depth_order(nodes)],[2,3,1])
        self.assertEqual([c['id'] for c in nodes],[1,2,3])
        for city in range(1,8):
            self.assertGreater(city_scale(city,100),city_scale(city,700))


if __name__=='__main__':unittest.main()
