"""Successful resource exchanges sound once; failed operations stay silent."""
import ast
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_otherworlds import fixture
import otherworlds as worlds


def action(path, name, **namespace):
    # Extract actions without importing modules that open the player's campaign.
    tree=ast.parse(Path(path).read_text(encoding='utf-8'))
    node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name==name)
    exec(compile(ast.Module(body=[node],type_ignores=[]),path,'exec'),namespace)
    return namespace[name]


class TradeAudioTests(unittest.TestCase):
    def test_main_market_buy_and_sell_sound_only_after_success(self):
        handle=action('economic.py','handle_trade',show_message=Mock(),format_number=str)
        for trade in ('buy','sell'):
            for success in (True,False):
                with self.subTest(trade=trade,success=success),patch('game_audio.play_effect') as sound:
                    market=SimpleNamespace(current_raw_material_price=100,_get_trade_bonus=lambda:1,resources={'Кроны':10000},
                        get_available_raw_material_lots=lambda:100,
                        trade_raw_material=Mock(return_value=success),update_economic_efficiency=Mock())
                    handle(market,trade,1,Mock())
                    if success:sound.assert_called_once_with('coins')
                    else:sound.assert_not_called()

    def test_mirror_market_success_and_insufficient_balances(self):
        db=fixture();self.addCleanup(db.close)
        worlds.enter(db,'Север','Home')
        with patch('game_audio.play_effect') as sound:
            worlds.trade_crystals(db,'Север',True)
            sound.assert_called_once_with('coins');sound.reset_mock()
            worlds.trade_crystals(db,'Север',False)
            sound.assert_called_once_with('coins');sound.reset_mock()
            db.execute("UPDATE resources SET amount=0 WHERE faction='Север'");db.commit()
            for buy in (True,False):
                with self.assertRaises(ValueError):worlds.trade_crystals(db,'Север',buy)
            sound.assert_not_called()

    def test_diplomatic_trade_and_agreement_only_sound_on_success(self):
        deal=action('game_process.py','_execute_trade_deal')
        owner=SimpleNamespace(conn=Mock(),selected_faction='Север',faction=Mock())
        message='[ТОРГОВЛЯ] Мы отдаём 100 Кристаллов, вы — 50 Крон.'
        for success in (True,False):
            with patch('utils.resource_payments.exchange_resources',return_value=success), \
                 patch('utils.resource_payments.sync_resources'),patch('game_audio.play_effect') as sound:
                deal(owner,'Эльфы',message,Mock())
                if success:sound.assert_called_once_with('coins')
                else:sound.assert_not_called()
        with patch('game_audio.play_effect') as sound:
            deal(owner,'Эльфы','[ТОРГОВЛЯ] Предлагаем торговое соглашение.',Mock())
            sound.assert_called_once_with('coins')

    def test_coin_clip_plays_with_the_game_sdl2_backend(self):
        from game_audio import EFFECTS,load_game_sound
        clip=load_game_sound(str(EFFECTS['coins']));self.addCleanup(clip.unload)
        self.assertEqual(type(clip).__name__,'SoundSDL2')
        import wave
        with wave.open('files/sounds/effects/coins-pour-out-2.wav') as source:
            duration=source.getnframes()/source.getframerate()
        self.assertAlmostEqual(clip.length,duration,places=2)
        clip.volume=0;clip.play()
        self.assertEqual(clip.state,'play')
        clip.stop()


if __name__=='__main__':unittest.main()
