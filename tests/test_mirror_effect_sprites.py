"""Real painted atlas frames, smooth blending and weather lifecycle."""
import math
import unittest
from pathlib import Path
from types import SimpleNamespace
from PIL import Image
from strategy_ui_fixture import Widget
from mirror_effect_sprites import (animation_frame,blend_opacities,animation_clip,
                                   atlas_texture,PaintedSprite,ASSET_ROOT)
from otherworld_effects import (MirrorEffects,lightning_envelope,lightning_glow_envelope,
                                fog_front,
                                AMBIENT_ICON_SCALE,LIGHTNING_INTERVAL,SKY_EFFECT_INTERVAL)


class PaintedWeatherTests(unittest.TestCase):
    def test_fog_returns_to_mountains_at_its_original_size_and_density(self):
        from map_terrain import MOUNTAIN,WATER
        terrain=SimpleNamespace(grid=[WATER,MOUNTAIN],width=2,height=1,world_width=1200,world_height=800)
        for faction in ('Вампиры','Эльфы','Север','Адепты'):
            m=SimpleNamespace(owner=SimpleNamespace(faction=faction),terrain=terrain,
                nodes=[dict(id=1,x=300,y=400)],width=1200,height=800,
                camera=SimpleNamespace(zoom=1),point=lambda x,y:(x,y))
            effects=MirrorEffects(m);effects.age=6;effects.update(0)
            expected=fog_front((900,400),6)
            self.assertEqual(len(effects.fog),32)
            for color,rect in effects.fog:
                self.assertEqual(tuple(rect.size),(180,78))
                self.assertAlmostEqual(rect.pos[0]+90,expected[0],delta=1e-4)
                self.assertAlmostEqual(rect.pos[1]+39,expected[1],delta=1e-4)
            self.assertGreater(max(c.a for c,_ in effects.fog),.4)
            m.camera.zoom=1.5;effects.update(0)
            self.assertEqual(tuple(effects.fog[0][1].size),(270,117))

    def test_elines_dust_keeps_its_original_full_map_wind(self):
        m=SimpleNamespace(owner=SimpleNamespace(faction='Элины'),terrain=None,
            nodes=[dict(id=1,x=300,y=400)],width=1200,height=800,
            camera=SimpleNamespace(zoom=1),point=lambda x,y:(x,y))
        effects=MirrorEffects(m);effects.update(0)
        self.assertEqual(tuple(effects.fog[0][1].size),(260,105))
        before=tuple(effects.fog[0][1].pos);effects.update(.1)
        self.assertGreater(effects.fog[0][1].pos[0],before[0])
        centers=[rect.pos[1]+rect.size[1]/2 for _,rect in effects.fog]
        self.assertLess(min(centers),100);self.assertGreater(max(centers),700)
    def test_every_clip_has_four_real_distinct_transparent_frames(self):
        for key in ('vampires','elves','north','adepts','elines','lightning','lightning-core'):
            with self.subTest(key=key):
                image=Image.open(ASSET_ROOT/(key+'.png'))
                self.assertEqual(image.mode,'RGBA')
                alpha=image.getchannel('A')
                self.assertLess(alpha.getextrema()[0],3)
                self.assertGreater(alpha.getextrema()[1],230)
                self.assertGreater(sum(alpha.histogram()[:8])/image.width/image.height,.35)
                for row in range(1 if key.startswith('lightning') else 4):
                    clip=animation_clip(key,row)
                    self.assertEqual(len(clip),4)
                    self.assertEqual(len({bytes(f.pixels) for f in clip}),4)
                    self.assertIs(atlas_texture(key),atlas_texture(key))

    def test_frame_wrap_and_alpha_are_continuous(self):
        self.assertEqual(animation_frame(0),(0,1,0))
        self.assertEqual(animation_frame(4/7),(0,1,0))
        self.assertEqual(animation_frame(2,fps=5,loop=False),(3,3,0))
        for opacity in (0,.2,.75,1):
            for mix in (0,.1,.5,.9,1):
                under,over=blend_opacities(opacity,mix)
                self.assertTrue(0<=under<=1 and 0<=over<=1)
                self.assertAlmostEqual(under*(1-over)+over,opacity)

    def test_painted_sprite_uses_two_textures_and_no_file_io_per_frame(self):
        sprite=PaintedSprite(Widget().canvas)
        sprite.draw('vampires',0,(120,80),(50,40),.05,.8,angle=12)
        self.assertGreater(sprite.layers[0][0].a,0)
        self.assertGreater(sprite.layers[1][0].a,0)
        self.assertIsNot(sprite.layers[0][1].texture,sprite.layers[1][1].texture)
        self.assertEqual(tuple(sprite.layers[0][1].pos),(95,60))
        before=animation_clip.cache_info().misses
        for i in range(60):sprite.draw('vampires',0,(120+i,80),(50,40),i/30,.8)
        self.assertEqual(animation_clip.cache_info().misses,before)
        sprite.hide();self.assertTrue(all(color.a==0 for color,_ in sprite.layers))

    def test_all_factions_follow_projection_and_keep_one_clock(self):
        for faction in ('Вампиры','Эльфы','Север','Адепты','Элины'):
            m=SimpleNamespace(owner=SimpleNamespace(faction=faction),terrain=None,
                nodes=[dict(id=1,x=300,y=400)],_current_city=1,width=1200,height=800,
                camera=SimpleNamespace(zoom=1),point=lambda x,y:(x,y))
            effects=MirrorEffects(m);effects.update(.1)
            self.assertTrue(all(isinstance(s,PaintedSprite) for s in effects.flair+effects.runes+effects.ripples))
            sprite=effects.flair[0];before=tuple(sprite.layers[0][1].pos)
            m.point=lambda x,y:(x+55,y+25);effects.update(0)
            for actual,expected in zip(sprite.layers[0][1].pos,(before[0]+55,before[1]+25)):
                self.assertAlmostEqual(actual,expected,delta=1e-4)
            effects.start();event=effects._event;effects.start();self.assertIs(effects._event,event)
            effects.stop();self.assertIsNone(effects._event)

    def test_lightning_is_small_and_bright_then_fades(self):
        self.assertGreater(lightning_envelope(.12),.8)
        self.assertGreater(lightning_envelope(.30),lightning_envelope(.25))
        self.assertEqual(lightning_envelope(2),0)
        self.assertEqual(lightning_envelope(8),0)
        m=SimpleNamespace(owner=SimpleNamespace(faction='Вампиры'),terrain=None,
            nodes=[dict(id=1,x=300,y=400)],width=1200,height=800,
            camera=SimpleNamespace(zoom=1),point=lambda x,y:(x,y))
        effects=MirrorEffects(m);effects.age=.12;effects.update(0)
        self.assertEqual(effects.lightning[0].clip,('lightning-core',0))
        self.assertGreater(effects.lightning[0].layers[0][1].size[0],effects.flair[0].layers[0][1].size[0])
        self.assertLess(effects.lightning[0].layers[0][1].size[0],40)
        effects.age=2;effects.update(0)
        self.assertTrue(all(c.a==0 for c,_ in effects.lightning[0].layers))

    def test_all_ambient_icons_are_almost_three_times_smaller(self):
        sprite=PaintedSprite(Widget().canvas,scale=AMBIENT_ICON_SCALE)
        sprite.draw('vampires',0,(120,80),(60,40),.1)
        self.assertAlmostEqual(sprite.layers[0][1].size[0],21)
        self.assertAlmostEqual(sprite.layers[0][1].size[1],14)
        m=SimpleNamespace(owner=SimpleNamespace(faction='Вампиры'),terrain=None,
            nodes=[dict(id=1,x=300,y=400)],width=1200,height=800,
            camera=SimpleNamespace(zoom=1),point=lambda x,y:(x,y))
        effects=MirrorEffects(m)
        self.assertTrue(all(s.scale==.35 for s in effects.flair+effects.motes+
                            effects.ripples+effects.runes+[effects.gate,effects.party,effects.sky]))
        self.assertTrue(all(s.scale==1 for s in effects.lightning))

    def test_glow_is_a_separate_delayed_layer_in_the_mist(self):
        m=SimpleNamespace(owner=SimpleNamespace(faction='Вампиры'),terrain=None,
            nodes=[dict(id=1,x=300,y=400)],width=1200,height=800,
            camera=SimpleNamespace(zoom=1),point=lambda x,y:(x,y))
        effects=MirrorEffects(m)
        effects.age=.10;effects.update(0)
        self.assertGreater(lightning_envelope(.10),0)
        self.assertTrue(all(c.a==0 for c,_ in effects.lightning_glow[0]))
        self.assertTrue(all(c.a>0 for c,_ in effects.storm_clouds[0]))
        effects.age=.38;effects.update(0)
        self.assertTrue(all(c.a>0 for c,_ in effects.lightning_glow[0]))
        effects.age=1.4;effects.update(0)
        self.assertEqual(lightning_envelope(1.4),0)
        self.assertGreater(lightning_glow_envelope(1.4),0)
        effects.age=2;effects.update(0)
        self.assertTrue(all(c.a==0 for c,_ in effects.lightning_glow[0]))

    def test_six_local_lightning_flashes_take_turns_at_six_distinct_positions(self):
        m=SimpleNamespace(owner=SimpleNamespace(faction='Вампиры'),terrain=None,
            nodes=[dict(id=1,x=300,y=400)],width=1200,height=800,
            camera=SimpleNamespace(zoom=1),point=lambda x,y:(x,y))
        effects=MirrorEffects(m);positions=[]
        self.assertEqual(len(effects.lightning),6)
        for i in range(6):
            effects.age=i*LIGHTNING_INTERVAL+.3;effects.update(0)
            visible=[j for j,s in enumerate(effects.lightning) if any(c.a>0 for c,_ in s.layers)]
            self.assertEqual(visible,[i])
            rect=effects.lightning[i].layers[0][1];positions.append(tuple(rect.pos))
            self.assertLessEqual(rect.size[0],effects.flair[0].layers[0][1].size[0]*2)
            self.assertTrue(all(r.size[0]<=rect.size[0] for _,r in effects.lightning_glow[i]))
        self.assertEqual(len(set(positions)),6)

    def test_all_faction_sky_effects_are_small_and_alternate(self):
        for faction in ('Вампиры','Север','Эльфы','Адепты','Элины'):
            m=SimpleNamespace(owner=SimpleNamespace(faction=faction),terrain=None,
                nodes=[dict(id=1,x=300,y=400)],width=1200,height=800,
                camera=SimpleNamespace(zoom=1),point=lambda x,y:(x,y))
            effects=MirrorEffects(m)
            self.assertEqual(len(effects.sky_effects),6)
            for i in range(6):
                effects.age=i*SKY_EFFECT_INTERVAL+.4;effects.update(0)
                self.assertEqual([j for j,s in enumerate(effects.sky_effects) if any(c.a>0 for c,_ in s.layers)],[i])
                self.assertLess(effects.sky_effects[i].layers[0][1].size[0],40)
