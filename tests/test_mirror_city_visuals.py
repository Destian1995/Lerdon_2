import hashlib
import json
from pathlib import Path
import unittest
from PIL import Image
from mirror_city_visuals import city_scale,depth_order
from otherworld_themes import THEMES,image_path,CITY_LAYOUTS


class MirrorCityVisualTests(unittest.TestCase):
    def test_harbors_are_at_reviewed_real_shores_instead_of_mountain_clearings(self):
        import math
        from tools.build_mirror_ambience import water_pixel
        # Reviewed pixels in the painted fjord, river, lake, river and oasis.
        shore_water={'north':(1080,175),'elves':(850,330),'vampires':(990,220),
                     'adepts':(95,96),'elines':(975,280)}
        for key,point in shore_water.items():
            with self.subTest(world=key):
                self.assertLess(math.dist(CITY_LAYOUTS[key][1],point),110)
                with Image.open(Path('files/otherworld/themes')/key/'map.png') as image:
                    rgb=image.convert('RGB').getpixel((int(point[0]/1200*image.width),int((1-point[1]/800)*image.height)))
                    self.assertTrue(water_pixel(key,rgb),(key,rgb))

    def test_marked_desert_and_vampire_areas_are_now_connected_water(self):
        from tools.build_mirror_ambience import water_pixel
        samples={'elines':((800,280),(820,270)),
                 'vampires':((820,250),(910,210))}
        for key,points in samples.items():
            with Image.open(Path('files/otherworld/themes')/key/'map.png') as image:
                image=image.convert('RGB')
                for x,y in points:
                    rgb=image.getpixel((int(x/1200*image.width),int((1-y/800)*image.height)))
                    self.assertTrue(water_pixel(key,rgb),(key,x,y,rgb))

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
                        if name=='city_2':self.assertTrue(image_path(faction,'cities',name).endswith('/harbor-water.png'))
                        else:self.assertIn('/cities-v2/'+name,image_path(faction,'cities',name))
                    self.assertEqual(len(hashes),7)

    def test_color_matched_harbors_have_real_transparent_edges(self):
        for faction,data in THEMES.items():
            path=Path(image_path(faction,'cities','city_2'))
            with Image.open(path) as source:
                self.assertEqual(source.mode,'RGBA')
                self.assertEqual(source.size,(1536,1024))
                alpha=source.getchannel('A')
                self.assertEqual(alpha.getextrema()[0],0)
                self.assertGreaterEqual(alpha.getextrema()[1],250)
                self.assertTrue(all(alpha.getpixel(p)<=1 for p in ((0,0),(1535,0),(0,1023),(1535,1023))))

    def test_depth_is_presentation_only_and_near_cities_are_larger(self):
        nodes=[dict(id=1,y=100),dict(id=2,y=600),dict(id=3,y=300)]
        self.assertEqual([c['id'] for c in depth_order(nodes)],[2,3,1])
        self.assertEqual([c['id'] for c in nodes],[1,2,3])
        for city in range(1,8):
            self.assertGreater(city_scale(city,100),city_scale(city,700))


if __name__=='__main__':unittest.main()
