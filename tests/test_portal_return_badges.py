"""The real return callback refreshes military data before another turn."""
import ast
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import otherworlds as worlds
from test_otherworlds import fixture


def load_nodes(file,names,ns):
    nodes=[n for n in ast.walk(ast.parse(Path(file).read_text(encoding='utf-8')))
           if isinstance(n,ast.FunctionDef) and n.name in names]
    exec(compile(ast.Module(body=nodes,type_ignores=[]),file,'exec'),ns)
    return ns


class ReturnBadgeTests(unittest.TestCase):
    def test_home_refreshes_badge_and_hero_flag_without_a_turn(self):
        db=fixture();self.addCleanup(db.close)
        db.executescript('''ALTER TABLE cities ADD COLUMN icon_coordinates TEXT DEFAULT '[100,100]';
            ALTER TABLE cities ADD COLUMN kf_crystal REAL DEFAULT 0;
            CREATE TABLE political_systems(faction,system);
            CREATE TABLE diplomacies(faction1,faction2,relationship);''')
        worlds.enter(db,'Север','Home')
        ns=load_nodes('game_process.py',{'update_city_military_status','calculate_star_level','update_army_rating'},
                      {'sqlite3':sqlite3,'ast':ast})
        cls=type('Screen',(),{name:ns[name] for name in
                 ('update_city_military_status','calculate_star_level','update_army_rating')})
        screen=cls();screen.conn=db;screen.selected_faction='Север';screen.parent=None
        screen.draw_army_stars_on_map=Mock()
        screen.update_army_rating()
        self.assertEqual(screen.city_star_levels['Home'][0],0)
        refresh_ns=load_nodes('game_process.py',{'refresh_map'},{'_active_game_screen':screen})
        module=SimpleNamespace(_active_game_screen=screen,refresh_map=refresh_ns['refresh_map'])
        callbacks=load_nodes('otherworld_ui.py',{'_refresh_main','home'},
            {'sync_resources':lambda *args:None,'_screen':lambda conn:screen,
             '_busy':lambda conn:False,'worlds':worlds})
        popup=SimpleNamespace(conn=db,faction='Север',dismiss=Mock())
        with patch.dict(sys.modules,{'game_process':module}):
            callbacks['home'](popup)
        self.assertEqual(screen.city_star_levels['Home'][0],3)
        self.assertTrue(screen.city_star_levels['Home'][4])
        self.assertIsNone(worlds.party(db,'Север'))
        self.assertEqual(db.execute('SELECT turn_count FROM turn').fetchone()[0],0)
        popup.dismiss.assert_called_once()
        self.assertEqual(screen.draw_army_stars_on_map.call_count,2)
