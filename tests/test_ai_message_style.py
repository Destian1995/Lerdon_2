"""Faction letters stay readable and keep original diplomatic callbacks."""
import ast
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace
from strategy_ui_fixture import ROOT,Window
from strategy_ui_fixture import __dict__ as fixture_globals
from test_responsive_windows import settle
from kivy.metrics import Metrics,dp
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.image import Image
from message_ui import PRESENTATION,letter_content,highlighted_letter,GREEN


def popup_class():
    tree=ast.parse((ROOT/'ui_components.py').read_text(encoding='utf-8'))
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='DiplomacyMessagePopup')
    namespace=dict(fixture_globals)
    exec(compile(ast.Module(body=[cls],type_ignores=[]),'ui_components.py','exec'),namespace)
    return namespace[cls.name]


class MessageStyleTests(unittest.TestCase):
    def setUp(self):
        self.size=Window.size;self.metrics=Metrics.density,Metrics.fontscale
        Metrics.density=Metrics.fontscale=1;Window.size=(640,360);settle()
        self.popups=[];self.calls=[];self.Popup=popup_class()

    def tearDown(self):
        for p in self.popups:p._cleanup()
        Metrics.density,Metrics.fontscale=self.metrics;Window.size=self.size;settle()

    def letter(self,kind,text=None):
        text=text or '[СОЮЗ] Пророчества ясны: наши пути едины. 2 города и 1 воин — всё это ваше, если вы с нами.'
        p=self.Popup('Адепты',text,kind,on_respond=lambda *args:self.calls.append(args))
        Window.add_widget(p);self.popups.append(p);settle()
        return p

    def test_every_type_uses_portrait_title_and_same_card(self):
        for kind,(caption,_) in PRESENTATION.items():
            p=self.letter(kind,'[ИНФОРМАЦИЯ] Послание фракции.' if kind=='info' else None)
            self.assertEqual(p.card.title_label.text,caption)
            self.assertIsInstance(p.card.portrait,Image)
            self.assertTrue(p.card.portrait.texture)
            self.assertEqual(p.card.sender_label.text,'Послание от фракции Адепты')
            self.assertNotIn('[СОЮЗ]',p.card.message_label.text)
            p._cleanup()

    def test_narrow_landscape_android_and_large_fonts_keep_actions_and_scroll(self):
        for size,density,fontscale in (((640,360),1,1.5),((1280,576),2,1.2),((320,568),1,1.4)):
            Window.size=size;Metrics.density=density;Metrics.fontscale=fontscale;settle()
            p=self.letter('alliance','[СОЮЗ] '+('Мы предлагаем союз и помощь в войне. '*90))
            card=p.card
            self.assertGreater(card.message_scroll.height,dp(40))
            self.assertGreater(card.message_label.height,card.message_scroll.height)
            self.assertEqual(card.actions.orientation,'vertical' if size[0]/density<440 else 'horizontal')
            for button in card.actions.children:
                self.assertGreaterEqual(button.height,dp(48)-1)
                self.assertGreaterEqual(button.y,card.y)
                self.assertLessEqual(button.top,card.top)
            card.message_scroll.scroll_y=0;settle()
            button=next(b for b in card.actions.children if b.text=='Принять')
            button.dispatch('on_release');self.assertEqual(self.calls[-1],('Адепты','да',p.message))
            p._cleanup()

    def test_trade_panels_keep_exact_values_and_all_responses_keep_original(self):
        original='[ТОРГОВЛЯ] Мы отдаём 1 тыс. Кроны, вы — 1.2 тыс. Кристаллы'
        p=self.letter('trade',original)
        self.assertEqual([panel[2].text for panel in p.card.offer_panels],['1 тыс.','1.2 тыс.'])
        self.assertIsNone(p.card.message_scroll)
        next(b for b in p.card.actions.children if b.text=='Отклонить').dispatch('on_release')
        self.assertEqual(self.calls[-1],('Адепты','нет',original))
        q=self.letter('warning','[ПРЕДУПРЕЖДЕНИЕ] Армия идёт к границе.')
        self.assertEqual({b.text for b in q.card.actions.children},{'Ясно','Ответить'})
        next(b for b in q.card.actions.children if b.text=='Ответить').dispatch('on_release')
        self.assertEqual(self.calls[-1],('Адепты','__open_chat__',q.message))

    def test_fallback_tags_numbers_and_untrusted_markup_remain_readable(self):
        kind,text=letter_content('[ТРЕБОВАНИЕ] Верните 15% крон. [b]Условие[/b]')
        self.assertEqual(kind,'demand');self.assertIn('[b]',text)
        marked=highlighted_letter(text,GREEN)
        self.assertIn('&bl;b&br;',marked);self.assertIn('15%',marked)
        p=self.letter('trade','[ТОРГОВЛЯ] Предлагаем обсудить ресурсы.')
        self.assertIsNotNone(p.card.message_scroll)
        self.assertEqual(p.card.message_label.text,'Предлагаем обсудить ресурсы.')

    def test_letter_content_consumes_touch_instead_of_clicking_map(self):
        p=self.letter('alliance')
        touch=SimpleNamespace(pos=p.card.message_scroll.center,is_mouse_scrolling=False,ud={})
        # A label is not a button; the overlay still owns this touch.
        with patch.object(FloatLayout,'on_touch_down',return_value=False):
            self.assertTrue(p.on_touch_down(touch))

    def test_war_notification_uses_shared_letter_without_accept_action(self):
        tree=ast.parse((ROOT/'game_process.py').read_text(encoding='utf-8'))
        game=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='GameScreen')
        method=next(n for n in game.body if isinstance(n,ast.FunctionDef) and n.name=='show_war_declaration_popup')
        ns={};exec(compile(ast.Module(body=[method],type_ignores=[]),'game_process.py','exec'),ns)
        module=SimpleNamespace(DiplomacyMessagePopup=self.Popup)
        owner=SimpleNamespace(_handle_diplomacy_response=Mock())
        with patch.dict('sys.modules',ui_components=module),patch.object(self.Popup,'open'):
            p=ns[method.name](owner,['Вампиры','Элины'])
        Window.add_widget(p);self.popups.append(p);settle()
        self.assertIn('Вампиры, Элины',p.message)
        self.assertEqual(p.card.title_label.text,'Объявление войны')
        self.assertEqual({b.text for b in p.card.actions.children},{'Ясно','Ответить'})
