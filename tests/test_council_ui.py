import sqlite3
import time
import unittest
from types import SimpleNamespace

from strategy_ui_fixture import Window, Label, Button, dp
from kivy.base import EventLoop
from window_theme import install_window_theme
from nobles import show_nobles_window


def settle():
    for _ in range(20):
        time.sleep(.015)
        EventLoop.idle()


class CouncilUITests(unittest.TestCase):
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
            (2,2,75,'active','Генрих','Борьба','1,0,1'),(3,3,25,'active','Иван','Любит Эльфы','0,0,0');
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
            actions = [w for w in popup.content.walk() if isinstance(w, Button)]
            self.assertEqual(sum(w.text.startswith('Устранить') for w in actions), 3)
            self.assertFalse(any(w.text == 'Тайная служба' for w in actions))
            self.assertEqual(popup.advisor_grid.cols, 3)
            _, bottom = popup.advisor_grid.to_window(popup.advisor_grid.x, popup.advisor_grid.y)
            self.assertGreaterEqual(bottom, popup._window_action_dock.top)
        finally:
            popup.dismiss(animation=False)
            db.close()
            Window.size = old_size
            settle()


if __name__ == '__main__':
    unittest.main()
