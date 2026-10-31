import time
import unittest

from strategy_ui_fixture import Window, Image, FloatLayout
from kivy.base import EventLoop
from portrait_ui import install_portrait_frames, portrait_accent
from strategy_ui import FACTIONS


class PortraitFrameTests(unittest.TestCase):
    def setUp(self):
        install_portrait_frames()
        self.host = FloatLayout()
        Window.add_widget(self.host)

    def tearDown(self):
        Window.remove_widget(self.host)

    def image(self, source):
        widget = Image(source=source, size_hint=(None, None), size=(320, 200), pos=(20, 30), fit_mode='contain')
        self.host.add_widget(widget)
        for _ in range(5):
            time.sleep(.02)
            EventLoop.idle()
        return widget

    def test_units_heroes_and_factions_have_frames_but_status_and_map_do_not(self):
        for source in ('files/army/death/morgana.png', 'files/pict/hero/default_image.png',
                       'files/buildings/people.png', 'files/sov/vampire.jpg'):
            widget = self.image(source)
            self.assertTrue(widget._portrait_frame.visible, source)
        for source in ('files/status/army.png', 'files/map/generate/map_1.png', 'files/menu/choise/vampire.jpg'):
            self.assertIsNone(portrait_accent(source))

    def test_frame_follows_visible_portrait_and_resize_without_layout_changes(self):
        widget = self.image('files/army/death/morgana.png')
        frame = widget._portrait_frame
        before = (widget.pos, widget.size, widget.size_hint)
        frame.update()
        self.assertEqual(before, (widget.pos, widget.size, widget.size_hint))
        x, y, width, height = frame.bounds
        self.assertAlmostEqual(x + width / 2, widget.center_x)
        self.assertAlmostEqual(y + height / 2, widget.center_y)
        self.assertLessEqual(width, widget.width)
        widget.size = (420, 280)
        frame.update()
        self.assertNotEqual(frame.bounds, (x, y, width, height))

    def test_dynamic_source_changes_update_one_frame_and_faction_accent(self):
        widget = self.image('files/status/army.png')
        widget.source = 'files/army/death/morgana.png'
        decoration = widget._portrait_frame
        for _ in range(5):
            EventLoop.idle()
        self.assertEqual(tuple(decoration.accent.rgba[:3]), tuple(FACTIONS['Нежить'][:3]))
        widget.source = 'files/army/people/vlad.jpg'
        self.assertIs(widget._portrait_frame, decoration)
        self.assertEqual(widget.canvas.after.children.count(decoration.group), 1)
        widget.source = 'files/status/army.png'
        self.assertFalse(decoration.visible)


if __name__ == '__main__':
    unittest.main()
