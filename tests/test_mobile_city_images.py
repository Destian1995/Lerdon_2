"""Android padded texture regions and whole tavern portraits on narrow screens."""
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from kivy.graphics import Fbo,ClearColor,ClearBuffers
from kivy.graphics.texture import Texture
from kivy.metrics import Metrics
from town_scene import TownScene,mirrored_tex_coords,texture
from otherworld_ui import ForeignCityPopup
import otherworlds as worlds


class AndroidWallTests(unittest.TestCase):
    def test_reflection_keeps_uvs_inside_offset_and_inverted_texture_regions(self):
        for coords in ((.125,.2,.375,.2,.375,.7,.125,.7),
                       (0,.49,.51,.49,.51,0,0,0)):
            mirrored=mirrored_tex_coords(coords)
            corners=lambda values:[tuple(values[i:i+2]) for i in range(0,8,2)]
            self.assertEqual(corners(mirrored),[corners(coords)[i] for i in (1,0,3,2)])
            self.assertEqual(mirrored_tex_coords(mirrored),list(coords))

    def test_both_built_walls_render_with_android_style_power_of_two_padding(self):
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.executescript('''CREATE TABLE cities(id,name,faction);
            INSERT INTO cities VALUES(1,'Home','Адепты');
            CREATE TABLE buildings(city_name,faction,building_type,count);
            INSERT INTO buildings VALUES('Home','Адепты','Стена',1);''')
        for faction,image_height in (('Адепты',503),('Элины',520)):
            with self.subTest(faction=faction):
                db.execute('UPDATE cities SET faction=?',(faction,))
                padded=Texture.create(size=(1024,1024),colorfmt='rgba')
                padded.blit_buffer(bytes(1024*1024*4),colorfmt='rgba',bufferfmt='ubyte')
                region=padded.get_region(0,0,520,image_height)
                region.blit_buffer(bytes((255,0,255,255))*520*image_height,
                                   colorfmt='rgba',bufferfmt='ubyte')
                with patch('town_scene.texture',side_effect=lambda path:
                           region if path.endswith('wall.png') else texture(path)):
                    scene=TownScene(db,'Home',faction,size_hint=(None,None),size=(640,360))
                scene.effects.stop()
                sprite=scene.sprites['Стена']
                self.assertEqual(tuple(sprite.tex_coords),tuple(mirrored_tex_coords(region.tex_coords)))
                fbo=Fbo(size=(640,360),with_stencilbuffer=True)
                with fbo:ClearColor(0,0,0,1);ClearBuffers()
                fbo.add(scene.canvas)
                try:
                    fbo.draw();pixels=fbo.pixels
                    magenta=sum(1 for i in range(0,len(pixels),4)
                                if pixels[i]>230 and pixels[i+1]<10 and pixels[i+2]>230)
                    self.assertGreater(magenta,sprite.size[0]*sprite.size[1]*.8)
                finally:fbo.remove(scene.canvas)


class BartenderFitTests(unittest.TestCase):
    def test_entire_portrait_is_inside_frame_for_every_faction_and_screen(self):
        db=fixture();self.addCleanup(db.close)
        original=Window.size;metrics=Metrics.density,Metrics.fontscale
        popup=None
        try:
            for faction in ('Адепты','Элины','Север','Эльфы','Вампиры'):
                owner=SimpleNamespace(conn=db,faction=faction)
                popup=ForeignCityPopup(owner,worlds.cities(db,faction)[2])
                popup.open(animation=False)
                for size,density in (((1280,576),1),((640,360),1),((1280,576),2),((390,844),1)):
                    with self.subTest(faction=faction,size=size,density=density):
                        Metrics.density=density;Window.size=size;settle();popup.fit();settle()
                        image=popup.bartender;frame=popup.art_frame
                        self.assertIsNotNone(image.texture)
                        self.assertEqual(image.fit_mode,'contain')
                        w,h=image.norm_image_size
                        self.assertGreater(w*h,0)
                        self.assertLessEqual(w,frame.width+.1)
                        self.assertLessEqual(h,frame.height+.1)
                        self.assertAlmostEqual(w/h,image.texture.width/image.texture.height,places=4)
                        self.assertAlmostEqual(image.center_x,frame.center_x,delta=.1)
                        self.assertAlmostEqual(image.center_y,frame.center_y,delta=.1)
                popup.dismiss(animation=False);popup=None;settle()
        finally:
            if popup:popup.dismiss(animation=False)
            Metrics.density,Metrics.fontscale=metrics;Window.size=original;settle()
