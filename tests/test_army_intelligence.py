import ast
from contextlib import redirect_stdout
import io
from pathlib import Path
import sqlite3
import unittest

import army_intelligence as intel


def fixture():
    db=sqlite3.connect(':memory:')
    db.executescript('''CREATE TABLE cities(name,faction);
        INSERT INTO cities VALUES('Дом','Север'),('Замок','Адепты'),('Роща','Эльфы'),('Пристань','Нейтрал');
        CREATE TABLE user_faction(faction_name);INSERT INTO user_faction VALUES('Север');
        CREATE TABLE turn(turn_count);INSERT INTO turn VALUES(5);
        CREATE TABLE resources(faction,resource_type,amount);INSERT INTO resources VALUES('Север','Кроны',5000000);''')
    return db


class IntelligenceTests(unittest.TestCase):
    def setUp(self):self.db=fixture();self.addCleanup(self.db.close)

    def test_own_army_is_visible_foreign_unknown_without_writing_schema(self):
        before=list(self.db.iterdump())
        self.assertTrue(intel.city_visible(self.db,'Север','Дом'))
        self.assertFalse(intel.city_visible(self.db,'Север','Замок'))
        self.assertEqual(intel.player_faction(self.db),'Север')
        self.assertEqual(list(self.db.iterdump()),before)

    def test_report_lasts_current_and_next_turn_then_hides_again(self):
        self.assertEqual(intel.gather(self.db,'Север','Адепты','Дом')['expires'],7)
        for turn,left in ((5,2),(6,1),(7,0),(8,0)):
            self.db.execute('UPDATE turn SET turn_count=?',(turn,))
            self.assertEqual(intel.remaining(self.db,'Север','Адепты'),left)
            self.assertEqual(intel.city_visible(self.db,'Север','Замок'),left>0)

    def test_reports_are_scoped_to_player_and_faction_and_survive_save(self):
        intel.gather(self.db,'Север','Адепты','Дом');self.db.commit()
        clone=sqlite3.connect(':memory:');self.addCleanup(clone.close);self.db.backup(clone)
        self.assertTrue(intel.visible(clone,'Север','Адепты'))
        self.assertFalse(intel.visible(clone,'Север','Эльфы'))
        self.assertFalse(intel.visible(clone,'Эльфы','Адепты'))

    def test_tavern_access_and_neutral_reports(self):
        with self.assertRaises(ValueError):intel.gather(self.db,'Север','Эльфы','Замок')
        intel.gather(self.db,'Север','Нейтрал','Пристань')
        self.assertTrue(intel.city_visible(self.db,'Север','Пристань'))
        with self.assertRaises(ValueError):intel.gather(self.db,'Север','Север','Дом')

    def test_refresh_and_turn_rollback_do_not_leave_permanent_visibility(self):
        intel.gather(self.db,'Север','Адепты','Дом')
        self.db.execute('UPDATE turn SET turn_count=6')
        intel.gather(self.db,'Север','Адепты','Дом')
        self.assertEqual(intel.remaining(self.db,'Север','Адепты'),2)
        self.db.execute('UPDATE turn SET turn_count=8')
        self.assertFalse(intel.visible(self.db,'Север','Адепты'))
        self.db.execute('UPDATE turn SET turn_count=1')
        self.assertFalse(intel.visible(self.db,'Север','Адепты'))

    def test_first_turn_works_before_turn_counter_is_persisted(self):
        self.db.execute('DELETE FROM turn')
        intel.gather(self.db,'Север','Адепты','Дом')
        self.db.execute('INSERT INTO turn VALUES(2)')
        self.assertEqual(intel.remaining(self.db,'Север','Адепты'),1)
        self.db.execute('UPDATE turn SET turn_count=3')
        self.assertFalse(intel.visible(self.db,'Север','Адепты'))

    def test_both_new_campaign_reset_paths_erase_reports(self):
        for filename in ('main.py','results_game.py'):
            with self.subTest(filename=filename):
                db=fixture();self.addCleanup(db.close)
                intel.gather(db,'Север','Адепты','Дом')
                node=next(n for n in ast.parse(Path(filename).read_text(encoding='utf-8-sig')).body
                          if isinstance(n,ast.FunctionDef) and n.name=='clear_tables')
                ns=dict(sqlite3=sqlite3)
                exec(compile(ast.Module(body=[node],type_ignores=[]),filename,'exec'),ns)
                with redirect_stdout(io.StringIO()):ns['clear_tables'](db)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM map_army_intelligence').fetchone()[0],0)


if __name__=='__main__':unittest.main()
