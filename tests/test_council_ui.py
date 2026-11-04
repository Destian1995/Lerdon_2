import sqlite3
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from strategy_ui_fixture import Window, Label, Button, dp
from kivy.base import EventLoop
from window_theme import install_window_theme
from nobles import show_nobles_window, show_event_popup, UIStyles
from diversion import CalculateCash
from kivy.uix.popup import Popup


def settle():
    for _ in range(20):
        time.sleep(.015)
        EventLoop.idle()


class CouncilUITests(unittest.TestCase):
    def test_event_with_legacy_duplicate_balance_charges_total_once(self):
        db = sqlite3.connect(':memory:')
        db.executescript('''
            CREATE TABLE resources(id INTEGER PRIMARY KEY, faction TEXT, resource_type TEXT, amount REAL);
            INSERT INTO resources VALUES(1,'Север','Кроны',2400000),(2,'Север','Кроны',2400000);
            CREATE TABLE nobles(id INTEGER, status TEXT, name TEXT, ideology TEXT);
            INSERT INTO nobles VALUES(1,'active','Игорь','{"type":"greed","demand":4431}');
        ''')
        model = SimpleNamespace(conn=db, resources={})
        refresh = Mock()
        try:
            cash = CalculateCash('Север', model)
            with patch('nobles.update_noble_loyalty_for_event') as loyalty, \
                    patch('nobles.pay_greedy_noble') as bribe, \
                    patch('nobles.show_toast_notification') as toast:
                show_event_popup(db, 'Север', 3, refresh, cash)
                popup = next(w for w in Window.children if isinstance(w, Popup))
                settle()
                confirm = next(w for w in popup.content.walk() if isinstance(w, Button) and w.text == 'Провести')
                confirm.dispatch('on_release')
                confirm.dispatch('on_release')
                amount, count = db.execute("SELECT amount, COUNT(*) FROM resources WHERE faction='Север' AND resource_type='Кроны'").fetchone()
                self.assertEqual((amount, count), (2400000 - 18200 - 4431, 1))
                self.assertEqual(model.money, amount)
                loyalty.assert_called_once()
                bribe.assert_called_once_with(db, 1, 4431)
                self.assertTrue(toast.call_args.kwargs['is_success'])
        finally:
            for popup in list(Window.children):
                if isinstance(popup, Popup):
                    popup.dismiss(animation=False)
            db.close()

    def test_all_advisors_and_secret_service_share_the_main_window(self):
        install_window_theme()
        old_size = Window.size
        Window.size = (900, 640)
        db = sqlite3.connect(':memory:')
        db.executescript('''
            CREATE TABLE user_faction(faction_name TEXT); INSERT INTO user_faction VALUES('Север');
            CREATE TABLE season(id INTEGER,season_index INTEGER); INSERT INTO season VALUES(1,0);
            CREATE TABLE nobles(id INTEGER,priority INTEGER,loyalty REAL,status TEXT,name TEXT,ideology TEXT,attendance_history TEXT);
            INSERT INTO nobles VALUES(1,1,80,'active','Николай','Смирение','1,1,1'),
            (2,2,61.6036,'active','Генрих','{"type":"greed","demand":3159}','1,0,1'),
            (3,3,25,'active','Иван','Любит Эльфы','0,0,0');
            CREATE TABLE resources(faction TEXT,resource_type TEXT,amount REAL);
            INSERT INTO resources VALUES('Север','Кроны',500000),('Север','Рабочие',500);
        ''')
        model = SimpleNamespace(conn=db, resources={})
        popup = show_nobles_window(db, 'Север', model)
        try:
            settle()
            labels = [w.text for w in popup.content.walk() if isinstance(w, Label)]
            for name in ('Николай', 'Генрих', 'Иван'):
                self.assertIn(name, labels)
            for text, color in (('Лояльность: 80% · высокая', UIStyles.COLOR_SUCCESS),
                                ('Лояльность: 61% · средняя', UIStyles.COLOR_GOLD),
                                ('Лояльность: 25% · низкая', UIStyles.COLOR_DANGER)):
                label = next(w for w in popup.content.walk() if isinstance(w, Label) and w.text == text)
                self.assertEqual(tuple(label.color), color)
            self.assertEqual(db.execute('SELECT loyalty FROM nobles WHERE id=2').fetchone()[0], 61.6036)
            actions = [w for w in popup.content.walk() if isinstance(w, Button)]
            self.assertEqual(sum(w.text.startswith('Устранить') for w in actions), 3)
            self.assertFalse(any(w.text == 'Тайная служба' for w in actions))
            self.assertFalse(any(w.text == 'Договориться' for w in actions))
            self.assertFalse(any('Пороги лояльности' in text for text in labels))
            self.assertEqual(popup.advisor_grid.cols, 3)
            _, bottom = popup.advisor_grid.to_window(popup.advisor_grid.x, popup.advisor_grid.y)
            self.assertGreaterEqual(bottom, popup.council_actions.top)
            self.assertEqual(len(popup.council_header.children), 2)
            for size in ((640,360),(1280,576),(392,844)):
                Window.size=size;settle()
                self.assertGreater(popup.advisor_scroll.height,80)
                self.assertGreaterEqual(popup.advisor_scroll.y,popup.council_actions.top)
                for card in popup.advisor_grid.children:
                    popup.advisor_scroll.scroll_to(card,padding=0,animate=False);settle()
                    self.assertLessEqual(card.y,popup.advisor_scroll.top)
                    self.assertGreaterEqual(card.top,popup.advisor_scroll.y)
        finally:
            popup.dismiss(animation=False)
            db.close()
            Window.size = old_size
            settle()


if __name__ == '__main__':
    unittest.main()
