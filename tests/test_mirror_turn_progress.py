import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from test_otherworlds import fixture
from kivy.metrics import Metrics
from otherworld_ui import OtherworldMap
import otherworlds as worlds


class MirrorTurnProgressTests(unittest.TestCase):
    def setUp(self):
        self.size=Window.size;self.density=max(1,Metrics.density)
        Metrics.density=1;Window.size=(640,360);settle()
        self.db=fixture();worlds.enter(self.db,'Север','Home')
        self.screen=SimpleNamespace(conn=self.db,_turn_overlay=None,_troop_movement_busy=False,
                                    selected_faction='Север',process_turn=Mock())
        self.module=patch.dict(sys.modules,game_process=SimpleNamespace(_active_game_screen=self.screen))
        self.module.start()
        self.popup=OtherworldMap(self.db,'Север');self.popup.open(animation=False);settle()

    def tearDown(self):
        self.popup.dismiss(animation=False);settle()
        self.module.stop();self.db.close()
        Metrics.density=self.density;Window.size=self.size;settle()

    def overlay(self,progress=.4,name='Эльфы'):
        self.screen._turn_overlay=SimpleNamespace(parent=object(),_bar_progress=progress,
                                                  _status_label=SimpleNamespace(text='Ход фракции: '+name))

    def test_click_shows_loading_immediately_and_blocks_repeat_request(self):
        def process(_):
            self.assertEqual(self.popup.turn_progress.opacity,1)
            self.assertTrue(self.popup.next_turn_button.disabled)
            self.popup.next_turn()
            self.overlay()
        self.screen.process_turn.side_effect=process
        self.popup.next_turn()
        self.screen.process_turn.assert_called_once_with(None)
        self.assertEqual(self.popup.turn_progress.opacity,1)
        self.assertIn('Эльфы',self.popup.turn_progress.label.text)

    def test_progress_and_faction_follow_real_overlay_then_disappear(self):
        self.overlay(.25)
        self.popup.map.effects.update(.1)
        indicator=self.popup.turn_progress
        self.assertEqual(indicator.progress,.25)
        self.assertAlmostEqual(indicator.fill.size[0],indicator.track.size[0]*.25)
        self.assertTrue(self.popup.quest_button.disabled)
        self.overlay(.75,'Вампиры');self.popup.map.effects.update(.1)
        self.assertIn('Вампиры',indicator.label.text)
        self.screen._turn_overlay=None;self.popup.map.effects.update(.1)
        self.assertEqual(indicator.opacity,0)
        self.assertFalse(hasattr(self.popup,'zoom_controls'))
        self.assertFalse(self.popup.next_turn_button.disabled)
        self.assertFalse(self.popup.quest_button.disabled)

    def test_pending_stripe_animates_and_early_exit_restores_controls(self):
        self.popup._turn_requested=True;self.popup.update_turn_progress(0)
        before=self.popup.turn_progress.fill.pos
        self.popup.map.effects.update(.1)
        self.assertNotEqual(self.popup.turn_progress.fill.pos,before)
        self.popup._turn_requested=False;self.popup.update_turn_progress(0)
        self.assertEqual(self.popup.turn_progress.opacity,0)
        self.popup.next_turn()
        self.assertEqual(self.popup.turn_progress.opacity,0)
        self.assertFalse(self.popup._turn_requested)

    def test_loading_row_fits_phone_android_and_portrait_without_overlapping_actions(self):
        self.overlay()
        for size,density in (((640,360),1),((1280,576),2),((392,844),1)):
            Window.size=size;Metrics.density=density;settle()
            self.popup.fit();settle()
            bar=self.popup.turn_progress;stage=self.popup.stage
            self.assertGreaterEqual(bar.x,stage.x)
            self.assertLessEqual(bar.right,stage.right)
            self.assertGreaterEqual(bar.y,self.popup.action_bar.top)
            self.assertLessEqual(bar.top,stage.top)
            self.assertGreaterEqual(bar.label.font_size,12)
        self.popup.dismiss(animation=False);settle()
        self.assertIsNone(self.popup.map.effects._event)
