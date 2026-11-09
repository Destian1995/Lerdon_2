"""Exercise real ending taps, modal cleanup and the app's menu restart path."""
import ast
from pathlib import Path
from types import SimpleNamespace,MethodType
from unittest.mock import Mock
import sqlite3
import gc
import time
import weakref
import unittest
from strategy_ui_fixture import Window
from kivy.clock import Clock
from kivy.metrics import Metrics
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.popup import Popup
from kivy.tests.common import UnitTestTouch
from test_dialog_layout import settle
from window_theme import install_window_theme,is_close_button
from results_ui import show_campaign_results

ROOT=Path(__file__).resolve().parents[1]

def method(file,cls,name,namespace):
 tree=ast.parse((ROOT/file).read_text(encoding='utf-8'))
 parent=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
 node=next(n for n in parent.body if isinstance(n,ast.FunctionDef) and n.name==name)
 exec(compile(ast.Module(body=[node],type_ignores=[]),file,'exec'),namespace)
 return namespace[name]

class EndingExitTests(unittest.TestCase):
 def test_touch_returns_to_menu_once_and_closes_every_campaign_modal(self):
  original_open=Popup.open;size=Window.size;metrics=(Metrics.density,Metrics.fontscale)
  db=sqlite3.connect(':memory:')
  try:
   install_window_theme();Window.size=(640,360);Metrics.density=1;Metrics.fontscale=1
   root=BoxLayout();root.add_widget(Label(text='Campaign'))
   class AppState:pass
   app=AppState();app.root=root;app.conn=db;app.selected_kingdom='old'
   clear=Mock();restore=Mock()
   ns=dict(Clock=Clock,sqlite3=sqlite3,clear_tables=clear,restore_from_backup=restore,
           MenuWidget=lambda conn:Label(text='Main menu'))
   app.recreate_main_menu=MethodType(method('main.py','Lerdon','recreate_main_menu',ns),app)
   app.restart_app=MethodType(method('main.py','Lerdon','restart_app',ns),app)
   exit_ns=dict(App=SimpleNamespace(get_running_app=lambda:app),Window=Window)
   class Owner:pass
   owner=Owner();owner.conn=None;owner.game_status='lose';owner.reason='Defeat'
   owner.exit_to_main_menu=MethodType(method('results_game.py','ResultsGame','exit_to_main_menu',exit_ns),owner)
   underneath=ModalView();underneath.open(animation=False)
   # Campaign overlays can veto ordinary dismiss; returning to menu must still close them.
   underneath.bind(on_dismiss=lambda *_:True)
   popup=show_campaign_results(owner,'Result','',[],(1,1,1,1));settle()
   owner_ref=weakref.ref(owner);del owner;gc.collect()
   self.assertIsNotNone(owner_ref(), 'The ending must retain its temporary ResultsGame owner')
   self.assertFalse(any(is_close_button(w) for w in popup.content.walk()))
   self.assertFalse(popup.auto_dismiss)
   for tab in (popup.statistics_button,popup.summary_button):
    tab.dispatch('on_release');settle()
   button=popup.exit_button
   self.assertGreaterEqual(button.y,popup.y)
   self.assertLessEqual(button.top,popup.top)
   touch=UnitTestTouch(*button.to_window(*button.center));touch.touch_down();touch.touch_up()
   owner_ref().exit_to_main_menu()  # A second release must not reset or create another menu.
   time.sleep(.25);settle()
   self.assertIsNone(popup.parent);self.assertIsNone(underneath.parent)
   self.assertIsNone(owner_ref().popup);self.assertIsNone(app.selected_kingdom)
   self.assertEqual([w.text for w in root.children],['Main menu'])
   clear.assert_called_once_with(db);restore.assert_called_once_with(db)
  finally:
   for w in list(Window.children):
    if isinstance(w,ModalView):w.dismiss(force=True,animation=False)
   Popup.open=original_open;Metrics.density,Metrics.fontscale=metrics;Window.size=size;db.close();settle()

if __name__=='__main__':unittest.main()
