import unittest
from unittest.mock import Mock,patch
from test_tactical_battle_ui import Window, settle
import test_tactical_battle_ui as ui_fixture
from test_tactical_abilities import arena
from tactical_battle_ui import TacticalBattlePopup
from game_audio import AudioManager
from test_game_audio import Sound
from audio_settings_ui import show_audio_settings


class AudioUITests(unittest.TestCase):
    setUp=ui_fixture.TacticalUITests.setUp
    tearDown=ui_fixture.TacticalUITests.tearDown
    def test_legacy_and_new_buttons_play_one_click_after_repeated_theming(self):
        from kivy.uix.button import Button
        from kivy.uix.boxlayout import BoxLayout
        from strategy_ui import StrategyButton
        from window_theme import theme_tree
        root=BoxLayout()
        buttons=[Button(text='Старая кнопка'),StrategyButton(text='Новая кнопка')]
        for button in buttons:root.add_widget(button)
        for _ in range(4):theme_tree(root)
        with patch('game_audio.get_audio') as audio:
            for button in buttons:
                audio.return_value.play.reset_mock()
                button.dispatch('on_release')
                audio.return_value.play.assert_called_once_with('click')
                button.disabled=True
                audio.return_value.play.reset_mock()
                button.dispatch('on_release')
                audio.return_value.play.assert_not_called()

    def test_audio_settings_fit_small_landscape_and_portrait(self):
        from kivy.uix.slider import Slider
        from strategy_ui import StrategyButton
        for size in ((568,320),(360,640)):
            Window.size=size;settle()
            manager=AudioManager(lambda path:Sound())
            done=Mock()
            popup=show_audio_settings(manager=manager,on_close=done)
            self.views.append(popup);settle()
            sliders=[w for w in popup.walk() if isinstance(w,Slider)]
            self.assertEqual(len(sliders),2)
            for slider in sliders:
                self.assertGreaterEqual(slider.height,44)
                self.assertLessEqual(slider.width,Window.width)
            toggle=next(w for w in popup.walk() if isinstance(w,StrategyButton) and w.text=='Звук: включён')
            toggle.dispatch('on_release')
            self.assertFalse(manager.settings['enabled'])
            close=next(w for w in popup.walk() if isinstance(w,StrategyButton) and w.text=='Готово')
            close.dispatch('on_release');settle()
            done.assert_called_once()

    def test_grenade_throw_and_explosion_cues_follow_animation_and_cleanup(self):
        model,a,g,b,h=arena('Владислав')
        view=TacticalBattlePopup(model,'attacker',lambda _:None)
        self.views.append(view);view.deploying=False
        view.audio=Mock()
        view.animate(model.use_ability('grenade',b.pos))
        view.audio.play.assert_called_once_with('throw',owner=view)
        for _ in range(6):view.tick(.1)
        self.assertNotIn('explosion',[call.args[0] for call in view.audio.play.call_args_list])
        view.tick(.1)
        self.assertEqual([call.args[0] for call in view.audio.play.call_args_list].count('explosion'),1)
        view.cleanup()
        view.audio.stop_owner.assert_called_once_with(view)
        self.assertEqual(view.sound_queue,[])

    def test_ranged_weapon_and_impact_cues_and_victory_only_once(self):
        from test_tactical_combat import battle,unit
        model,a,b=battle([unit(kind='archer',initiative=100)])
        a.pos=(1,2);b.pos=(5,2)
        a.unit['unit_image']='files/army/people/predator.jpg'
        view=TacticalBattlePopup(model,'attacker',lambda _:None)
        self.views.append(view);view.deploying=False;view.audio=Mock()
        view.animate(model.attack(b.id));view.tick(.01)
        view.audio.play.assert_called_with('rifle',owner=view)
        for _ in range(3):view.tick(.1)
        self.assertIn('hit',[call.args[0] for call in view.audio.play.call_args_list])
        model.winner='attacker';view.busy=0
        view.refresh();view.refresh()
        self.assertEqual([call.args[0] for call in view.audio.play.call_args_list].count('victory'),1)


if __name__=='__main__':unittest.main()
