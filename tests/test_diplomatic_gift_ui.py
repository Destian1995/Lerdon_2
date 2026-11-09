import ast
from pathlib import Path
import random
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from strategy_ui_fixture import Window
from test_dialog_layout import settle
from kivy.metrics import Metrics,dp
from kivy.uix.popup import Popup
from kivy.uix.boxlayout import BoxLayout
from window_theme import install_window_theme
from diplomatic_gift_ui import DiplomaticGiftPopup
from utils.resource_text import resource_amount


class GiftFormattingTests(unittest.TestCase):
    def test_declensions_and_fractional_balances(self):
        for n,ending in ((1,'кристалл'),(2,'кристалла'),(5,'кристаллов'),(11,'кристаллов'),(21,'кристалл'),(112,'кристаллов')):
            self.assertEqual(resource_amount(n,'Кристаллы'),f'{n} {ending}')
        self.assertEqual(resource_amount(1,'Кроны'),'1 крона')
        self.assertEqual(resource_amount(24,'Кроны'),'24 кроны')
        self.assertEqual(resource_amount(1_991_775.7500000002,'Кристаллы'),'1,9 млн. кристаллов')
        self.assertEqual(resource_amount(100000,'Кристаллы'),'100 тыс. кристаллов')
        self.assertEqual(resource_amount(100001,'Кроны',compact=False),'100 001 крона')
        self.assertEqual(resource_amount(1234.9,'Рабочие'),'1,2 тыс. рабочих')


class DiplomaticGiftTests(unittest.TestCase):
    def setUp(self):
        self.size=Window.size;self.metrics=Metrics.density,Metrics.fontscale
        Metrics.density=Metrics.fontscale=1;Window.size=(1000,700);install_window_theme();settle()

    def tearDown(self):
        for p in list(Window.children):
            if isinstance(p,Popup):p.dismiss(animation=False)
        settle();Metrics.density,Metrics.fontscale=self.metrics;Window.size=self.size;settle()

    def test_small_screens_keep_actions_visible_and_description_scrollable(self):
        from diplomatic_gifts import GiftQuote
        quote=GiftQuote(25000,(1,1,1),30000,2,15,8250)
        p=DiplomaticGiftPopup('Вампиры','Кристаллы',quote.total,1_991_775.7500000002,73,8,quote=quote)
        p.open(animation=False);settle()
        self.assertEqual(p.need_label.text,'Фракция нуждается в кристаллах.')
        self.assertEqual(p.balance_label.text,'1,9 млн. кристаллов')
        self.assertEqual(p.relation_label.text.replace('→','->'),'73%  ->  81%')
        for screen,density,scale in (((1000,700),1,1),((640,360),1,1),((1280,576),2,1.2),((320,568),1,1.3)):
            Window.size=screen;Metrics.density=density;Metrics.fontscale=scale;settle();p.fit();settle()
            self.assertGreater(p.scroll.height,dp(50))
            for button in (p.confirm_button,p.cancel_button):
                self.assertGreaterEqual(button.height,dp(48)-1)
                self.assertGreaterEqual(button.y,p.y)
                self.assertLessEqual(button.top,p.top)
                self.assertGreaterEqual(button.x,p.x)
                self.assertLessEqual(button.right,p.right+1)
            if screen==(640,360):
                p.export_to_png('.release/diplomatic-gift-phone.png')
                p.scroll.scroll_y=0;settle();p.export_to_png('.release/diplomatic-gift-breakdown-phone.png')
        p.export_to_png('.release/diplomatic-gift-portrait.png')

    def test_insufficient_balance_disables_gift_and_explains_shortage(self):
        p=DiplomaticGiftPopup('Элины','Кроны',500000,1234.567,20,5)
        self.assertTrue(p.confirm_button.disabled)
        self.assertEqual(p.need_label.text,'Фракция нуждается в кронах.')
        self.assertTrue(p.remaining_label.text.startswith('Не хватает:'))

    def test_real_chat_action_charges_exactly_once_and_restores_chat_on_close(self):
        db=sqlite3.connect(':memory:');self.addCleanup(db.close)
        db.executescript('CREATE TABLE resources(faction,resource_type,amount); CREATE TABLE relations(faction1,faction2,relationship);')
        db.executemany('INSERT INTO resources VALUES(?,?,?)',[('Север','Кристаллы',1991775.75),('Вампиры','Кристаллы',200000),('Вампиры','Кроны',1000000)])
        db.execute('INSERT INTO relations VALUES(?,?,?)',('Север','Вампиры',73));db.commit()
        db.executescript('''CREATE TABLE cities(name,faction,kf_crystal);
            INSERT INTO cities VALUES('A','Вампиры',1.1),('B','Вампиры',2.3),('C','Вампиры',5.3),('D','Север',1);''')
        obj=SimpleNamespace(db_connection=db,selected_faction='Вампиры',_get_player_faction=lambda:'Север',
                            _calculate_army_strength=lambda faction:100 if faction=='Вампиры' else 200,
                            _get_faction_resources=lambda faction:dict(db.execute('SELECT resource_type,amount FROM resources WHERE faction=?',(faction,))),
                            add_chat_message_system=Mock(),add_chat_message=Mock(),update_relation_info_android=Mock())
        tree=ast.parse(Path('ai_models/diplomacy_chat.py').read_text(encoding='utf-8'))
        node=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='_show_improve_relations')
        restore=Mock();namespace=dict(self=obj,quick_row=BoxLayout(),_show_main_buttons=restore,random=random)
        exec(compile(ast.Module(body=[node],type_ignores=[]),'gift-action','exec'),namespace)
        with patch.dict('sys.modules',game_process=SimpleNamespace(_active_game_screen=None)):
            namespace['_show_improve_relations'](None);settle()
            p=next(w for w in Window.children if isinstance(w,DiplomaticGiftPopup))
            self.assertEqual(p.quote.total,63250)
            self.assertIn('25%',p.breakdown.text)
            self.assertIn('Армия №2',p.breakdown.text)
            p.confirm_button.dispatch('on_release');settle()
            p.confirm_button.dispatch('on_release');settle()
        self.assertEqual(db.execute('SELECT amount FROM resources WHERE faction=?',('Север',)).fetchone()[0],1928525.75)
        self.assertEqual(db.execute('SELECT amount FROM resources WHERE faction=? AND resource_type=?',('Вампиры','Кристаллы')).fetchone()[0],263250)
        self.assertEqual(db.execute('SELECT relationship FROM relations').fetchone()[0],81)
        restore.assert_called_once();self.assertEqual(obj.add_chat_message.call_count,2)


if __name__=='__main__':unittest.main()
