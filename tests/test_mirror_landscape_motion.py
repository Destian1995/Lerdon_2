import hashlib
import math
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch,Mock
from PIL import Image
from strategy_ui_fixture import Widget
from mirror_landscape_motion import (landscape_data,LandscapeMotion,water_position,falling_leaf,ROOT)
from tools.build_mirror_ambience import water_pixel


class LandscapeMotionTests(unittest.TestCase):
    def test_animation_keeps_running_without_quest_queries_during_ai_turn(self):
        from otherworld_effects import MirrorEffects
        model=SimpleNamespace(owner=SimpleNamespace(faction='Эльфы',conn=object()),
            terrain=None,nodes=[dict(id=1,x=300,y=400)],width=1200,height=800,
            camera=SimpleNamespace(zoom=1),point=lambda x,y:(x,y))
        effects=MirrorEffects(model)
        with patch('turn_ui_guard.database_busy',return_value=True), \
             patch('otherworld_quests.objectives',side_effect=AssertionError('DB owned by worker')):
            effects.update(.1)
        self.assertGreater(effects.age,0)
        self.assertTrue(effects.landscape.water)

    def test_reviewed_water_patches_match_current_map_and_stay_on_water(self):
        for key in ('north','elves','adepts','elines','vampires'):
            data=landscape_data(key);source=ROOT/key/'map.png'
            self.assertEqual(data['image_sha256'],hashlib.sha256(source.read_bytes()).hexdigest())
            self.assertTrue(data['water'])
            self.assertLessEqual(len(data['water']),28)
            with Image.open(source) as image:
                image=image.convert('RGB')
                for area in data['water']:
                    for age in (0,1.25,2.5,3.75):
                        x,y,_=water_position(area,age,0)
                        rgb=image.getpixel((int(x/1200*image.width),int((1-y/800)*image.height)))
                        self.assertTrue(water_pixel(key,rgb),(key,x,y,rgb))

    def test_falling_leaves_descend_and_wrap_without_a_visible_jump(self):
        start=falling_leaf((100,400),0,0)
        middle=falling_leaf((100,400),2,0)
        end=falling_leaf((100,400),5.5,0)
        self.assertLess(middle[1],start[1])
        self.assertGreater(middle[3],0)
        self.assertEqual(start[3],0)
        self.assertEqual(end[3],0)

    def test_effects_follow_map_projection_and_do_not_reload_assets_per_frame(self):
        host=Widget();water=Mock()
        model=SimpleNamespace(point=lambda x,y:(x,y))
        # Kivy's bezier setter is write-only; observe the submitted geometry.
        # Real Line instructions are also exercised by the map UI tests.
        with patch('mirror_landscape_motion.Line',side_effect=lambda **kwargs:SimpleNamespace(**kwargs)):
            motion=LandscapeMotion(model,host.canvas,water,'elves')
        self.assertEqual(len(motion.leaves),12)
        self.assertLessEqual(len(motion.water),56)
        motion.update(2,1)
        before=tuple(motion.leaves[0][2].pos)
        first_curve=tuple(motion.water[0][3].bezier)
        model.point=lambda x,y:(x+50,y+25)
        with patch('mirror_landscape_motion.landscape_data',side_effect=AssertionError('per-frame IO')):
            motion.update(2,1)
        after=motion.leaves[0][2].pos
        self.assertAlmostEqual(after[0]-before[0],50,places=3)
        self.assertAlmostEqual(after[1]-before[1],25,places=3)
        curve=motion.water[0][3].bezier
        for i,value in enumerate(curve):self.assertAlmostEqual(value-first_curve[i],50 if i%2==0 else 25,places=3)
        motion.update(3,1)
        self.assertNotEqual(tuple(curve),tuple(motion.water[0][3].bezier))
