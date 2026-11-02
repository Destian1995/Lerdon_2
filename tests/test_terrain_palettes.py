import random
import unittest
from types import SimpleNamespace

from map_terrain import load_terrain
from terrain_icons import local_palette,site_palette,icon_path,icon_name,assign_variants


class PaletteTests(unittest.TestCase):
    def test_green_map_never_uses_the_orange_maple_asset_even_with_five_forests(self):
        terrain=load_terrain('files/map/generate/map_8.png')
        sites=[dict(kind='forest',x=200+i*150,y=400) for i in range(5)]
        assign_variants(sites,terrain,random.Random(8))
        self.assertEqual({s['icon_variant'] for s in sites},{1,2,3,4,5})
        for site in sites:
            palette=site_palette(terrain,site)
            self.assertEqual(palette,'green')
            path=icon_path('forest',site['icon_variant'],palette)
            self.assertTrue(path.is_file(),path)
            self.assertNotIn('Осен',icon_name('forest',site['icon_variant'],palette))
            if site['icon_variant']==3:
                self.assertEqual(path.stem,'forest_3_green')

    def test_mixed_map_selects_green_and_warm_art_in_different_locations(self):
        terrain=load_terrain('files/map/generate/map_10.png')
        data=terrain.foliage_palette
        width,height=data['grid_size']
        for expected,index in [('warm',next(i for i,c in enumerate(data['cells']) if c[3])),
                               ('green',next(i for i,c in enumerate(data['cells']) if not c[3]))]:
            y,x=divmod(index,width)
            wx=(x+.5)*terrain.world_width/width
            wy=terrain.world_height-(y+.5)*terrain.world_height/height
            self.assertEqual(local_palette(terrain,wx,wy)[0],expected)
            for variant in range(1,6):
                path=icon_path('forest',variant,expected)
                self.assertTrue(path.is_file(),path)
                if expected=='warm':
                    self.assertNotEqual(path.stem,'forest_3_green')
                    if variant!=3:
                        self.assertTrue(path.stem.endswith('_warm'))

    def test_swamps_match_local_ground_without_duplicates_and_assignment_is_stable(self):
        def make_sites():
            return [dict(kind='swamp',x=25,y=50),dict(kind='swamp',x=75,y=50)]
        terrain=SimpleNamespace(world_width=100,world_height=100,foliage_palette={
            'grid_size':[2,1],'cells':[[74,116,66,0],[100,86,56,1]]})
        sites=assign_variants(make_sites(),terrain,random.Random(3))
        self.assertEqual([s['icon_variant'] for s in sites],[3,2])
        self.assertEqual(sites,assign_variants(make_sites(),terrain,random.Random(3)))

    def test_all_ten_maps_have_complete_offline_palette_annotations(self):
        for number in range(1,11):
            with self.subTest(map=number):
                terrain=load_terrain(f'files/map/generate/map_{number}.png')
                palette=terrain.foliage_palette
                self.assertEqual(palette['version'],1)
                width,height=palette['grid_size']
                self.assertEqual(len(palette['cells']),width*height)
                self.assertTrue(all(len(c)==4 and all(0<=n<=255 for n in c[:3]) for c in palette['cells']))

    def test_legacy_masks_use_green_fallback(self):
        self.assertEqual(local_palette(None,200,300)[0],'green')
        self.assertEqual(icon_path('forest',3,'green').stem,'forest_3_green')


if __name__=='__main__':
    unittest.main()
