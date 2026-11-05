"""Defense plots, reflected gates and their touch targets stay in agreement."""
import unittest
from unittest.mock import patch
from strategy_ui_fixture import Window
from test_town_interior import TownTests
from test_dialog_layout import settle
from test_map_zoom import Touch
from town_art import LOTS,THEMES,building_mirrored,building_path,CITADEL_DOORS,citadel_entry,theme_key
from town_scene import building_shape,TownScene


class TownDefenseTests(unittest.TestCase):
    setUp=TownTests.setUp
    tearDown=TownTests.tearDown

    def test_defense_slots_are_swapped_without_changing_footprint_sizes(self):
        self.assertEqual(LOTS['Стена'],(.84,.56,.31))
        self.assertEqual(LOTS['Цитадель'],(.52,.50,.22))

    def test_all_factions_use_consistent_rendering_and_alpha_hit_test(self):
        town=self.owner._open_build_menu();settle()
        for faction in THEMES:
            with self.subTest(faction=faction):
                self.db.execute('DELETE FROM buildings')
                self.db.execute('UPDATE cities SET faction=?',(faction,))
                for name in ('Стена','Цитадель'):
                    self.db.execute('INSERT INTO buildings VALUES(?,?,?,1)',(self.owner.city_name,faction,name))
                self.db.commit()
                scene=town.scene;scene.refresh()
                left,bottom,width,height=scene.scene_bounds
                for name in ('Стена','Цитадель'):
                    sprite=scene.sprites[name]
                    u,v,_=scene.lots[name]
                    self.assertAlmostEqual(sprite.pos[0]+sprite.size[0]/2,left+u*width,delta=.1)
                    self.assertAlmostEqual(sprite.pos[1],bottom+v*height,delta=.1)
                    reflected=building_mirrored(faction,name)
                    self.assertEqual(sprite.tex_coords[0],1 if reflected else 0)
                    mask,_=building_shape(building_path(faction,name))
                    candidates=[(x,y) for y in range(len(mask)*2//3,len(mask))
                                for x in range(len(mask[0])) if mask[y][x]]
                    x,y=candidates[len(candidates)//2]
                    u=(x+.5)/len(mask[0]);v=(y+.5)/len(mask)
                    touch=Touch(sprite.pos[0]+(1-u if reflected else u)*sprite.size[0],
                                sprite.pos[1]+v*sprite.size[1])
                    scene.selected=None
                    scene.on_touch_down(touch);scene.on_touch_up(touch)
                    self.assertEqual(scene.selected,name)
                    self.assertIn(name,scene.outlines)

    def test_every_variant_door_meets_approach_target_in_both_scene_modes(self):
        for faction in THEMES:
            self.db.execute('DELETE FROM buildings')
            self.db.execute('UPDATE cities SET faction=?',(faction,))
            self.db.execute('INSERT INTO buildings VALUES(?,?,?,1)',(self.owner.city_name,faction,'Цитадель'))
            self.db.commit()
            for variant in (1,2,3):
                for size,preview in (((640,300),False),((300,600),False),((540,150),True)):
                    with self.subTest(faction=faction,variant=variant,size=size,preview=preview), \
                         patch('town_art.city_variant',return_value=variant):
                        scene=TownScene(self.db,self.owner.city_name,faction,preview=preview,
                                        size_hint=(None,None),size=size)
                        sprite=scene.sprites['Цитадель']
                        u,v=CITADEL_DOORS[theme_key(faction)]
                        actual=(sprite.pos[0]+u*sprite.size[0],sprite.pos[1]+v*sprite.size[1])
                        u,v=citadel_entry(faction,self.owner.city_name)
                        x,y,w,h=scene.scene_bounds
                        self.assertAlmostEqual(actual[0],x+u*w,delta=.1)
                        self.assertAlmostEqual(actual[1],y+v*h,delta=.1)
                        if faction=='Эльфы':
                            center=(sprite.pos[0]+sprite.size[0]/2-x)/w
                            self.assertGreaterEqual(center,.49)
                            self.assertLessEqual(center,.57)
                        self.assertLessEqual(sprite.pos[1]+sprite.size[1],y+h*.98+.1)
                        scene.effects.stop()


if __name__=='__main__':
    unittest.main()
