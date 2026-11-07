import unittest
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from kivy.metrics import Metrics,dp
from kivy.uix.popup import Popup
import test_morgana_covenant as logic
import morgana_covenant as covenant
from morgana_covenant_ui import show_offer


class MorganaOfferUITests(unittest.TestCase):
    def test_responsive_offer_reopen_accept_and_necropolis_art(self):
        seed=logic.MorganaCovenantTests();seed.setUp()
        size=Window.size;metrics=(Metrics.density,Metrics.fontscale)
        try:
            Metrics.density=Metrics.fontscale=1
            popup=show_offer(seed.db,'Север');settle()
            self.assertIsNotNone(popup.art.texture)
            for screen,density in (((640,360),1),((1280,576),2),((392,844),1)):
                Window.size=screen;Metrics.density=density;settle();popup.fit();settle()
                self.assertGreater(popup.copy_scroll.height,dp(35))
                self.assertGreaterEqual(popup.body.y,popup.root.y-1)
                self.assertLessEqual(popup.body.top,popup.root.top+1)
                self.assertGreaterEqual(popup.art.x,popup.root.x-1)
                self.assertLessEqual(popup.art.right,popup.root.right+1)
            popup.export_to_png('.release/morgana-offer-phone.png')
            popup.dismiss(animation=False);settle()
            self.assertIsNone(show_offer(seed.db,'Север'))
            popup=show_offer(seed.db,'Север',force=True);settle()
            popup.accept();settle()
            self.assertTrue(covenant.serving(seed.db,'Север'))
            from town_scene import TownScene
            scene=TownScene(seed.db,'Home','Север')
            self.assertEqual(scene.art_faction,'Нежить')
            self.assertEqual(scene.faction,'Север')
            self.assertEqual(sum(scene.counts.values()),6)
        finally:
            for widget in list(Window.children):
                if isinstance(widget,Popup):widget.dismiss(animation=False)
            settle();seed.doCleanups()
            Metrics.density,Metrics.fontscale=metrics;Window.size=size;settle()


if __name__=='__main__':unittest.main()
