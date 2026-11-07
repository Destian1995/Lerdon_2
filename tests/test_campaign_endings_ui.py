import unittest
from types import SimpleNamespace
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from kivy.metrics import Metrics,dp
from results_ui import show_campaign_results


class EndingUITests(unittest.TestCase):
    def test_story_statistics_and_exit_fit_android(self):
        size=Window.size;metrics=(Metrics.density,Metrics.fontscale);calls=[]
        owner=SimpleNamespace(current_faction='Эльфы',game_status='win',reason='Мир во всем мире',
                              conn=None,exit_to_main_menu=lambda *_:calls.append('exit'))
        popup=show_campaign_results(owner,'Победа!','Победа!',
            [dict(faction='Эльфы',units_combat=20,units_destroyed=2,units_killed=30,army_efficiency_ratio=1.5)],(1,1,1,1))
        try:
            for screen,density,scale in (((640,360),1,1),((1280,576),2,1.2),((320,568),1,1.4)):
                Window.size=screen;Metrics.density=density;Metrics.fontscale=scale;settle()
                self.assertGreater(popup.story_scroll.height,dp(35))
                self.assertIsNotNone(popup.ending_art.texture)
                self.assertGreaterEqual(popup.ending_art.x,popup.x-1)
                self.assertLessEqual(popup.ending_art.right,popup.right+1)
                self.assertGreaterEqual(popup.summary_button.height,dp(44)-1)
                popup.statistics_button.dispatch('on_release');settle()
                self.assertIsNotNone(popup.statistics_scroll.parent)
                popup.summary_button.dispatch('on_release');settle()
                self.assertIsNotNone(popup.epilogue_body.parent)
            popup.export_to_png('.release/campaign-ending-phone.png')
            self.assertEqual(calls,[])
            next(w for w in popup.content.walk() if getattr(w,'text','')=='Вернуться в меню').dispatch('on_release')
            self.assertEqual(calls,['exit'])
        finally:
            popup.dismiss(animation=False);settle()
            Metrics.density,Metrics.fontscale=metrics;Window.size=size;settle()
