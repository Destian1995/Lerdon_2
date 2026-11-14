import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from strategy_ui_fixture import Window,FloatLayout
from test_frontend_ui import settle
from author_ui import build_author,LINKS,PORTRAIT


class AuthorUITests(unittest.TestCase):
    def setUp(self):
        self.old_size=Window.size
        self.owner=FloatLayout()
        self.owner.open_link=Mock();self.owner.go_back=Mock()
        Window.add_widget(self.owner)
        self.page=build_author(self.owner)
        self.addCleanup(Window.remove_widget,self.owner)
        self.addCleanup(setattr,Window,'size',self.old_size)

    def test_phone_rotation_keeps_back_visible_and_links_readable(self):
        self.assertTrue(Path(PORTRAIT).is_file())
        for size in ((1280,720),(640,360),(320,568),(640,360)):
            Window.size=size;settle()
            page=self.page
            self.assertGreaterEqual(page.back_button.y,page.panel.y)
            self.assertLessEqual(page.back_button.top,page.scroll.y)
            self.assertGreaterEqual(page.back_button.height,48)
            for button in page.link_buttons:
                self.assertGreaterEqual(button.height,48)
                self.assertLessEqual(button.title_label.texture_size[0],button.title_label.width+1)
            if size==(640,360):
                self.assertLessEqual(page.body.height,page.scroll.height+1)
                page.export_to_png('.release/author-landscape.png')
            elif size==(320,568):page.export_to_png('.release/author-portrait.png')
            else:page.export_to_png('.release/author-desktop.png')

    def test_links_keep_existing_destinations_and_back_calls_owner(self):
        Window.size=(640,360);settle()
        with patch('game_audio.get_audio'):
            for button,link in zip(self.page.link_buttons,LINKS):
                button.dispatch('on_release')
                self.owner.open_link.assert_called_with(button,link[3])
            self.page.back_button.dispatch('on_release')
        self.owner.go_back.assert_called_once()


if __name__=='__main__':unittest.main()
