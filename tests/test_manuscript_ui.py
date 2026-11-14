import unittest
from unittest.mock import Mock,patch
from strategy_ui_fixture import Window
from test_frontend_ui import frontend_classes,settle


class ManuscriptUITests(unittest.TestCase):
    def setUp(self):
        self.old=Window.size
        self.owner=frontend_classes()['Lor'](None)
        self.page=self.owner._manuscript
        self.addCleanup(setattr,Window,'size',self.old)
        self.addCleanup(self.close)
        Window.add_widget(self.owner)

    def close(self):
        if self.owner.parent:self.owner.parent.remove_widget(self.owner)
        self.page.stop()

    def test_manuscript_preserves_story_and_fits_small_screens(self):
        self.assertIn('Командующий 9-й армией Владислав',self.page.ink.text)
        for size in ((1280,720),(640,360),(320,568)):
            Window.size=size;settle()
            p=self.page
            self.assertGreaterEqual(p.sheet.x,0)
            self.assertLessEqual(p.candle.right,Window.width+1)
            self.assertGreaterEqual(p.candle.body.pos[0],0)
            self.assertLessEqual(p.candle.body.pos[0]+p.candle.body.size[0],Window.width+1)
            self.assertGreaterEqual(p.back_button.height,48)
            self.assertGreaterEqual(p.back_button.y,p.sheet.y)
            self.assertGreaterEqual(p.back_button.x,p.sheet.x)
            self.assertLessEqual(p.back_button.right,p.sheet.right)
            self.assertLessEqual(p.back_button.top,p.scroll.y)
            self.assertGreater(p.ink.height,p.scroll.height)
            self.assertLessEqual(p.ink.text_size[0],p.scroll.width)
            p.export_to_png(f'.release/manuscript-{size[0]}.png')

    def test_flame_moves_without_accumulating_canvas_and_stops_on_exit(self):
        Window.size=(640,360);settle()
        p=self.page;count=len(p.candle.canvas.children)
        self.assertIsNone(p.candle.flame.fallback)
        first=p.candle.flame.canvas['u_time']
        pixels=p.candle.flame.export_as_image().texture.pixels
        p.update(.1)
        self.assertNotEqual(first,p.candle.flame.canvas['u_time'])
        self.assertNotEqual(pixels,p.candle.flame.export_as_image().texture.pixels)
        for _ in range(120):p.update(.04)
        self.assertEqual(count,len(p.candle.canvas.children))
        self.assertIsNotNone(p._event)
        self.owner.parent.remove_widget(self.owner)
        self.assertIsNone(p._event)


if __name__=='__main__':unittest.main()
